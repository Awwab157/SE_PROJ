"""OAuth 2.0 for installed apps (FR-7, UI-4).

* Loopback redirect on 127.0.0.1, ``state`` parameter and PKCE (S256), system browser.
* Read features request only ``youtube.readonly``. The ``youtube`` (write) scope is requested only
  when a playlist is about to be created (incremental authorisation, ``include_granted_scopes``).
* Tokens live in the OS keychain via ``keyring``; if no secure keyring backend exists, they are kept in
  an encrypted file (mode 0600) in the state directory, which is always outside the repo.
* ``invalid_grant`` / revoked / expired refresh tokens raise :class:`InvalidGrant` with
  ``start_authorization`` as the next step (apps in Google "Testing" mode expire tokens after 7 days).
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from yt_intel_mcp.errors import AuthorizationRequired, InvalidGrant, WriteScopeRequired, YTIntelError

SCOPE_READ = "https://www.googleapis.com/auth/youtube.readonly"
SCOPE_WRITE = "https://www.googleapis.com/auth/youtube"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
KEYRING_SERVICE = "yt-intel-mcp"
KEYRING_ACCOUNT = "oauth-credentials"


def scopes_for(write: bool) -> list[str]:
    return [SCOPE_READ, SCOPE_WRITE] if write else [SCOPE_READ]


class Authorizer(Protocol):
    requested_scopes: list[list[str]]

    def credentials(self, write: bool = False) -> Any: ...
    def has_scope(self, write: bool = False) -> bool: ...
    def granted_scopes(self) -> list[str]: ...
    def authorize(self, write: bool = False) -> list[str]: ...
    def revoke(self) -> None: ...


# ==================================================================================================
# Token storage
# ==================================================================================================


class TokenStore(Protocol):
    def load(self) -> str | None: ...
    def save(self, value: str) -> None: ...
    def delete(self) -> None: ...


class MemoryTokenStore:
    def __init__(self, value: str | None = None) -> None:
        self.value = value

    def load(self) -> str | None:
        return self.value

    def save(self, value: str) -> None:
        self.value = value

    def delete(self) -> None:
        self.value = None


class KeyringTokenStore:
    def __init__(self) -> None:
        import keyring

        self._keyring = keyring

    def load(self) -> str | None:
        return self._keyring.get_password(KEYRING_SERVICE, KEYRING_ACCOUNT)

    def save(self, value: str) -> None:
        self._keyring.set_password(KEYRING_SERVICE, KEYRING_ACCOUNT, value)

    def delete(self) -> None:
        try:
            self._keyring.delete_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
        except self._keyring.errors.PasswordDeleteError:
            pass


class EncryptedFileTokenStore:
    """Fallback when no secure keyring backend exists. Files are created with mode 0600."""

    def __init__(self, directory: Path) -> None:
        from cryptography.fernet import Fernet

        self._fernet_cls = Fernet
        self.key_path = directory / "token.key"
        self.data_path = directory / "token.enc"

    @staticmethod
    def _write_private(path: Path, data: bytes) -> None:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        try:
            os.chmod(path, 0o600)
        except OSError:  # pragma: no cover
            pass

    def _fernet(self):
        if not self.key_path.exists():
            self._write_private(self.key_path, self._fernet_cls.generate_key())
        return self._fernet_cls(self.key_path.read_bytes())

    def load(self) -> str | None:
        if not self.data_path.exists():
            return None
        return self._fernet().decrypt(self.data_path.read_bytes()).decode("utf-8")

    def save(self, value: str) -> None:
        self._write_private(self.data_path, self._fernet().encrypt(value.encode("utf-8")))

    def delete(self) -> None:
        for path in (self.data_path, self.key_path):
            if path.exists():
                path.unlink()


def default_token_store(state_dir: Path) -> TokenStore:
    try:
        import keyring
        from keyring.backends import fail

        backend = keyring.get_keyring()
        if not isinstance(backend, fail.Keyring) and getattr(backend, "priority", 0) >= 1:
            return KeyringTokenStore()
    except Exception:  # noqa: BLE001 - any keyring problem means "use the fallback"
        pass
    return EncryptedFileTokenStore(state_dir)


# ==================================================================================================
# Google OAuth
# ==================================================================================================


class AuthManager:
    def __init__(
        self,
        client_secrets_file: Path | None,
        store: TokenStore,
        *,
        on_revoke: Callable[[], None] | None = None,
        timeout_seconds: int = 300,
        open_browser: bool = True,
    ) -> None:
        self.client_secrets_file = client_secrets_file
        self.store = store
        self.on_revoke = on_revoke
        self.timeout_seconds = timeout_seconds
        self.open_browser = open_browser
        self.requested_scopes: list[list[str]] = []

    def _flow(self, scopes: list[str]):
        from google_auth_oauthlib.flow import InstalledAppFlow

        if not self.client_secrets_file or not Path(self.client_secrets_file).exists():
            raise AuthorizationRequired(
                "No OAuth client configuration was found.",
                "Download the OAuth 'Desktop app' client JSON from Google Cloud Console and set "
                "YT_INTEL_CLIENT_SECRETS to its path (keep it outside the repository).",
            )
        return InstalledAppFlow.from_client_secrets_file(
            str(self.client_secrets_file), scopes=scopes, autogenerate_code_verifier=True
        )

    def authorization_url(self, write: bool = False, redirect_uri: str = "http://127.0.0.1:8765/") -> str:
        """Builds the consent URL exactly as :meth:`authorize` does (used by security tests)."""
        scopes = scopes_for(write)
        flow = self._flow(scopes)
        flow.redirect_uri = redirect_uri
        url, _state = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")
        return url

    def authorize(self, write: bool = False) -> list[str]:
        scopes = scopes_for(write)
        self.requested_scopes.append(scopes)
        flow = self._flow(scopes)
        try:
            creds = flow.run_local_server(
                host="127.0.0.1",
                port=0,
                open_browser=self.open_browser,
                timeout_seconds=self.timeout_seconds,
                authorization_prompt_message="Opening your browser to authorise YouTube access.",
                success_message="Authorisation complete. You can close this tab and return to your AI client.",
                access_type="offline",
                include_granted_scopes="true",
                prompt="consent",
            )
        except YTIntelError:
            raise
        except Exception as exc:  # noqa: BLE001 - never leak library messages
            raise AuthorizationRequired(
                "Authorisation did not complete (the browser flow was cancelled, timed out or failed).",
                "Call start_authorization again and finish the consent screen in the browser.",
            ) from exc
        self.store.save(creds.to_json())
        return list(creds.scopes or scopes)

    def _load(self):
        from google.oauth2.credentials import Credentials

        raw = self.store.load()
        if not raw:
            return None
        info = json.loads(raw)
        return Credentials.from_authorized_user_info(info, info.get("scopes"))

    def granted_scopes(self) -> list[str]:
        creds = self._load()
        return list(creds.scopes or []) if creds else []

    def has_scope(self, write: bool = False) -> bool:
        granted = set(self.granted_scopes())
        if write:
            return SCOPE_WRITE in granted
        return bool(granted & {SCOPE_READ, SCOPE_WRITE})

    def credentials(self, write: bool = False):
        from google.auth.exceptions import RefreshError
        from google.auth.transport.requests import Request

        creds = self._load()
        if creds is None:
            raise AuthorizationRequired("No YouTube account is authorised yet.")
        if write and SCOPE_WRITE not in set(creds.scopes or []):
            raise WriteScopeRequired("The stored authorisation is read-only.")
        if not creds.valid:
            if not creds.refresh_token:
                raise InvalidGrant("The stored authorisation has expired.")
            try:
                creds.refresh(Request())
            except RefreshError as exc:
                raise InvalidGrant("The stored authorisation was revoked or has expired.") from exc
            self.store.save(creds.to_json())
        return creds

    def revoke(self) -> None:
        raw = self.store.load()
        if raw:
            info = json.loads(raw)
            token = info.get("refresh_token") or info.get("token")
            if token:
                data = urllib.parse.urlencode({"token": token}).encode()
                req = urllib.request.Request(
                    REVOKE_URL, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                try:
                    urllib.request.urlopen(req, timeout=10).close()  # noqa: S310 - fixed https URL
                except Exception:  # noqa: BLE001 - local deletion still happens
                    pass
        self.store.delete()
        if self.on_revoke:
            self.on_revoke()


class StaticAuthorizer:
    """Offline authorizer for the fixture provider, tests and ``local-check``.

    ``granted`` are the scopes already held. ``allow_write_upgrade`` simulates the user approving the
    incremental write-scope consent screen.
    """

    def __init__(
        self,
        granted: list[str] | None = None,
        *,
        allow_write_upgrade: bool = True,
        error: YTIntelError | None = None,
    ) -> None:
        self.granted = list(granted if granted is not None else [SCOPE_READ])
        self.allow_write_upgrade = allow_write_upgrade
        self.error = error
        self.requested_scopes: list[list[str]] = []
        self.credential_requests: list[bool] = []
        self.revoked = False

    def credentials(self, write: bool = False) -> Any:
        self.credential_requests.append(write)
        if self.error is not None:
            raise self.error
        if not self.granted:
            raise AuthorizationRequired("No YouTube account is authorised yet.")
        if write and SCOPE_WRITE not in self.granted:
            raise WriteScopeRequired("The stored authorisation is read-only.")
        return {"fake": True, "scopes": list(self.granted)}

    def has_scope(self, write: bool = False) -> bool:
        if write:
            return SCOPE_WRITE in self.granted
        return bool(set(self.granted) & {SCOPE_READ, SCOPE_WRITE})

    def granted_scopes(self) -> list[str]:
        return list(self.granted)

    def authorize(self, write: bool = False) -> list[str]:
        scopes = scopes_for(write)
        self.requested_scopes.append(scopes)
        if write and not self.allow_write_upgrade:
            raise WriteScopeRequired("The user did not grant the playlist-creation permission.")
        for scope in scopes:
            if scope not in self.granted:
                self.granted.append(scope)
        return list(self.granted)

    def revoke(self) -> None:
        self.granted = []
        self.revoked = True
