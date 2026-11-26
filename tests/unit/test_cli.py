"""scripts/yt.py command-line tool, run against the offline sample data."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("yt_cli", ROOT / "scripts" / "yt.py")
yt = importlib.util.module_from_spec(spec)
sys.modules["yt_cli"] = yt
spec.loader.exec_module(yt)


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["similar", "pdIntro0001", "--limit", "3"], "Merging and Joining DataFrames in Pandas"),
        (["channels", "@datadojo"], "Pandas Pro Tips"),
        (["recommend", "--max-min", "20"], "because:"),
        (["analyze", "--period", "2025", "--compare", "2026"], "Top channels (likes):"),
        (["quota"], "search_calls"),
    ],
)
def test_sample_commands(argv, expected, capsys) -> None:
    assert yt.main(["--sample", *argv]) == 0
    assert expected in capsys.readouterr().out


def test_invalid_link_shows_error(capsys) -> None:
    assert yt.main(["--sample", "similar", "not a link"]) == 1
    out = capsys.readouterr().out
    assert "invalid_input" in out and "Next step:" in out


def test_playlist_declined_writes_nothing(capsys, monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    argv = ["--sample", "playlist", "pandas python", "--total", "60", "--max", "20", "--lang", "en"]
    assert yt.main(argv) == 0
    out = capsys.readouterr().out
    assert "Proposed a private playlist" in out
    assert "Nothing was written to YouTube" in out


def test_live_mode_without_client_file_explains_setup(capsys, monkeypatch, tmp_path) -> None:
    monkeypatch.delenv(yt.CLIENT_SECRETS_ENV, raising=False)
    monkeypatch.setattr(yt, "DEFAULT_SECRETS", tmp_path / "missing.json")
    assert yt.main(["similar", "pdIntro0001"]) == 1
    assert "No OAuth client file found" in capsys.readouterr().out
