# Test and CI results (Stage 3)

Plan: [test-plan.md](test-plan.md). Newest run first. Remote CI runs are on the repository's **Actions** tab, and each run
keeps `test-results.xml` and `coverage.xml` as artifacts.

## 2026-11-27: full offline run (CI-equivalent, local)
Environment: Windows 11, Python 3.13.15, fixture provider, no network. Commands are the same as in `ci.yml`.

| Check | Command | Result |
|---|---|---|
| Lint | `ruff check src tests scripts` | **PASS**, no findings |
| Offline tests + coverage | `pytest -q --cov=yt_intel_mcp --cov-fail-under=85 --junitxml=...` | **PASS**: 257 passed, 0 failed, 3 live deselected (83.8 s) |
| Coverage gate | `--cov-fail-under=85` | **PASS**: 90.87 % lines (2,836 statements, 259 missed) |
| Skill validator | `python scripts/validate_skills.py` | **PASS**, 0 errors |
| Brain validator | `python scripts/validate_brain.py` | **PASS**, 0 errors |
| local-check skill | `python scripts/local_check.py` | **PASS**, 5/5 steps |
| Secret scan | gitleaks | runs in CI only (not installed locally) |

### Tests per level
| Level | Tests | Failed |
|---|---|---|
| Unit (TQ-1) | 151 | 0 |
| Integration (TQ-2) | 34 | 0 |
| System, FR-1 to FR-5 and skill scenarios (TQ-3, TQ-7) | 17 | 0 |
| Negative (TQ-4) | 33 | 0 |
| Security | 22 | 0 |
| **Total** | **257** | **0** |
| Live (TQ-5, scheduled only) | 3 | not run locally |

### Requirement coverage by tests
| Requirement | Evidence |
|---|---|
| FR-1 to FR-5 end to end via MCP | `tests/system/test_mcp_end_to_end.py` (`test_fr1_to_fr4_*`, `test_fr5_*`) |
| TQ-4 negative cases | invalid/malformed IDs, private, deleted (`test_errors_are_structured`); missing tags (`test_missing_seed_fields_reported_unavailable`); `quotaExceeded` (`test_quota_exceeded_is_not_retried`); `youtubeSignupRequired` (`test_youtube_signup_required`); expired tokens (`test_invalid_grant_requires_reauthorisation`, `test_refresh_error_maps_to_invalid_grant`); rate limiting (`test_rate_limit_*`) |
| TQ-6 rejected before any API call | `test_over_budget_rejected_with_zero_provider_calls`, `test_quota_budget_error_via_mcp` |
| Prompt injection cannot bypass confirmation | `test_prompt_injection_in_metadata_is_inert`, `test_scenario_5_injected_instructions_in_description` |
| SK-1 video-to-playlist | 6 scenarios, 7 tests in `tests/system/test_skill_video_to_playlist.py`: all PASS |
| TQ-8 defects have regression tests | `tests/unit/test_defect_log.py`: 4 defects, all regression tests present and passing |

### Coverage by module (lowest first)
| Module | Lines | Why not higher |
|---|---|---|
| `providers/live.py` | 60 % | HTTP paths against the real API; covered by the scheduled live tests and the fake-service error tests |
| `approval.py` | 67 % | Local HTTP approval page and browser launch; tests use a recording prompt instead |
| `auth.py` | 70 % | Interactive Google sign-in and keychain backends |
| all other modules | 90 – 100 % | |

### Performance (NFR-2, `scripts/benchmark.py`, fixture provider with simulated 250 ms API latency)
| Workflow | Local p50 (ms) | Local max (ms) | API calls | API wait (s) |
|---|---|---|---|---|
| `find_similar_videos` | 217.9 | 229.9 | 7 | 1.75 |
| `find_similar_channels` | 129.3 | 135.3 | 13 | 3.25 |
| `recommend_videos` | 197.1 | 198.0 | 13 | 3.25 |
| `analyze_engagement` | 82.0 | 93.7 | 7 | 1.75 |
| `propose_playlist` | 185.5 | 209.7 | 2 | 0.5 |

Local processing stays under 250 ms per workflow; API waiting time dominates. NFR-2 targets are still TBD-3.

## Remote CI and live runs
| Date | Workflow | Result | Notes |
|---|---|---|---|
| 2026-11-27 | `ci.yml` on GitHub, `main` @ `093b0b0` ([run 46051982833](https://github.com/Awwab157/SE_PROJ/actions/runs/46051982833)) | **PASS**, 6/6 jobs | lint clean; 257 passed, 3 deselected on Ubuntu + Windows x Python 3.11 + 3.12; coverage 90.87 % (gate 85 %); skill + brain validators; gitleaks clean |
| 2026-11-26 to 2026-11-27 | `ci.yml` on every push to `main` (8 runs, `6a03270` to `093b0b0`) | **PASS**, 8/8 | all runs green |
| (to record) | `live-api.yml` | **not yet run** | Needs secrets `YT_INTEL_LIVE_TOKEN_JSON`, `YT_INTEL_LIVE_VIDEO`, `YT_INTEL_LIVE_CHANNEL` in the `live-api` environment |

Manual live check on 2026-11-27: `scripts/yt.py login` and `similar` worked against the real API on the developer's
machine (one `similar` = 3 search calls, 305 units by the ledger).
