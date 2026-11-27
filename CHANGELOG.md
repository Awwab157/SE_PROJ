# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [1.0.0] — unreleased (pending human review; tag `v1.0.0` after merge and green CI)

### Added
- MCP server over stdio with nine tools (`find_similar_videos`, `find_similar_channels`, `recommend_videos`,
  `analyze_engagement`, `propose_playlist`, `create_playlist`, `start_authorization`, `revoke_authorization`,
  `clear_cache`) and resources `quota://status`, `config://server`, `proposal://{id}` (FR-8).
- Similar videos and channels from metadata with TF-IDF and weighted, explainable scores (FR-1, FR-2).
- Recommendations from likes, subscriptions and playlists (FR-3) and engagement analysis with labelled timestamp
  sources (FR-4).
- Playlist planner and approval-gated creation: elicitation or local one-time code, fail closed otherwise; idempotent
  state machine that resumes instead of duplicating (FR-5).
- Quota ledger with atomic per-bucket reservation and Pacific-time reset; 24 h / 7 d cache (FR-6).
- Installed-app OAuth with PKCE, incremental write scope, keychain token storage and revocation (FR-7).
- `propose_playlist` accepts optional `candidate_video_ids` so `video-to-playlist` builds the playlist from the
  similar videos; `find_similar_videos` returns the seed's description, tags, duration, category, language and
  publish date for the metadata-based summary (D-003, D-004).
- MCP prompt `video-to-playlist` (argument `video`): the Agent Skill is exposed through the server; its text is
  `skills/video-to-playlist/SKILL.md` (SK-1.1).
- System design document: `docs/architecture.md` (context, deployment, components, provider abstraction, MCP
  surface, workflows, state machine, data model, similarity, quota, errors, security, tests, knowledge base) and
  `docs/design.pdf` built by `scripts/build_design_pdf.py`.
- Testing and CI: `docs/tests/test-plan.md` and `test-results.md`; six video-to-playlist evaluation scenarios as
  MCP system tests; defect-log consistency test; CI coverage gate (85 %) and JUnit/coverage artifacts.
- Redacting logs with per-tool timing; structured errors with cause and next step.
- Fixture provider and offline test suite (unit, integration, system, negative, security); scheduled live tests.
- Agent Skills `video-to-playlist`, `local-check`, `brain-ingest`, `brain-refine`, `brain-query`.
- Obsidian PARA vault with 12 research notes; CI validators for skills and notes; gitleaks secret scan.
- Command-line tool `scripts/yt.py` (login, similar, channels, recommend, analyze, playlist, quota, logout) and
  offline walkthrough `scripts/demo.py`.
- Documentation: user guide, API reference (generated), architecture diagrams, ADRs, dev plan, traceability.
