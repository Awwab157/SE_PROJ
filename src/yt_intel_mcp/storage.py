"""SQLite state file (cache, quota ledger, reservations, proposals) stored outside the repo."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from yt_intel_mcp.config import repo_root

STATE_DIR_ENV = "YT_INTEL_STATE_DIR"

SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (
    key TEXT PRIMARY KEY,
    method TEXT NOT NULL,
    value TEXT NOT NULL,
    fetched_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS cache_method ON cache(method);

CREATE TABLE IF NOT EXISTS quota_ledger (
    day TEXT NOT NULL,
    bucket TEXT NOT NULL,
    consumed INTEGER NOT NULL DEFAULT 0,
    reserved INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, bucket)
);

CREATE TABLE IF NOT EXISTS reservations (
    id TEXT PRIMARY KEY,
    day TEXT NOT NULL,
    label TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    remaining TEXT NOT NULL,
    consumed TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quota_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    reservation_id TEXT NOT NULL,
    api_method TEXT NOT NULL,
    cost TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    payload TEXT NOT NULL,
    playlist_id TEXT,
    inserted TEXT NOT NULL DEFAULT '[]',
    failed TEXT NOT NULL DEFAULT '{}',
    code_hash TEXT,
    code_salt TEXT,
    code_attempts INTEGER NOT NULL DEFAULT 0,
    lease_until TEXT,
    quota_used TEXT NOT NULL DEFAULT '{}',
    result TEXT
);
"""


def default_state_dir() -> Path:
    override = os.environ.get(STATE_DIR_ENV)
    return Path(override).expanduser() if override else Path.home() / ".yt-intel-mcp"


def ensure_outside_repo(path: Path) -> None:
    """Refuse to keep state (tokens, account data) inside the source repository."""
    root = repo_root()
    if not (root / "pyproject.toml").exists():
        return
    resolved = path.resolve()
    if resolved == root or root in resolved.parents:
        raise ValueError("State directory must be outside the repository (NFR-10).")


def prepare_state_dir(path: Path) -> Path:
    ensure_outside_repo(path)
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:  # pragma: no cover - best effort on Windows
        pass
    return path


class Database:
    """Opens a short-lived connection per operation so it is safe across worker threads."""

    def __init__(self, path: Path) -> None:
        self.path = path
        conn = self.connect()
        try:
            conn.executescript(SCHEMA)
        finally:
            conn.close()  # sqlite3's context manager commits but does not close
        try:
            os.chmod(path, 0o600)
        except OSError:  # pragma: no cover
            pass

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 30000")
        return conn

    @contextmanager
    def transaction(self, immediate: bool = True) -> Iterator[sqlite3.Connection]:
        """``BEGIN IMMEDIATE`` takes the write lock up front, which makes reservations atomic."""
        conn = self.connect()
        try:
            conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")
        finally:
            conn.close()

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        conn = self.connect()
        try:
            yield conn
        finally:
            conn.close()
