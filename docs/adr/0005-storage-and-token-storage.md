# ADR 0005 — Storage: one SQLite file outside the repo; tokens in the OS keychain

- Status: accepted (pending human review)
- Date: 2026-11-26

## Context
The server needs a cache, a quota ledger and proposal state that survive restarts, plus OAuth tokens that must never
enter the repository, fixtures or logs. Background: [OAuth 2.0](../../brain/resources/oauth-2-0.md),
[API Security and Error Handling](../../brain/resources/api-security-and-error-handling.md).

## Decision
- One SQLite database `state.db` in `~/.yt-intel-mcp/` (override `YT_INTEL_STATE_DIR`). The server refuses a state
  directory inside the repository. Directory mode 0700, file mode 0600 where the OS supports it.
- Short-lived connection per operation (thread-safe with worker threads); `BEGIN IMMEDIATE` for atomic updates.
- Tokens in the OS keychain via `keyring`. If no secure backend exists, an encrypted file (Fernet) with mode 0600 in the
  state directory.
- `revoke_authorization` revokes the token at Google, deletes the stored token and clears cached account data;
  `clear_cache` clears cached data.

## Consequences
- No server process or migration tool is needed; the schema is created on start.
- The encrypted-file fallback keeps its key next to the data, so it protects against accidental disclosure (e.g. copying
  the repo), not against an attacker with the user's account — acceptable for a single-user desktop tool (BR-1).
