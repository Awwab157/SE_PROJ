---
name: brain-ingest
description: Capture research into the team's Obsidian second brain (brain/) as a well-formed research note with sources, requirement IDs and wikilinks. Use when someone reads documentation, an article or a spec relevant to the YouTube Video Intelligence MCP project and wants it recorded for the team.
---
# brain-ingest (SK-3)

## Steps
1. **Collect sources.** Use primary sources (official docs, specs, RFCs) where possible. Record each URL. Never paste secrets, tokens or personal data.
2. **Pick a file name.** kebab-case title, e.g. `quota-management.md`. Search `brain/` first; if a note on the topic exists, extend it instead of creating a duplicate.
3. **Write the note** in `brain/resources/` (or `brain/inbox/` if unsure where it belongs) using this template:

```markdown
---
title: <Title>
type: research
status: draft            # brain-refine sets "distilled" once reviewed
created: <YYYY-MM-DD>
tags: [<topic>, research]
---
# <Title>

## Summary
<2–3 sentences: what it is and why it matters to this project>

## Key points
- <facts, each checkable against a source; mark anything unverified "(to verify)">

## Sources
- <URL>

## Requirements
- <SRS IDs this informs, e.g. FR-6.1, NFR-10>

## Links
- <wikilinks to related notes>
```

4. **Link it.** Add at least one wikilink to a related note, and add the new note to `brain/index.md`.
5. **Log it.** Append a dated line to `brain/log.md` (what was ingested, by whom, AI-assisted or not).
6. **Validate.** Run `python scripts/validate_brain.py`; fix every error before committing.

## Related notes
- [[obsidian-para-second-brain]] — PARA layout and note format
- [[agent-skills-format]]
