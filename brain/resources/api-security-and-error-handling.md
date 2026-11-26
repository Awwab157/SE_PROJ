---
title: API Security and Error Handling
type: research
status: distilled
created: 2026-11-26
tags: [security, errors, research]
---
# API Security and Error Handling

## Summary
Security controls for an AI-driven server: least privilege, secret hygiene, prompt-injection resistance, safe errors and retry discipline.

## Key points
- All external text (titles, descriptions, tags, channel names) is untrusted data and is never interpreted as instructions (FR-5.10). The write path needs out-of-band human approval, so injected text cannot cause a write.
- Secrets: no tokens or client secrets in the repo, fixtures, logs or prompts; gitleaks runs in CI; state lives outside the repo (NFR-10).
- Logs: tool name + duration + outcome only; titles, channel names, queries, emails, tokens and account IDs are dropped or redacted (FR-4.6, NFR-1).
- Errors carry code, cause and next step and never include stack traces or library messages (UI-3).
- Retries: reads only, 429/5xx only, max 3, bounded exponential backoff; never `quotaExceeded`, never writes (NFR-15).
- Isolation: only `providers/live.py` imports the Google client library (NFR-13); the provider interface has no delete/update methods (NFR-5).

## Sources
- https://owasp.org/API-Security/editions/2023/en/0x11-t10/
- https://genai.owasp.org/llmrisk/llm01-prompt-injection/
- https://developers.google.com/youtube/v3/docs/errors
- https://github.com/gitleaks/gitleaks

## Requirements
- NFR-1, NFR-5, NFR-10, NFR-13, NFR-15, FR-4.6, FR-5.10, UI-3

## Links
- [[oauth-2-0]] · [[quota-management]] · [[playlist-creation]] · [[mcp-servers-tools-and-resources]]
