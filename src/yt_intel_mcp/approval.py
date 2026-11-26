"""User-mediated approval for playlist creation (FR-5.6, TBD-5, UI-5).

Order of preference:
(a) MCP elicitation, when the client advertises it: the user sees the exact proposal summary and
    accepts, declines or cancels in the client UI.
(b) Local approval prompt: a single-use code (CSPRNG) is shown with the proposal summary on a page
    served on the loopback interface and opened in the system browser, outside the AI conversation.
    The code is stored only as a salted hash bound to the proposal ID. It never appears in a tool
    result, resource, prompt, log or error; the user types it back to the AI client.
(c) Neither available -> fail closed (no write).
"""

from __future__ import annotations

import hashlib
import hmac
import html
import secrets
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Literal, Protocol

import anyio
from pydantic import BaseModel, Field

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I
CODE_LENGTH = 8
PBKDF2_ITERATIONS = 200_000
MAX_CODE_ATTEMPTS = 3
ELICITATION_TIMEOUT_SECONDS = 300

ElicitOutcome = Literal["approved", "declined", "cancelled", "timed_out", "unsupported"]


# --- codes -----------------------------------------------------------------------------------------


def generate_code(length: int = CODE_LENGTH) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(max(6, length)))


def normalise_code(code: str) -> str:
    return "".join(ch for ch in code.upper() if ch.isalnum())


def hash_code(code: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", normalise_code(code).encode(), salt, PBKDF2_ITERATIONS).hex()


def new_code_record(length: int = CODE_LENGTH) -> tuple[str, str, str]:
    """Returns ``(code, salt_hex, hash_hex)``. Only the hash and salt are stored."""
    code = generate_code(length)
    salt = secrets.token_bytes(16)
    return code, salt.hex(), hash_code(code, salt)


def verify_code(code: str, salt_hex: str | None, hash_hex: str | None) -> bool:
    if not code or not salt_hex or not hash_hex:
        return False
    return hmac.compare_digest(hash_code(code, bytes.fromhex(salt_hex)), hash_hex)


# --- (a) elicitation -------------------------------------------------------------------------------


class ApprovalForm(BaseModel):
    approve: bool = Field(
        default=False,
        description="Set to true to create exactly this playlist on YouTube. Leave false to decline.",
    )


def elicitation_supported(ctx: Any) -> bool:
    try:
        caps = ctx.client_capabilities
    except Exception:  # noqa: BLE001 - no request context
        return False
    return bool(caps is not None and getattr(caps, "elicitation", None) is not None)


async def elicit_approval(
    ctx: Any, message: str, timeout_seconds: float = ELICITATION_TIMEOUT_SECONDS
) -> ElicitOutcome:
    from mcp.shared.exceptions import NoBackChannelError

    try:
        with anyio.fail_after(timeout_seconds):
            result = await ctx.elicit(message, ApprovalForm)
    except TimeoutError:
        return "timed_out"
    except NoBackChannelError:
        return "unsupported"
    except Exception:  # noqa: BLE001 - anything unexpected fails closed
        return "cancelled"
    action = getattr(result, "action", None)
    if action == "accept":
        data = getattr(result, "data", None)
        return "approved" if data is not None and data.approve is True else "declined"
    if action == "decline":
        return "declined"
    return "cancelled"


# --- (b) local approval prompt ---------------------------------------------------------------------


class LocalApprovalPrompt(Protocol):
    def available(self) -> bool: ...
    def show(self, proposal_id: str, summary: str, code: str, expires_at: datetime) -> None: ...


def render_page(summary: str, code: str, expires_at: datetime) -> str:
    """All proposal text is HTML-escaped: titles are untrusted data."""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Approve playlist creation?</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{{font-family:system-ui,sans-serif;max-width:46rem;margin:2rem auto;padding:0 1rem;line-height:1.45}}
pre{{white-space:pre-wrap;background:#f4f4f4;padding:1rem;border-radius:6px}}
.code{{font-size:2.2rem;letter-spacing:.3rem;font-weight:700;font-family:ui-monospace,monospace}}
.warn{{color:#8a4b00}}
</style></head><body>
<h1>Approve playlist creation?</h1>
<p>Your AI assistant asked the YouTube Video Intelligence server to create this playlist:</p>
<pre>{html.escape(summary)}</pre>
<p>If you approve, type this one-time code into your AI client:</p>
<p class="code">{html.escape(code)}</p>
<p>If you do not approve, ignore this page. Nothing is created without the code.
The code expires at {html.escape(expires_at.isoformat(timespec="minutes"))}.</p>
<p class="warn">Never share this code if you did not ask for this playlist.</p>
</body></html>"""


class BrowserApprovalPrompt:
    """Serves the approval page on 127.0.0.1 and opens the system browser."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def available(self) -> bool:
        if not self.enabled:
            return False
        try:
            webbrowser.get()
        except webbrowser.Error:
            return False
        return True

    def show(self, proposal_id: str, summary: str, code: str, expires_at: datetime) -> None:
        page = render_page(summary, code, expires_at).encode("utf-8")
        path = "/approve/" + secrets.token_urlsafe(16)

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - stdlib API
                if self.client_address[0] != "127.0.0.1" or self.path != path:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'")
                self.send_header("X-Frame-Options", "DENY")
                self.end_headers()
                self.wfile.write(page)

            def log_message(self, *args: Any) -> None:  # never log requests
                return

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        lifetime = max(5.0, (expires_at - datetime.now(expires_at.tzinfo)).total_seconds())
        threading.Thread(target=server.serve_forever, daemon=True).start()
        threading.Timer(lifetime, server.shutdown).start()
        webbrowser.open(f"http://127.0.0.1:{server.server_address[1]}{path}")


class RecordingApprovalPrompt:
    """Test double standing in for the human looking at the local approval page."""

    def __init__(self, available: bool = True) -> None:
        self._available = available
        self.shown: list[dict[str, Any]] = []

    def available(self) -> bool:
        return self._available

    def show(self, proposal_id: str, summary: str, code: str, expires_at: datetime) -> None:
        self.shown.append({"proposal_id": proposal_id, "summary": summary, "code": code, "expires_at": expires_at})

    @property
    def last_code(self) -> str:
        return self.shown[-1]["code"]
