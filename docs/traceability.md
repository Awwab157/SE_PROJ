# Traceability matrix (SE-5)

Requirement → Issue → PR → test / review artifact → skill → brain note. Issue and PR numbers are **TBD** until the
repository is on GitHub. Requirements whose text is not described in `BUILD_PLAN_PROMPT.md` are listed as **TBD** and
must be mapped after reading the SRS — nothing is assumed about them.

Test paths are relative to `tests/`. Notes are in `brain/resources/` unless stated.

## Functional requirements
| Req | Summary | Issue | PR | Tests / artifact | Skill | Note |
|---|---|---|---|---|---|---|
| FR-1 | Similar videos | TBD | TBD | `integration/test_services.py::test_similar_videos_*`, `system/test_mcp_end_to_end.py::test_fr1_to_fr4_*` | video-to-playlist | video-metadata |
| FR-1.1 | Video URL/ID forms | TBD | TBD | `unit/test_ids.py::test_video_url_forms`, `::test_malformed_video_ids` | video-to-playlist | video-metadata |
| FR-1.2 | Missing seed fields marked unavailable | TBD | TBD | `integration/test_services.py::test_missing_seed_fields_reported_unavailable` | — | video-metadata |
| FR-1.4 | Weighted similarity, explanations | TBD | TBD | `unit/test_similarity.py` | — | tf-idf-and-cosine-similarity |
| FR-1.6 | No tags fallback / insufficient metadata | TBD | TBD | `integration/test_services.py::test_insufficient_metadata` | — | video-metadata |
| FR-2 | Similar channels, content-first ranking | TBD | TBD | `integration/test_services.py::test_channel_*`, `unit/test_similarity.py::test_subscriber_count_cannot_outrank_content_similarity` | — | channel-metadata |
| FR-2.1 | Channel ID / handle / URL forms | TBD | TBD | `unit/test_ids.py::test_channel_forms`, `integration/test_services.py::test_channel_resolution_forms` | — | channel-metadata |
| FR-2.2 | `/c/` search, candidates if ambiguous | TBD | TBD | `integration/test_services.py::test_custom_url_*` | — | channel-metadata |
| FR-3 | Recommendations from likes/subs/playlists | TBD | TBD | `integration/test_services.py::test_recommendation*`, `negative/test_negative.py::test_empty_account`, `::test_1000_like_limit_is_stated` | — | video-metadata |
| FR-3.7 | No watch history | TBD | TBD | `security/test_security.py::test_tool_descriptions_never_mention_watch_history`, `::test_no_delete_or_update_methods_in_provider_interface` | — | youtube-data-api-v3 |
| FR-4 | Engagement analysis | TBD | TBD | `unit/test_engagement_logic.py` | — | video-metadata |
| FR-4.5 | Duration parsing / buckets | TBD | TBD | `unit/test_duration.py`, `unit/test_engagement_logic.py::test_duration_buckets_mean_median` | — | video-metadata |
| FR-4.6 | Redaction in logs | TBD | TBD | `unit/test_logging.py` | — | api-security-and-error-handling |
| FR-5 | Playlist propose + create | TBD | TBD | `unit/test_playlist_logic.py`, `integration/test_quota_and_proposals.py`, `system/test_mcp_end_to_end.py::test_fr5_*` | video-to-playlist | playlist-creation |
| FR-5.1 | Input validation | TBD | TBD | `unit/test_validation.py::test_propose_validation` | — | playlist-creation |
| FR-5.2 | Fill ≤ total, ≥ 90 % when possible | TBD | TBD | `unit/test_playlist_logic.py::test_never_exceeds_total`, `::test_subset_sum_improves_on_greedy` | — | playlist-creation |
| FR-5.3 | Exclusions (duplicates, private, unknown duration, too long) | TBD | TBD | `unit/test_playlist_logic.py::test_propose_constraints_on_fixtures` | — | video-metadata |
| FR-5.4 | Language exclusion counted | TBD | TBD | `unit/test_playlist_logic.py::test_propose_constraints_on_fixtures` | — | video-metadata |
| FR-5.5 | Shortfall + unmet constraints | TBD | TBD | `unit/test_playlist_logic.py::test_propose_shortfall_reported` | — | playlist-creation |
| FR-5.6 | Approval: elicitation / local code / fail closed | TBD | TBD | `security/test_security.py` (decline, cancel, timeout, fail closed, code never leaks), `system/test_mcp_end_to_end.py::test_fr5_with_local_code` | video-to-playlist | playlist-creation |
| FR-5.8 | Atomic write-quota reservation before writes | TBD | TBD | `integration/test_quota_and_proposals.py::test_playlist_write_quota_reserved_before_any_write` | — | quota-management |
| FR-5.9 | Idempotent create, resume after failure | TBD | TBD | `integration/test_quota_and_proposals.py::test_repeated_confirmation_*`, `::test_failure_after_playlist_insert_*`, `::test_crash_after_*`, `::test_concurrent_create_calls_single_playlist` | — | playlist-creation |
| FR-5.10 | Metadata never treated as instructions | TBD | TBD | `security/test_security.py::test_prompt_injection_in_metadata_is_inert` | video-to-playlist | api-security-and-error-handling |
| FR-6 | Quota buckets, ledger, PT reset | TBD | TBD | `unit/test_quota.py` | — | quota-management |
| FR-6.1 | Cost table | TBD | TBD | `unit/test_quota.py::test_cost_table_loaded` | — | quota-management |
| FR-6.4 | Reject before first call with cost/limit/remaining | TBD | TBD | `integration/test_quota_and_proposals.py::test_over_budget_rejected_with_zero_provider_calls` | — | quota-management |
| FR-6.6 | Cache 24 h / 7 d | TBD | TBD | `unit/test_cache.py` | — | quota-management |
| FR-6.7 | No retry on quotaExceeded | TBD | TBD | `negative/test_negative.py::test_quota_exceeded_is_not_retried` | — | quota-management |
| FR-7 | OAuth, PKCE, scopes, refresh, revoke | TBD | TBD | `security/test_security.py::test_authorization_url_*`, `::test_read_only_token_*`, `negative/test_negative.py::test_invalid_grant_*`, `system/test_mcp_end_to_end.py::test_clear_cache_and_revoke` | — | oauth-2-0 |
| FR-8 | MCP tools + resources | TBD | TBD | `system/test_mcp_end_to_end.py::test_tools_registered_with_write_statement`, `::test_resources` | — | mcp-servers-tools-and-resources |
| FR-8.3 | Schema validation | TBD | TBD | `unit/test_validation.py`, `negative/test_negative.py::test_errors_are_structured` | — | mcp-servers-tools-and-resources |
| FR-8.5 | Skills not registered as tools/resources (exposed as MCP prompts instead) | TBD | TBD | `system/test_mcp_end_to_end.py::test_skills_not_registered`, `::test_video_to_playlist_prompt_exposed` | — | agent-skills-format |

## Non-functional requirements
| Req | Summary | Issue | PR | Tests / artifact | Skill | Note |
|---|---|---|---|---|---|---|
| NFR-1 | Per-tool timing in logs | TBD | TBD | `unit/test_logging.py::test_tool_timer_logs_name_duration_and_outcome` | local-check | api-security-and-error-handling |
| NFR-2 | Local processing vs API wait | TBD | TBD | `scripts/benchmark.py` (review artifact); targets TBD-3 | — | — |
| NFR-5 | No modify/delete | TBD | TBD | `security/test_security.py::test_no_delete_or_update_methods_in_provider_interface` | — | api-security-and-error-handling |
| NFR-10 | No secrets/personal data in repo, logs; state outside repo | TBD | TBD | `security/test_security.py::test_no_secrets_in_repo_files`, `::test_state_and_tokens_only_outside_repo`, `unit/test_storage.py`, CI gitleaks | — | api-security-and-error-handling |
| NFR-11 | Delete cached account data | TBD | TBD | `unit/test_cache.py::test_clear_deletes_account_data`, `system/test_mcp_end_to_end.py::test_clear_cache_and_revoke` | — | oauth-2-0 |
| NFR-13 | Only live provider imports Google client | TBD | TBD | `security/test_security.py::test_only_live_provider_imports_google_client` | — | api-security-and-error-handling |
| NFR-15 | Bounded read retries, no write retries | TBD | TBD | `negative/test_negative.py::test_rate_limit_*`, `::test_writes_are_never_retried` | — | quota-management |
| NFR-17 | Tested OS documented | TBD | TBD | `docs/user-guide.md` §8 (review artifact) | — | — |
| NFR-19 | Descriptions state whether a tool writes | TBD | TBD | `system/test_mcp_end_to_end.py::test_tools_registered_with_write_statement` | — | mcp-servers-tools-and-resources |
| NFR-3, 4, 6–9, 12, 14, 16, 18 | TBD — not described in the build plan | TBD | TBD | TBD | — | — |

## Skills
| Req | Summary | Issue | PR | Tests / artifact | Skill | Note |
|---|---|---|---|---|---|---|
| SK-1 | video-to-playlist | TBD | TBD | `system/test_skill_video_to_playlist.py` (6 evaluation scenarios), `system/test_mcp_end_to_end.py::test_video_to_playlist_chain`, `integration/test_services.py::test_seed_carries_metadata_for_summary`, `::test_propose_from_candidate*`, `scripts/validate_skills.py`; real-client evaluation pending (`docs/tests/skill-evaluations.md`) | video-to-playlist | playlist-creation |
| SK-1.1 | video-to-playlist exposed through the server as MCP prompt `video-to-playlist` (project statement §1: "expose tools, resources, and Agent Skills") | TBD | TBD | `system/test_mcp_end_to_end.py::test_video_to_playlist_prompt_exposed`, `negative/test_negative.py::test_skill_prompt_rejects_invalid_video`, `unit/test_skill_prompt.py` | video-to-playlist | agent-skills-format |
| SK-2 | local-check | TBD | TBD | `scripts/local_check.py` runs recorded in skill evaluations (`docs/tests/skill-evidence-2026-11-27.md`) | local-check | mcp |
| SK-3 | brain-ingest | TBD | TBD | 12 research notes created with it; `scripts/validate_brain.py` | brain-ingest | obsidian-para-second-brain |
| SK-4 | brain-refine | TBD | TBD | validator; evaluation run on a vault copy (`docs/tests/skill-evidence-2026-11-27.md`) | brain-refine | obsidian-para-second-brain |
| SK-5 | brain-query | TBD | TBD | validator; 3 scenarios evaluated (`docs/tests/skill-evidence-2026-11-27.md`) | brain-query | obsidian-para-second-brain |
| SK-6 | Frontmatter, kebab-case, links a distilled note | TBD | TBD | `unit/test_validators.py`, CI validators | all | agent-skills-format |
| SK-7 | TBD — not described in the build plan | TBD | TBD | TBD | — | — |

## Tests and quality
| Req | Summary | Issue | PR | Tests / artifact |
|---|---|---|---|---|
| TQ-1 | Unit tests | TBD | TBD | `tests/unit/` |
| TQ-2 | Integration tests | TBD | TBD | `tests/integration/` |
| TQ-3 | System tests via MCP client | TBD | TBD | `tests/system/` |
| TQ-4 | Negative tests | TBD | TBD | `tests/negative/` |
| TQ-5 | Live API tests (scheduled, budgeted) | TBD | TBD | `tests/live/`, `.github/workflows/live-api.yml` |
| TQ-6 | Quota rejection with zero calls | TBD | TBD | `integration/test_quota_and_proposals.py::test_over_budget_*` |
| TQ-7 | Skill evaluations | TBD | TBD | `docs/tests/skill-evaluations.md` |
| TQ-8 | Defect log + regression tests | TBD | TBD | `docs/tests/defect-log.md` |
| TQ-9 | Proposal/quota concurrency | TBD | TBD | `integration/test_quota_and_proposals.py` |

## Software engineering, second brain, UI, business rules
| Req | Summary | Issue | PR | Artifact / tests | Note |
|---|---|---|---|---|---|
| SE-1 | TBD — not described in the build plan | TBD | TBD | TBD | — |
| SE-2 | Architecture diagrams | TBD | TBD | `docs/architecture.md` (12 diagrams), `docs/design.pdf` (`scripts/build_design_pdf.py`), `docs/adr/` | — |
| SE-3 | ADRs citing brain notes | TBD | TBD | `docs/adr/0001`–`0005` | all research notes |
| SE-4 | Development plan | TBD | TBD | `docs/dev-plan.md` | — |
| SE-5 | Traceability | TBD | TBD | this file | — |
| SE-6 | Provider interface | TBD | TBD | `providers/base.py`, `security/test_security.py::test_no_delete_or_update_*` | youtube-data-api-v3 |
| SE-7 | API documentation | TBD | TBD | `docs/api.md` (generated) | mcp-servers-tools-and-resources |
| SB-1 | PARA vault | TBD | TBD | `brain/`, `scripts/validate_brain.py` | obsidian-para-second-brain |
| SB-2 | Stage review notes | TBD | TBD | `brain/projects/stage-review-1-requirements.md`, `stage-review-2-design.md`, `stage-review-3-testing-ci.md` (build phases: `phase-review-*.md`) | — |
| SB-3 | Skills link distilled notes | TBD | TBD | `scripts/validate_skills.py` | agent-skills-format |
| SB-4 | AGENTS.md conventions | TBD | TBD | `AGENTS.md` | — |
| SB-5, SB-6 | TBD — not described in the build plan | TBD | TBD | TBD | — |
| UI-1 | Structured content + summary | TBD | TBD | `system/test_mcp_end_to_end.py::test_fr1_to_fr4_results_have_summary_and_structure` | mcp-servers-tools-and-resources |
| UI-2 | Proposal contents | TBD | TBD | `system/test_mcp_end_to_end.py::test_fr5_with_elicitation_accept` | playlist-creation |
| UI-3 | Errors: cause + next step, no leaks | TBD | TBD | `negative/test_negative.py::test_errors_are_structured`, `::test_unexpected_error_does_not_leak` | api-security-and-error-handling |
| UI-4 | System-browser OAuth | TBD | TBD | `security/test_security.py::test_authorization_url_*`; browser launch: manual review | oauth-2-0 |
| UI-5 | Decline/cancel/timeout/unsupported write nothing | TBD | TBD | `security/test_security.py::test_decline_and_cancel_*`, `::test_elicitation_timeout_*`, `::test_no_safe_mechanism_fails_closed` | playlist-creation |
| BR-1 | One authorised user per instance | TBD | TBD | design: single token store entry (`auth.py`), review artifact | oauth-2-0 |
| BR-2 | Playlists private by default | TBD | TBD | `unit/test_validation.py::test_propose_valid_defaults_private`, `system/test_mcp_end_to_end.py::test_fr5_with_elicitation_accept` | playlist-creation |
| BR-3–BR-7 | TBD — not described in the build plan | TBD | TBD | TBD | — |
