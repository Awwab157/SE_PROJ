---
title: MCP Servers, Tools and Resources
type: research
status: distilled
created: 2026-11-26
tags: [mcp, design, research]
---
# MCP Servers, Tools and Resources

## Summary
How the server's surface is shaped: nine tools with JSON Schemas generated from pydantic models, three read-only resources, structured results and structured errors (FR-8, UI-1, UI-3).

## Key points
- Tools: `find_similar_videos`, `find_similar_channels`, `recommend_videos`, `analyze_engagement`, `propose_playlist`, `create_playlist`, `start_authorization`, `revoke_authorization`, `clear_cache` (TBD-4).
- Each description states inputs, effect and **whether it writes to YouTube** (NFR-19); only `create_playlist` does. Tool annotations (`readOnlyHint` etc.) are hints, not security.
- Results: `structuredContent` + a short human summary + the JSON as text for clients that ignore structured output (UI-1).
- Errors: `isError: true` with `{code, cause, next_step}`; never tokens or stack traces (UI-3).
- Resources: `quota://status`, `config://server`, `proposal://{id}` — read-only, no secrets, no confirmation codes.
- SKILL.md files are not registered as tools or resources (FR-8.5), see [[agent-skills-format]]. Prompts are the third MCP primitive: user-selected templates; `video-to-playlist` is served as one (SK-1.1).

## Sources
- https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- https://modelcontextprotocol.io/specification/2025-06-18/server/resources

## Requirements
- FR-8, FR-8.3, FR-8.5, NFR-19, UI-1, UI-3, TBD-4

## Links
- [[mcp]] · [[api-security-and-error-handling]]
