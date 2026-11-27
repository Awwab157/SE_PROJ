"""Agent Skill text served as an MCP prompt (SK-1)."""

import pytest

from yt_intel_mcp.errors import InternalError
from yt_intel_mcp.server import skill_instructions


def test_frontmatter_and_related_notes_removed(tmp_path) -> None:
    skill = tmp_path / "demo"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: demo\ndescription: x\n---\n# demo\n\n## Steps\n1. Do it.\n\n## Related notes\n- [[x]]\n",
        encoding="utf-8",
    )
    text = skill_instructions("demo", tmp_path)
    assert text == "# demo\n\n## Steps\n1. Do it."


def test_real_skill_body_is_served() -> None:
    text = skill_instructions("video-to-playlist")
    assert text.startswith("# video-to-playlist")
    assert "## Steps" in text and "## Related notes" not in text


def test_missing_skill_file_is_a_clean_error(tmp_path) -> None:
    with pytest.raises(InternalError) as info:
        skill_instructions("nope", tmp_path)
    assert "pip install -e" in info.value.next_step
