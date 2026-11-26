# ADR 0002 — Playlist confirmation: elicitation, else local one-time code, else fail closed

- Status: accepted (pending human review)
- Date: 2026-11-26
- Closes: TBD-5

## Context
`create_playlist` is the only write. A model can be manipulated (e.g. by text inside video descriptions) or can
simply assert that the user agreed. Approval must come from the human, through a channel the model cannot forge.
Background: [Playlist Creation](../../brain/resources/playlist-creation.md),
[API Security and Error Handling](../../brain/resources/api-security-and-error-handling.md).

## Decision
1. If the client advertises MCP **elicitation**, the server sends the exact proposal summary and requires
   `accept` with `approve: true`. `decline` marks the proposal DECLINED; `cancel` and timeout write nothing.
2. Otherwise, if a local browser is available, the server generates a single-use code with `secrets` (8 chars from a
   32-symbol alphabet), stores only a salted PBKDF2 hash bound to the proposal, and shows code + summary on a page served
   on `127.0.0.1` under a random path. The user types the code back. Three wrong attempts invalidate the code.
3. Otherwise **fail closed** (`approval_unavailable`).
- Bare `confirmation=true`, free text or a wrong/reused code never writes. No tool, resource, log or error contains the code.

## Consequences
- Works in clients without elicitation, at the cost of a browser round-trip.
- Headless/remote setups cannot create playlists unless the client supports elicitation — accepted as the safe default.
- Tests act as the human through a recording prompt and grep every output for the code.
