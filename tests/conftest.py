"""Shared test fixtures. All CI tests use the fixture provider and never touch the network."""

from __future__ import annotations

import json
import socket
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from yt_intel_mcp.approval import RecordingApprovalPrompt
from yt_intel_mcp.auth import SCOPE_READ, StaticAuthorizer
from yt_intel_mcp.clock import FakeClock
from yt_intel_mcp.providers.fixture import FixtureProvider, load_fixture_data
from yt_intel_mcp.server import build_app
from yt_intel_mcp.services import AppContext

FIXTURES = Path(__file__).parent / "fixtures"
CH: dict[str, str] = json.loads((FIXTURES / "channel_ids.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _no_network(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    """CI tests must not open network connections (loopback is allowed)."""
    if request.node.get_closest_marker("live"):
        return
    real_connect = socket.socket.connect

    def guarded(self: socket.socket, address: Any) -> Any:
        host = address[0] if isinstance(address, tuple) else address
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise RuntimeError(f"Network access attempted in an offline test: {host}")
        return real_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(datetime(2026, 3, 10, 20, 0, tzinfo=UTC))


@pytest.fixture
def authorizer() -> StaticAuthorizer:
    return StaticAuthorizer([SCOPE_READ])


@pytest.fixture
def fixture_data() -> dict[str, Any]:
    return load_fixture_data(FIXTURES)


@pytest.fixture
def provider(fixture_data: dict[str, Any], authorizer: StaticAuthorizer) -> FixtureProvider:
    return FixtureProvider(fixture_data, authorizer=authorizer)


@pytest.fixture
def prompt() -> RecordingApprovalPrompt:
    return RecordingApprovalPrompt()


def make_app(tmp_path: Path, provider: Any, authorizer: Any, prompt: Any, clock: FakeClock) -> AppContext:
    return build_app(
        state_dir=tmp_path / "state",
        raw_provider=provider,
        authorizer=authorizer,
        approval_prompt=prompt,
        clock=clock,
        provider_mode="fixture",
    )


@pytest.fixture
def app(tmp_path: Path, provider, authorizer, prompt, clock) -> AppContext:
    return make_app(tmp_path, provider, authorizer, prompt, clock)


def consume(app: AppContext, **buckets: int) -> None:
    """Pre-consume quota in the ledger (simulates earlier usage today)."""
    day = app.quota.day_key()
    with app.db.transaction() as conn:
        for bucket, n in buckets.items():
            app.quota._bump(conn, day, bucket, consumed=n)
