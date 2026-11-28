---
title: AI session 2026-11-27 — expose the video-to-playlist skill as an MCP prompt
type: ai-session
status: pending-human-review
created: 2026-11-27
---
# AI session 2026-11-27 — expose the video-to-playlist skill as an MCP prompt

## Goal
The project statement (section 1) says the server shall expose tools, resources **and Agent Skills**. Skills existed
only as SKILL.md files, and FR-8.5 forbids registering them as tools or resources. The user chose to expose
`video-to-playlist` as an MCP prompt.

## What the AI did
- `server.py`: prompt `video-to-playlist` (argument `video`, validated with `parse_video_id`); the text is the
  SKILL.md body without frontmatter and related notes (`skill_instructions`), plus the validated video ID. Errors
  are protocol errors with code, cause and next step.
- Tests: system (listed and rendered), negative (invalid video), unit (stripping, missing file).
- Docs: traceability SK-1.1 and FR-8.5, API reference prompts section, user guide, research notes, changelog.

## What worked and what failed
- Worked: serving the skill as an MCP prompt satisfied "expose Agent Skills" without breaking FR-8.5; SKILL.md stays the single source.
- Failed: the SDK replaced the prompt's error message with a generic one until the error was raised as `MCPError`.

## Human review
- Check that exposing a prompt is an acceptable reading of FR-8.5 (it names tools and resources only).
- Try the prompt in Claude Desktop and record it in `docs/tests/skill-evaluations.md`.

## Links
- [[agent-skills-format]] · [[mcp-servers-tools-and-resources]] · [[ai-session-2026-11-27-video-to-playlist-gaps]]
