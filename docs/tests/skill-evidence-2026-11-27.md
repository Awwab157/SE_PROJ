# Skill evaluation evidence — 2026-11-27 (Stage 2)

AI-run (Claude Code) on Windows 11, Python 3.13. Needs human check before the results count as accepted (AGENTS.md).

## SK-4 brain-refine

Run on a **copy** of `brain/` (outside the repository) so the team vault was not changed. Three problems were seeded:
a research note in `inbox/`, a duplicate of `quota-management` (`resources/quota-costs.md`, same costs and source),
and a broken wikilink `search-quota-costs` in the inbox note.

| Step (SKILL.md) | What happened |
|---|---|
| 1 Baseline | `validate_brain.py <copy>`: **FAILED (1 error)**, broken wikilink `search-quota-costs`. The duplicate is not a validator error and had to be found by step 3. |
| 2 PARA moves | `inbox/youtube-search-filters.md` is reference material, so it moved to `resources/` (file name unchanged). |
| 3 Duplicates | `resources/quota-costs.md` repeated a key point and the source already in `quota-management`; nothing new to merge. Marked `status: archived`, added "Merged into `[[quota-management]]`", moved to `archive/`. No note linked to it. |
| 4 Broken links | `search-quota-costs` was repointed to `[[quota-management]]`. |
| 6 Index and log | `index.md` lists `[[youtube-search-filters]]`; dated line appended to `log.md`. First attempt wrote the dead link as a wikilink inside the log line, and the validator flagged it. It was rewritten as code, so the step also showed the validator catches mistakes made during refinement. |
| 7 Validate | `validate_brain.py <copy>`: **OK (0 errors)**; `validate_skills.py`: **OK (0 errors)**. |

## SK-5 brain-query

**Q1: "Why is search charged 100 units?"**
> `search.list` is charged in both quota buckets: one search call and 100 units, "the conservative choice", because
> 100 is the documented legacy unit cost (`[[quota-management]]`, source:
> https://developers.google.com/youtube/v3/determine_quota_cost). The note marks this **TBD: confirm on the project's
> quota page**. If the separate search bucket replaces the unit cost, the value should be lowered.

Result: cites the note and its source, repeats the TBD, and adds nothing beyond the note. **PASS**

**Q2: "What do YouTube's policies say about caching video thumbnails?"**
> The brain does not cover thumbnails (no note mentions them). `[[youtube-api-compliance]]` only says cached account
> data is served for at most 24 h and purged after 7 days. Suggestion: run `brain-ingest` on the YouTube API Services
> Developer Policies (https://developers.google.com/youtube/terms/developer-policies) before answering.

Result: says the notes do not answer the question and suggests `brain-ingest` with a named source, without answering from memory. **PASS**

**Q3: "Draft an ADR for the response cache."**

> *AI-drafted — needs human review.*
>
> **ADR 0006 — Response cache: serve 24 h, purge after 7 days**
>
> **Context.** Quota is a hard daily limit, and cache hits cost nothing (`[[quota-management]]`). Cached account data
> must expire and be deletable on request (`[[youtube-api-compliance]]`).
>
> **Decision.** Serve cached read responses up to 24 h old, refetch after that, purge entries after 7 days. Never cache
> writes. `clear_cache` and `revoke_authorization` delete all cached account data.
>
> **Consequences.** Repeated questions cost no quota within a day; data can be up to 24 h stale; nothing cached
> outlives 7 days.
>
> **References.** `[[quota-management]]` (https://developers.google.com/youtube/v3/getting-started#quota),
> `[[youtube-api-compliance]]`.

Result: uses the ADR structure (Context, Decision, Consequences, References), cites brain notes and is marked AI-drafted.
Not added to `docs/adr/`: the team decides whether to adopt it (the policy is already described in
`docs/architecture.md` and the `quota-management` note). **PASS**

## SK-2 local-check

`python scripts/local_check.py`:
```
[PASS] 1 build: package installed
[PASS] 2 tests: 248 passed, 3 deselected in 76.23s (0:01:16)
[PASS] 3 start: 9 tools registered
[PASS] 4 call: Found 3 videos similar to the seed video (from 22 candidates). Top match: "Merging and Joining DataFrames in Pandas" (score 0.50).
[PASS] 5 stop: server exited cleanly
local-check: ALL 5 STEPS PASSED
```
