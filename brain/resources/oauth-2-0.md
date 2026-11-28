---
title: OAuth 2.0
type: research
status: distilled
created: 2026-11-26
tags: [oauth, security, research]
---
# OAuth 2.0

## Summary
Installed-app (desktop) OAuth with a loopback redirect, `state` and PKCE, opened in the system browser (FR-7, UI-4).

## Key points
- Redirect to `http://127.0.0.1:<random port>/`; the app runs a one-shot local server to receive the code (RFC 8252).
- PKCE (`code_challenge_method=S256`, RFC 7636) and a random `state` per flow protect the code exchange and against CSRF.
- Least privilege: read features request only `youtube.readonly`. The `youtube` scope is requested **only when a playlist is created** (incremental authorisation, `include_granted_scopes=true`).
- Apps in Google "Testing" publishing status get refresh tokens that expire after 7 days → `invalid_grant` → tell the user to call `start_authorization` again.
- Tokens are kept in the OS keychain (`keyring`); fallback is an encrypted file with mode 0600 outside the repo (NFR-10).
- Revocation: `POST https://oauth2.googleapis.com/revoke`, then delete the stored token and cached account data (NFR-11).

## Sources
- https://developers.google.com/identity/protocols/oauth2/native-app
- https://developers.google.com/youtube/v3/guides/auth/installed-apps
- https://developers.google.com/identity/protocols/oauth2#expiration
- https://datatracker.ietf.org/doc/html/rfc7636
- https://datatracker.ietf.org/doc/html/rfc8252

## Requirements
- FR-7, UI-4, NFR-10, NFR-11, BR-1

## Links
- [[api-security-and-error-handling]] · [[playlist-creation]] · [[youtube-data-api-v3]]
