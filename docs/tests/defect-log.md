# Defect log (TQ-8)

Every significant defect gets an entry and a regression test.

| ID | Date | Found by | Severity | Description | Root cause | Fix | Regression test |
|---|---|---|---|---|---|---|---|
| D-001 | 2026-11-26 | `scripts/benchmark.py` on Windows | Medium | State database file stayed locked after the server objects were discarded (`PermissionError` when deleting the temp dir). | `Database.__init__` used `with sqlite3.connect(...)`, which commits but does not close the connection. | Explicit `close()` after creating the schema (`storage.py`). | `tests/unit/test_storage.py::test_database_releases_file_handles` |
| D-002 | 2026-11-26 | `tests/unit/test_quota.py` | Medium | After YouTube reported `quotaExceeded`, quota became available again once the active reservation was released. | `mark_exhausted` set consumed to `limit - reserved`, so releasing the reservation re-opened that amount. | Mark the full daily limit as consumed (`quota.py`). | `tests/unit/test_quota.py::test_mark_exhausted` |
