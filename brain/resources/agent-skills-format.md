---
title: Agent Skills Format
type: research
status: distilled
created: 2026-11-26
tags: [skills, agents, research]
---
# Agent Skills Format

## Summary
Agent Skills are folders with a `SKILL.md` (YAML frontmatter + Markdown instructions) that an agent loads on demand. This repo ships five skills (SK-1..SK-5).

## Key points
- Required frontmatter: `name` (lowercase letters, digits, hyphens; at most 64 chars; we also require it to equal the folder name) and `description` (what it does and when to use it; at most 1024 chars).
- The description is what the agent sees first; the body is loaded only when the skill is used (progressive disclosure).
- Every skill here links at least one distilled brain note (SK-6, SB-3); `scripts/validate_skills.py` enforces format and links in CI.
- Skills orchestrate MCP tools but are not registered as MCP tools or resources (FR-8.5), see [[mcp-servers-tools-and-resources]].
- Skill evaluations are recorded in `docs/tests/skill-evaluations.md` (TQ-7).

## Sources
- https://docs.claude.com/en/docs/agents-and-tools/agent-skills/overview
- https://github.com/anthropics/skills

## Requirements
- SK-1, SK-2, SK-3, SK-4, SK-5, SK-6, TQ-7, FR-8.5

## Links
- [[obsidian-para-second-brain]] · [[mcp]]
