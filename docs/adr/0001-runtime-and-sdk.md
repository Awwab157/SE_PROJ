# ADR 0001 — Runtime: Python 3.11+ with the official MCP SDK, stdio only

- Status: accepted (pending human review)
- Date: 2026-11-26
- Closes: TBD-1

## Context
The server must run locally next to a desktop MCP client, talk to the YouTube Data API through Google's client
libraries, and compute text similarity. Background: [MCP](../../brain/resources/mcp.md),
[YouTube Data API v3](../../brain/resources/youtube-data-api-v3.md).

## Decision
- Python 3.11+ (Google's `google-api-python-client`, `google-auth-oauthlib` and `scikit-learn` are first-class there).
- Official `mcp` Python SDK, high-level server API. In SDK v2 (installed: 2.3) `FastMCP` was renamed `MCPServer`
  (`mcp.server.mcpserver`); we pin `mcp>=2.3,<3`.
- **stdio transport only.** No HTTP transport, no UI.
- Tools return `Annotated[CallToolResult, OutputModel]` so the output schema is published from pydantic and errors can
  still be returned as `isError` results with structured content.

## Consequences
- Logs must go to stderr (stdout is the transport).
- In-process tests use `mcp.Client(server, mode="legacy")`, which supports elicitation; the default "auto" mode in-process
  has no back-channel for server-initiated requests.
- A future SDK v3 may need migration work; the pin makes that explicit.
