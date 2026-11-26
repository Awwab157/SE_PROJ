"""Helpers for in-process MCP client sessions (TQ-3)."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

import mcp.types as types
from mcp import Client

from yt_intel_mcp.server import create_server

ElicitFn = Callable[[Any, Any], Awaitable[types.ElicitResult]]


def client_for(app, elicitation: ElicitFn | None = None) -> Client:
    kwargs: dict[str, Any] = {}
    if elicitation is not None:
        kwargs["elicitation_callback"] = elicitation
    return Client(create_server(app), mode="legacy", **kwargs)


def accept(record: list[str] | None = None, approve: bool = True) -> ElicitFn:
    async def cb(ctx, params):
        if record is not None:
            record.append(params.message)
        return types.ElicitResult(action="accept", content={"approve": approve})

    return cb


def respond(action: str) -> ElicitFn:
    async def cb(ctx, params):
        return types.ElicitResult(action=action)

    return cb


def all_text(result) -> str:
    """Everything a client (and therefore the model) could see from a tool result."""
    parts = [c.text for c in result.content if getattr(c, "text", None)]
    if result.structured_content is not None:
        parts.append(json.dumps(result.structured_content))
    return "\n".join(parts)
