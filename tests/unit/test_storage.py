"""Regression test for D-001 (docs/tests/defect-log.md): the state file must not stay locked."""

import os

import pytest

from yt_intel_mcp.config import repo_root
from yt_intel_mcp.storage import Database, prepare_state_dir


def test_database_releases_file_handles(tmp_path) -> None:
    path = tmp_path / "state.db"
    db = Database(path)
    with db.transaction() as conn:
        conn.execute("INSERT INTO cache(key, method, value, fetched_at) VALUES ('k', 'm', '1', 0)")
    with db.read() as conn:
        assert conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0] == 1
    os.remove(path)  # fails on Windows if any connection were left open
    assert not path.exists()


def test_state_dir_inside_repo_is_refused() -> None:
    with pytest.raises(ValueError):
        prepare_state_dir(repo_root() / "state-in-repo")
