from pathlib import Path

from agentify.fill import FILL_FILES, Marker, find_markers


def test_finds_markers_with_line_numbers_and_collapsed_prompts(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text(
        "# x\n\n<<FILL: first\n  prompt >>\n\ntext\n<<FILL: second>>\n"
    )
    assert find_markers(tmp_path) == [
        Marker("AGENTS.md", 3, "first prompt"),
        Marker("AGENTS.md", 7, "second"),
    ]


def test_only_generated_files_are_scanned(tmp_path: Path):
    (tmp_path / "notes.md").write_text("<<FILL: ignored>>\n")
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / ".github/workflows/ci.yml").write_text("# <<FILL: seen>>\n")
    assert find_markers(tmp_path) == [Marker(".github/workflows/ci.yml", 1, "seen")]
    assert "AGENTS.md" in FILL_FILES
