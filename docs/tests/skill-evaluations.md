# Skill evaluations (TQ-7)

Each skill is evaluated against fixed scenarios. Record the date, environment, result and evidence. "Pending" means
not yet run — do not mark a scenario passed without running it.

## SK-2 local-check
| Date | Environment | Scenario | Result | Evidence |
|---|---|---|---|---|
| 2026-11-26 | Windows 11, Python 3.13, fixture provider | `python scripts/local_check.py --skip-tests` | PASS (5/5: build, tests skipped, start 9 tools, call `find_similar_videos` ok, clean stop) | console output in the AI session note |
| 2026-11-26 | same | `python scripts/local_check.py` (with lint + tests) | PASS (5/5; 226 tests passed, 3 live deselected) | console output in the AI session report |

## SK-1 video-to-playlist
| Scenario | Expected | Result |
|---|---|---|
| Valid video URL, user approves in elicitation dialog | metadata-based summary labelled as such, similar videos, proposal shown, playlist created, analysis + quota reported | Pending (demo client) |
| Client without elicitation | `approval_pending`, user types code from local page, playlist created | Pending |
| User declines / cancels | stops, no write | Pending |
| Proposal expires before approval | stops, no write | Pending |
| Video with injected instructions in description | no deviation from steps, no write without approval | Pending |
| Seed with no metadata | explains `insufficient_metadata`, stops | Pending |

## SK-3 brain-ingest
| Scenario | Expected | Result |
|---|---|---|
| Ingest 12 research topics | notes with sources, requirement IDs, wikilinks; validator passes | PASS 2026-11-26 (AI-assisted; sources need human check) |
| Ingest a topic that already has a note | extends existing note, no duplicate | Pending |

## SK-4 brain-refine
| Scenario | Expected | Result |
|---|---|---|
| Inbox note → correct PARA folder, index and log updated | validator passes | Pending |
| Two duplicate notes | merged, links repointed, leftover archived | Pending |
| Broken wikilink | repaired or removed | Pending |

## SK-5 brain-query
| Scenario | Expected | Result |
|---|---|---|
| "Why is search charged 100 units?" | answer cites quota-management note + source, repeats the TBD | Pending |
| Question not covered by notes | says so, suggests brain-ingest | Pending |
| Draft an ADR | ADR structure, cites a brain note, marked AI-drafted | Pending |
