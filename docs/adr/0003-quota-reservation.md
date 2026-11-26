# ADR 0003 — Quota: per-bucket ledger with atomic reservation

- Status: accepted (pending human review)
- Date: 2026-11-26

## Context
The YouTube quota is small and shared by the team's single project; running out mid-workflow (especially between
`playlists.insert` and its items) is worse than refusing up front. Background:
[Quota Management](../../brain/resources/quota-management.md).

## Decision
- Two configurable buckets in `config/quota.yaml`: `search_calls` (100/day) and `units` (10,000/day), reset at midnight
  America/Los_Angeles.
- Services compute a plan (max calls per API method) and call `reserve()` before any request. Reservation runs in a
  SQLite `BEGIN IMMEDIATE` transaction across all buckets, so concurrent workflows cannot overspend.
- Reads use *bounded* reservations (a minimum plan must fit; optional calls stop when the reservation is used).
  Playlist creation reserves `50 + 50 × items` all-or-nothing.
- Providers `charge()` before every HTTP attempt; charges count even if the request fails. Retries of reads may top up
  from the free budget. `release_unused()` returns the rest.
- `search.list` is charged 1 search call **and** 100 units (the documented legacy unit cost) — conservative.
  **TBD:** confirm against the project's quota page and lower the unit cost if the separate search bucket replaces it.

## Consequences
- Over-budget requests fail with estimated cost, limit and remaining quota and zero API calls.
- The ledger is local: usage by other tools on the same Google project is not visible; a `quotaExceeded` response marks
  the day as exhausted locally.
