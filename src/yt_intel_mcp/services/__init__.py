"""Application services (FR-1..FR-5). Services are synchronous; the MCP layer runs them in a worker
thread. Every service reserves quota *before* its first provider call via :func:`run_metered`."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, TypeVar

from yt_intel_mcp import quota
from yt_intel_mcp.cache import Cache
from yt_intel_mcp.clock import Clock
from yt_intel_mcp.providers.base import YouTubeProvider
from yt_intel_mcp.quota import QuotaManager
from yt_intel_mcp.storage import Database

T = TypeVar("T")


@dataclass
class AppContext:
    provider: YouTubeProvider  # cache-wrapped provider used by services
    raw_provider: YouTubeProvider
    db: Database
    cache: Cache
    quota: QuotaManager
    clock: Clock
    authorizer: Any
    similarity: dict[str, Any]
    approval_prompt: Any = None
    provider_mode: str = "live"
    extras: dict[str, Any] = field(default_factory=dict)

    def retrieval(self, name: str) -> dict[str, Any]:
        return dict(self.similarity.get("retrieval", {}).get(name, {}))


def run_metered(
    app: AppContext,
    label: str,
    plan: Mapping[str, int],
    fn: Callable[[], T],
    *,
    min_plan: Mapping[str, int] | None = None,
) -> tuple[T, dict[str, int]]:
    """Reserve quota, run ``fn`` with the reservation active, then release what was not used."""
    reservation = app.quota.reserve(plan, min_plan=min_plan, label=label)
    try:
        with quota.active(reservation):
            result = fn()
    finally:
        used = reservation.release_unused()
    return result, {k: v for k, v in used.items() if v}


def with_quota(result: Any, used: dict[str, int]) -> Any:
    result.quota_used = used
    return result
