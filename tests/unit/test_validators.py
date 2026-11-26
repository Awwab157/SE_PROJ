"""The CI validators must fail on bad input (Phase 1, step 6)."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(name: str):
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


vb = load("validate_brain")
vs = load("validate_skills")

RESEARCH = """---
title: Good Note
type: research
status: distilled
---
# Good Note
## Summary
Text.
## Key points
- point
## Sources
- https://example.org/doc
## Requirements
- FR-1
## Links
- [[{link}]]
"""


def make_brain(tmp: Path, link: str = "other-note") -> Path:
    brain = tmp / "brain"
    for folder in ("inbox", "projects", "areas", "resources", "archive"):
        (brain / folder).mkdir(parents=True)
    (brain / "index.md").write_text("# Index\n[[good-note]]\n")
    (brain / "log.md").write_text("# Log\n")
    (brain / "resources" / "good-note.md").write_text(RESEARCH.format(link=link))
    (brain / "resources" / "other-note.md").write_text(RESEARCH.format(link="good-note"))
    return brain


def make_skill(tmp: Path, frontmatter: str, body: str = "See [[good-note]].") -> Path:
    skill = tmp / "skills" / "demo-skill"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(f"---\n{frontmatter}\n---\n# Demo\n{body}\n")
    return tmp / "skills"


def test_valid_brain_and_skill(tmp_path) -> None:
    brain = make_brain(tmp_path)
    assert vb.validate_brain(brain) == []
    skills = make_skill(tmp_path, "name: demo-skill\ndescription: Does a demo thing.")
    assert vs.validate_skills(skills, brain) == []


def test_skill_missing_description_fails(tmp_path) -> None:
    brain = make_brain(tmp_path)
    skills = make_skill(tmp_path, "name: demo-skill")
    errors = vs.validate_skills(skills, brain)
    assert any("description" in e for e in errors)
    assert vs.main([str(skills), str(brain)]) == 1


def test_skill_bad_name_fails(tmp_path) -> None:
    brain = make_brain(tmp_path)
    skills = make_skill(tmp_path, "name: Demo_Skill\ndescription: x")
    assert any("kebab-case" in e for e in vs.validate_skills(skills, brain))


def test_skill_broken_link_fails(tmp_path) -> None:
    brain = make_brain(tmp_path)
    skills = make_skill(tmp_path, "name: demo-skill\ndescription: x", body="See [[missing-note]].")
    errors = vs.validate_skills(skills, brain)
    assert any("broken wikilink" in e for e in errors)
    assert any("distilled" in e for e in errors)


def test_brain_broken_link_fails(tmp_path) -> None:
    brain = make_brain(tmp_path, link="does-not-exist")
    errors = vb.validate_brain(brain)
    assert any("broken wikilink [[does-not-exist]]" in e for e in errors)
    assert vb.main([str(brain)]) == 1


def test_brain_missing_section_fails(tmp_path) -> None:
    brain = make_brain(tmp_path)
    note = brain / "resources" / "good-note.md"
    note.write_text(note.read_text().replace("## Requirements\n- FR-1\n", ""))
    errors = vb.validate_brain(brain)
    assert any("missing section '## Requirements'" in e for e in errors)


def test_repository_brain_and_skills_are_valid() -> None:
    assert vb.validate_brain(ROOT / "brain") == []
    assert vs.validate_skills(ROOT / "skills", ROOT / "brain") == []
