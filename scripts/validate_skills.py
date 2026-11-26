"""Validate Agent Skills (SK-6, SB-3).

For every ``skills/<dir>/SKILL.md``:
* YAML frontmatter with ``name`` and ``description``;
* ``name`` is kebab-case, at most 64 characters, and equals the directory name;
* ``description`` is non-empty and at most 1024 characters;
* the body links (``[[wikilink]]``) to at least one existing brain note whose status is ``distilled``,
  and every wikilink resolves.

Usage: ``python scripts/validate_skills.py [skills_dir] [brain_dir]``. Exits 1 on any error.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_brain import split_frontmatter, wikilinks  # noqa: E402

KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def brain_index(brain: Path) -> dict[str, dict]:
    notes: dict[str, dict] = {}
    for path in brain.rglob("*.md"):
        if ".obsidian" in path.parts:
            continue
        meta, _ = split_frontmatter(path.read_text(encoding="utf-8"))
        notes[path.stem.lower()] = meta or {}
    return notes


def validate_skill(path: Path, notes: dict[str, dict]) -> list[str]:
    rel = path.as_posix()
    meta, body = split_frontmatter(path.read_text(encoding="utf-8"))
    if meta is None:
        return [f"{rel}: missing or invalid YAML frontmatter"]
    errors: list[str] = []
    name = meta.get("name")
    description = meta.get("description")
    if not name:
        errors.append(f"{rel}: frontmatter 'name' is missing")
    elif not isinstance(name, str) or not KEBAB.match(name) or len(name) > 64:
        errors.append(f"{rel}: name '{name}' must be kebab-case and at most 64 characters")
    elif name != path.parent.name:
        errors.append(f"{rel}: name '{name}' must match its directory '{path.parent.name}'")
    if not description or not str(description).strip():
        errors.append(f"{rel}: frontmatter 'description' is missing")
    elif len(str(description)) > 1024:
        errors.append(f"{rel}: description is longer than 1024 characters")
    links = wikilinks(body)
    for link in links:
        if link.lower() not in notes:
            errors.append(f"{rel}: broken wikilink [[{link}]]")
    if not any(notes.get(link.lower(), {}).get("status") == "distilled" for link in links):
        errors.append(f"{rel}: must link at least one distilled brain note")
    return errors


def validate_skills(skills: Path, brain: Path) -> list[str]:
    files = sorted(skills.glob("*/SKILL.md"))
    if not files:
        return [f"{skills.as_posix()}: no SKILL.md files found"]
    notes = brain_index(brain)
    errors: list[str] = []
    for path in files:
        errors.extend(validate_skill(path, notes))
    for folder in sorted(p for p in skills.iterdir() if p.is_dir()):
        if not (folder / "SKILL.md").exists():
            errors.append(f"{folder.as_posix()}: directory has no SKILL.md")
    return errors


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    root = Path(__file__).resolve().parents[1]
    skills = Path(argv[0]) if argv else root / "skills"
    brain = Path(argv[1]) if len(argv) > 1 else root / "brain"
    errors = validate_skills(skills, brain)
    for e in errors:
        print(f"ERROR {e}")
    print(f"skill validation: {'FAILED' if errors else 'OK'} ({len(errors)} errors)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
