"""Logging with redaction (FR-4.6, NFR-10) and per-tool timing (NFR-1).

Logs go to stderr only (stdout is the MCP stdio transport). Log calls must never pass titles,
descriptions, channel names, queries or other account content; :func:`log_event` drops such keys
and every record is passed through :func:`redact` as a second line of defence.
"""

from __future__ import annotations

import logging
import re
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

LOGGER_NAME = "yt_intel_mcp"

SENSITIVE_KEYS = frozenset(
    {
        "title",
        "description",
        "tags",
        "channel_title",
        "channel_name",
        "query",
        "topic",
        "email",
        "token",
        "access_token",
        "refresh_token",
        "code",
        "confirmation_code",
        "account_id",
        "channel_id",
    }
)

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"ya29\.[0-9A-Za-z_\-.]+"), "[REDACTED_TOKEN]"),
    (re.compile(r"1//[0-9A-Za-z_\-]{10,}"), "[REDACTED_TOKEN]"),
    (re.compile(r"(?i)\bbearer\s+[^\s\"']+"), "Bearer [REDACTED_TOKEN]"),
    (
        re.compile(
            r"(?i)([\"']?(?:access_token|refresh_token|id_token|client_secret|token|code)[\"']?\s*[:=]\s*[\"']?)"
            r"[^\"'\s,&}]+"
        ),
        r"\1[REDACTED]",
    ),
    (re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"), "[REDACTED_EMAIL]"),
    (re.compile(r"\bUC[A-Za-z0-9_\-]{22}\b"), "[REDACTED_CHANNEL_ID]"),
]


def redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Tracebacks are not emitted: only the (redacted) message.
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return redact(super().format(record))


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if not any(getattr(h, "_yt_intel", False) for h in logger.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        handler._yt_intel = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def log_event(event: str, level: int = logging.INFO, **fields: Any) -> None:
    safe = {k: v for k, v in fields.items() if k not in SENSITIVE_KEYS}
    text = " ".join(f"{k}={v}" for k, v in sorted(safe.items()))
    get_logger().log(level, redact(f"event={event} {text}".strip()))


@contextmanager
def tool_timer(tool: str) -> Iterator[dict[str, Any]]:
    """Logs tool name, duration and outcome (never arguments or results)."""
    info: dict[str, Any] = {"outcome": "ok"}
    start = time.perf_counter()
    try:
        yield info
    except BaseException:
        info["outcome"] = "exception"
        raise
    finally:
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        info["duration_ms"] = duration_ms
        log_event(
            "tool_call",
            tool=tool,
            duration_ms=duration_ms,
            **{k: v for k, v in info.items() if k != "duration_ms"},
        )
