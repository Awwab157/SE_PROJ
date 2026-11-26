"""Validate the Obsidian second brain (SB-1..SB-6).

Checks every Markdown note under ``brain/``:
* frontmatter with ``title``, ``type`` and ``status`` (``index.md`` and ``log.md`` are exempt);
* the sections required for the note ``type``;
* research notes cite at least one source URL and at least one requirement ID;
* every ``[[wikilink]]`` resolves to an existing note.

Usage: ``python scripts/validate_brain.py [brain_dir]``. Exits 1 on any error.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

REQUIRED_SECTIONS: dict[str, list[str]] = {
    "research": ["Summary", "Key points", "Sources", "Requirements", "Links"],
    "project": ["Summary", "Links"],
    "area": ["Summary", "Links"],
    "stage-review": ["Summary", "Decisions", "Open items", "Links"],
    "ai-session": ["Goal", "What the AI did", "Human review", "Links"],
}
EXEMPT = {"index.md", "log.md"}
REQ_ID = re.compile(r"\b(FR|NFR|SK|TQ|SE|SB|UI|BR|TBD)-\d+(\.\d+)?\b")
WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
URL = re.compile(r"https?://\S+")


def split_frontmatter(text: str) -> tuple[dict | None, str]:
    if not text.startswith("---"):
        return None, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, text
    try:
        data = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return None, text
    return (data if isinstance(data, dict) else None), parts[2]


def note_names(brain: Path) -> set[str]:
    return {p.stem.lower() for p in brain.rglob("*.md") if ".obsidian" not in p.parts}


def wikilinks(text: str) -> list[str]:
    return [m.group(1).strip() for m in WIKILINK.finditer(text)]


def sections(body: str) -> set[str]:
    return {m.group(1).strip() for m in re.finditer(r"^##\s+(.+?)\s*$", body, re.M)}


def section_text(body: str, name: str) -> str:
    match = re.search(rf"^##\s+{re.escape(name)}\s*$(.*?)(?=^##\s|\Z)", body, re.M | re.S)
    return match.group(1) if match else ""


def validate_note(path: Path, names: set[str]) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    rel = path.as_posix()
    for link in wikilinks(text):
        if link.lower() not in names:
            errors.append(f"{rel}: broken wikilink [[{link}]]")
    if path.name in EXEMPT:
        return errors
    meta, body = split_frontmatter(text)
    if meta is None:
        return errors + [f"{rel}: missing or invalid YAML frontmatter"]
    for key in ("title", "type", "status"):
        if not meta.get(key):
            errors.append(f"{rel}: frontmatter field '{key}' is missing")
    note_type = meta.get("type")
    if note_type not in REQUIRED_SECTIONS:
        return errors + [f"{rel}: unknown note type '{note_type}' (expected one of {sorted(REQUIRED_SECTIONS)})"]
    present = sections(body)
    for section in REQUIRED_SECTIONS[note_type]:
        if section not in present:
            errors.append(f"{rel}: missing section '## {section}'")
    if note_type == "research":
        if not URL.search(section_text(body, "Sources")):
            errors.append(f"{rel}: research note cites no source URL")
        if not REQ_ID.search(section_text(body, "Requirements")):
            errors.append(f"{rel}: research note lists no requirement ID")
        if not wikilinks(body):
            errors.append(f"{rel}: research note has no [[wikilinks]]")
    return errors


def validate_brain(brain: Path) -> list[str]:
    if not brain.is_dir():
        return [f"{brain}: brain directory not found"]
    names = note_names(brain)
    errors: list[str] = []
    for path in sorted(brain.rglob("*.md")):
        if ".obsidian" in path.parts:
            continue
        errors.extend(validate_note(path, names))
    for required in ("index.md", "log.md"):
        if not (brain / required).exists():
            errors.append(f"{brain.as_posix()}: missing {required}")
    for folder in ("inbox", "projects", "areas", "resources", "archive"):
        if not (brain / folder).is_dir():
            errors.append(f"{brain.as_posix()}: missing PARA folder '{folder}'")
    return errors


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    brain = Path(argv[0]) if argv else Path(__file__).resolve().parents[1] / "brain"
    errors = validate_brain(brain)
    for e in errors:
        print(f"ERROR {e}")
    print(f"brain validation: {'FAILED' if errors else 'OK'} ({len(errors)} errors)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
