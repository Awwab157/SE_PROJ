---
title: Stage review 2 — architecture, design documentation and skills
type: stage-review
status: pending-human-review
created: 2026-11-27
---
# Stage review 2 — architecture, design documentation and skills

## Summary
| Deliverable | State | Where |
|---|---|---|
| Architecture and design documentation | done: 17 sections (goals, context, deployment, components, provider abstraction, MCP surface, workflows, state machine, data model, similarity, quota, errors, security, tests, knowledge base, concurrency, decisions) | `docs/architecture.md`, `docs/design.pdf`, 5 ADRs in `docs/adr/` |
| Diagrams | done: 12 Mermaid diagrams, rendered in the PDF | `docs/architecture.md` |
| brain-refine and brain-query skills | done; evaluated 2026-11-27 (6/6 scenarios PASS, brain-refine on a vault copy) | `skills/brain-refine/`, `skills/brain-query/`, `docs/tests/skill-evidence-2026-11-27.md` |
| First version of local-check | done; 5/5 steps PASS | `skills/local-check/`, `scripts/local_check.py` |

Implementation details of the build phases are in [[phase-review-implementation]] and [[phase-review-skills-and-docs]].

## Decisions
- `docs/architecture.md` is the single design source; `docs/design.pdf` is generated from it and the ADRs by `scripts/build_design_pdf.py` (headless Edge/Chrome).
- Agent Skills are served as MCP prompts, not tools or resources (FR-8.5); see [[agent-skills-format]].
- Decisions are ADRs 0001–0005 (runtime, confirmation, quota, similarity, storage).

## What worked
- One design source (`docs/architecture.md`) with Mermaid diagrams, rendered to a PDF by a script, keeps the PDF reproducible.
- Looking at the rendered pages caught an unreadable component diagram and orphaned headings before submission.
- Evaluating brain-refine on a copy of the vault tested the skill without touching team notes; the validator even caught a mistake made during refinement.

## What did not work
- The first architecture document had fallen behind the code (no prompt, no candidate-ID path) until it was rewritten.
- Skill evaluations for brain-refine and brain-query stayed "Pending" from the first build until this stage.
- The PDF build needs internet access for two rendering libraries.

## What to change
- Update `docs/architecture.md` and rebuild the PDF in the same PR as any design-relevant code change.
- Run skill evaluations at the end of every stage (TQ-7), not only before submission.

## Open items
- Human check of the design PDF against the code and of the AI-run skill evaluations.
- Rebuild the PDF after every design or ADR change (needs internet for the two rendering libraries).

## Links
- [[ai-session-2026-11-27-design-docs]] · [[stage-review-1-requirements]] · [[stage-review-3-testing-ci]] · [[mcp-servers-tools-and-resources]]
