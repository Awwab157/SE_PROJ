---
title: AI session 2026-11-28 - SDLC requirements audit
type: ai-session
status: pending-human-review
created: 2026-11-28
---
# AI session 2026-11-28 - SDLC requirements audit

## Goal
Check the project against the project statement and the SDLC workflow document (SB-1..6, SE-1..7, version control,
CI, TQ-7/8, AI policy, stages 1-3) and fix what can be fixed in the repository.

## What the AI did
- Added "What worked / What did not work / What to change" to every stage and phase review note (SB-2) and "What
  worked and what failed" to every ai-session note (AI policy); `scripts/validate_brain.py` now requires both, with
  failing-case tests.
- Removed the stray `SE_PROJ/` vault.
- Prepared GitHub issues for requirements, skills, stages, defects and open items, and this change as a pull request
  instead of a direct commit to `main` (SB-5).

## What worked and what failed
- Worked: the brain validator immediately flagged the two build-phase notes that also needed the new sections.
- Failed: GitHub issues and the PR need the GitHub CLI signed in to the user's account, which the session cannot do.

## Human review
- A teammate reviews and merges the PR; the author cannot approve their own PR.
- Still open for the team: SRS in `docs/` (SE-1), notes and commits from every member (SB-6).

## Links
- [[stage-review-1-requirements]] · [[stage-review-2-design]] · [[stage-review-3-testing-ci]] · [[obsidian-para-second-brain]]
