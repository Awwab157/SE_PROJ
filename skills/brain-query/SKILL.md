---
name: brain-query
description: Answer questions about the YouTube Video Intelligence MCP project from the team's Obsidian second brain (brain/), citing the notes and their sources, and help draft SRS sections or ADRs from them. Use when someone asks why a design decision was made, what the API or quota rules are, or needs a cited draft.
---
# brain-query (SK-5)

## Steps
1. **Find notes.** Start at `brain/index.md`, then search `brain/` for the question's key terms (file names, `title:`, `tags:` and headings). Read the most relevant notes fully, plus the notes they link to when needed.
2. **Answer only from the notes.** Every claim cites its note as a wikilink and, where the note gives one, the source URL. If the notes do not answer the question, say so and suggest running `brain-ingest` on a named source — do not fill gaps from memory.
3. **Flag uncertainty.** Repeat any "(to verify)" or TBD markers from the notes.
4. **Drafting.** When asked for an SRS section or ADR:
   - ADR: use the structure in `docs/adr/` (Context, Decision, Consequences, References) and cite at least one brain note.
   - SRS section: keep requirement IDs (FR, NFR, SK, TQ, SE, SB, UI, BR) exactly as in the notes; mark unknowns as TBD.
   - Mark the draft "AI-drafted — needs human review".
5. **Do not edit notes** in this skill; use `brain-ingest` or `brain-refine` for changes.

## Related notes
- [[obsidian-para-second-brain]]
- [[youtube-data-api-v3]]
- [[quota-management]]
