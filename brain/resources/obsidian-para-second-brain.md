---
title: Obsidian PARA Second Brain
type: research
status: distilled
created: 2026-11-26
tags: [obsidian, para, knowledge-management, research]
---
# Obsidian PARA Second Brain

## Summary
The team's knowledge base is an Obsidian vault in `brain/`, organised with PARA and linked with Obsidian wikilinks (double square brackets) (SB-1..SB-6).

## Key points
- PARA: **Projects** (time-bound goals, e.g. release 1.0), **Areas** (ongoing responsibilities, e.g. API compliance), **Resources** (reference/research notes), **Archive** (inactive). `inbox/` holds unprocessed captures.
- `index.md` is the map of content; `log.md` is the chronological log of ingests, refinements and reviews.
- Research notes have frontmatter (`title`, `type`, `status`) and sections Summary, Key points, Sources, Requirements, Links; `scripts/validate_brain.py` enforces this and fails on broken wikilinks.
- Skills: `brain-ingest` (capture with sources), `brain-refine` (PARA moves, duplicates, link repair), `brain-query` (answers with citations, drafts SRS sections/ADRs). See [[agent-skills-format]].
- Stage review notes close each stage (SB-2); ai-session notes record significant AI sessions.

## Sources
- https://fortelabs.com/blog/para/
- https://help.obsidian.md/Linking+notes+and+files/Internal+links

## Requirements
- SB-1, SB-2, SB-3, SB-4, SK-3, SK-4, SK-5

## Links
- [[agent-skills-format]] · [[yt-intel-mcp-release-1]]
