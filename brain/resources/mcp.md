---
title: Model Context Protocol (MCP)
type: research
status: distilled
created: 2026-11-26
tags: [mcp, protocol, research]
---
# Model Context Protocol (MCP)

## Summary
MCP is the JSON-RPC protocol between AI clients and servers that expose tools, resources and prompts. This project is an MCP server over **stdio only** (TBD-1).

## Key points
- Transports: stdio (chosen), Streamable HTTP. With stdio, stdout carries protocol messages — logs must go to stderr.
- Client capabilities are negotiated at initialisation; **elicitation** lets the server ask the user for structured input through the client UI (accept / decline / cancel).
- Official Python SDK: in v2 the high-level `FastMCP` class is named `MCPServer` (`mcp.server.mcpserver`); the installed version is 2.3. Tools can return `Annotated[CallToolResult, Model]` to publish an output schema and still return `isError` results.
- In-process testing: `mcp.Client(server, mode="legacy")` gives a real client session without a subprocess.

## Sources
- https://modelcontextprotocol.io/specification/2025-06-18
- https://modelcontextprotocol.io/specification/2025-06-18/client/elicitation
- https://github.com/modelcontextprotocol/python-sdk

## Requirements
- FR-8, TBD-1, TBD-5, FR-5.6

## Links
- [[mcp-servers-tools-and-resources]] · [[agent-skills-format]] · [[playlist-creation]]
