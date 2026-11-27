## Summary
<!-- What changes and why. -->

## Requirements
<!-- SRS IDs this PR implements or affects, e.g. FR-5.6, NFR-10, SK-1. Link the issue(s). -->

## AI-generated parts
<!-- Required by AGENTS.md. List the files/sections an AI generated, or write "None". -->
- AI session note: `brain/projects/ai-session-<date>-<topic>.md` <!-- required for significant AI sessions -->

## Human review
<!-- Who read the AI-generated diff, and what they checked. At least 1 approving review is required. -->

## Checklist
- [ ] `ruff check src tests scripts` passes
- [ ] `pytest -q` passes (fixture provider, no network)
- [ ] `python scripts/validate_skills.py` and `python scripts/validate_brain.py` pass
- [ ] No secrets, tokens or real personal data in code, fixtures, logs or prompts
- [ ] New behaviour has a test; a fixed defect has an entry in `docs/tests/defect-log.md` and a regression test
- [ ] `docs/traceability.md` (and `docs/api.md` via `scripts/gen_api_docs.py`, if the API changed) updated
- [ ] No YouTube write without explicit user-mediated approval; existing videos and playlists are never modified
