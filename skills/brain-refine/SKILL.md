---
name: brain-refine
description: Tidy the team's Obsidian second brain (brain/) - file inbox notes into PARA folders, merge duplicate notes, repair broken wikilinks and mark reviewed research notes as distilled. Use periodically, after several ingests, or when validate_brain.py reports errors.
---
# brain-refine (SK-4)

## Steps
1. **Baseline.** Run `python scripts/validate_brain.py` and note the errors.
2. **PARA moves.** For each note in `brain/inbox/`, move it to:
   - `projects/` if it serves a time-bound goal (a release, a stage),
   - `areas/` if it is an ongoing responsibility,
   - `resources/` if it is reference or research,
   - `archive/` if it is no longer active.
   Moving a file keeps its name, so wikilinks stay valid.
3. **Duplicates.** Find notes with the same or very similar titles or overlapping Key points (compare file names and `title:` frontmatter). Merge into the better note, keep all sources and requirement IDs, and replace the duplicate's links with links to the kept note. Move the leftover file to `archive/` with a line "Merged into <wikilink>".
4. **Broken links.** For each broken wikilink reported by the validator: link to the correct existing note (renamed or merged), or create a stub in `inbox/` if the target should exist, or remove the link if it was a mistake.
5. **Distil.** For research notes whose sources a human has checked, set `status: distilled` and make the Summary and Key points concise.
6. **Index and log.** Update `brain/index.md` for moved or new notes and append a dated line to `brain/log.md` describing the changes.
7. **Validate.** `python scripts/validate_brain.py` and `python scripts/validate_skills.py` must both pass.

## Related notes
- [[obsidian-para-second-brain]]
- [[agent-skills-format]]
