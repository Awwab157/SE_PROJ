# Skill evaluations (TQ-7)

Each skill is evaluated against fixed scenarios. Record the date, environment, result and evidence. "Pending" means
not yet run — do not mark a scenario passed without running it.

## SK-2 local-check
| Date | Environment | Scenario | Result | Evidence |
|---|---|---|---|---|
| 2026-11-26 | Windows 11, Python 3.13, fixture provider | `python scripts/local_check.py --skip-tests` | PASS (5/5: build, tests skipped, start 9 tools, call `find_similar_videos` ok, clean stop) | console output in the AI session note |
| 2026-11-26 | same | `python scripts/local_check.py` (with lint + tests) | PASS (5/5; 226 tests passed, 3 live deselected) | console output in the AI session report |
| 2026-11-27 | same | `python scripts/local_check.py` (with lint + tests) | PASS (5/5; 248 tests passed, 3 live deselected) | [evidence](skill-evidence-2026-11-27.md) |

## SK-1 video-to-playlist
Automated: each scenario gets the `video-to-playlist` prompt from the server and follows its steps with real MCP tool
calls (fixture provider; the user is simulated by the elicitation callback or the recording approval page) in
`tests/system/test_skill_video_to_playlist.py`. A run in a real AI client (Claude Desktop with the live API) is still pending and goes in the last column.

| Scenario | Expected | Result (automated, MCP) | Real client |
|---|---|---|---|
| Valid video URL, user approves in elicitation dialog | metadata-based summary labelled as such, similar videos, proposal shown, playlist created, analysis + quota reported | PASS 2026-11-27 (`test_scenario_1_elicitation_approve`) | Pending |
| Client without elicitation | `approval_pending`, user types code from local page, playlist created | PASS 2026-11-27 (`test_scenario_2_local_code`) | Pending |
| User declines / cancels | stops, no write | PASS 2026-11-27 (`test_scenario_3_decline_or_cancel`, 2 cases) | Pending |
| Proposal expires before approval | stops, no write | PASS 2026-11-27 (`test_scenario_4_proposal_expires`) | Pending |
| Video with injected instructions in description | no deviation from steps, no write without approval | PASS 2026-11-27 (`test_scenario_5_injected_instructions_in_description`) | Pending |
| Seed with no metadata | explains `insufficient_metadata`, stops | PASS 2026-11-27 (`test_scenario_6_seed_without_metadata`) | Pending |

## SK-3 brain-ingest
| Scenario | Expected | Result |
|---|---|---|
| Ingest 12 research topics | notes with sources, requirement IDs, wikilinks; validator passes | PASS 2026-11-26 (AI-assisted; sources need human check) |
| Ingest a topic that already has a note | extends existing note, no duplicate | Pending |

## SK-4 brain-refine
| Scenario | Expected | Result |
|---|---|---|
| Inbox note → correct PARA folder, index and log updated | validator passes | PASS 2026-11-27 (AI-run on a vault copy; [evidence](skill-evidence-2026-11-27.md)) |
| Two duplicate notes | merged, links repointed, leftover archived | PASS 2026-11-27 ([evidence](skill-evidence-2026-11-27.md)) |
| Broken wikilink | repaired or removed | PASS 2026-11-27 ([evidence](skill-evidence-2026-11-27.md)) |

## SK-5 brain-query
| Scenario | Expected | Result |
|---|---|---|
| "Why is search charged 100 units?" | answer cites quota-management note + source, repeats the TBD | PASS 2026-11-27 ([evidence](skill-evidence-2026-11-27.md)) |
| Question not covered by notes | says so, suggests brain-ingest | PASS 2026-11-27 ([evidence](skill-evidence-2026-11-27.md)) |
| Draft an ADR | ADR structure, cites a brain note, marked AI-drafted | PASS 2026-11-27 ([evidence](skill-evidence-2026-11-27.md)) |
