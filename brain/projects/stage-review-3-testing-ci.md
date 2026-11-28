---
title: Stage review 3 — testing and CI
type: stage-review
status: pending-human-review
created: 2026-11-27
---
# Stage review 3 — testing and CI

## Summary
| Deliverable | State | Where |
|---|---|---|
| Continuous testing and CI plan | done | `docs/tests/test-plan.md` |
| Results | local CI-equivalent run on 2026-11-27: 257 passed, 0 failed, coverage 90.87 % (gate 85 %), lint and validators clean, local-check 5/5; remote CI and live runs still to record | `docs/tests/test-results.md` |
| Product skill video-to-playlist with test results | 6 scenarios (7 tests) automated through MCP: all PASS; a real-client run is pending | `tests/system/test_skill_video_to_playlist.py`, `docs/tests/skill-evaluations.md` |
| Defect log with regression tests | 4 defects (D-001 to D-004), each with a passing regression test; `tests/unit/test_defect_log.py` enforces it | `docs/tests/defect-log.md` |
| Review note per stage | done | [[stage-review-1-requirements]], [[stage-review-2-design]], this note |

CI now has a coverage gate and keeps JUnit and coverage reports as artifacts; the live workflow keeps its JUnit report too.

## Decisions
- CI tests use only the fixture provider; the live API runs weekly in `live-api.yml` with a budget of 6 searches and 800 units (TQ-5).
- Coverage gate 85 % on `yt_intel_mcp`; modules that need the network, a browser or a keychain (`providers/live.py`, `approval.py`, `auth.py`) are covered by fake services and the live job instead.
- Defect rows must name an existing regression test (checked in CI).

## What worked
- The fixture provider with call recording made every TQ-4 negative case and the "zero API calls when over budget" check (TQ-6) deterministic.
- Driving the video-to-playlist scenarios through the MCP prompt and tools tests the skill the way a client uses it.
- A test that reads the defect log keeps TQ-8 honest: a defect without an existing regression test fails CI.

## What did not work
- Remote CI results and the live-API workflow could not be verified from the development session; they are still unrecorded.
- Commits carried an AI co-author trailer that listed the assistant as a GitHub contributor; history had to be rewritten and force-pushed.
- Review notes were first organised by build phase, not by stage, and had to be renamed.

## What to change
- Record every remote CI run and the weekly live run in `docs/tests/test-results.md`.
- No AI attribution trailers in commits; the PR template states which parts are AI-generated instead.
- Write the stage review note as the last task of each stage.

## Open items
- Record the first green `ci.yml` run on GitHub (Actions tab) in `docs/tests/test-results.md`.
- Configure the `live-api` environment secrets and record the first live run.
- Run video-to-playlist in a real client (Claude Desktop, live API) and fill the "Real client" column.
- Set NFR-2 targets (TBD-3) from the benchmark.

## Links
- [[stage-review-2-design]] · [[quota-management]] · [[api-security-and-error-handling]] · [[playlist-creation]]
