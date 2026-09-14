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


def test_unterminated_marker_is_reported_instead_of_silently_dropped(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("# x\n\n<<FILL: no closing\n")
    assert find_markers(tmp_path) == [
        Marker("AGENTS.md", 3, "unterminated marker: add the closing >>")
    ]


def test_prose_mentioning_the_marker_syntax_without_a_colon_is_not_flagged(
    tmp_path: Path,
):
    # README.md's own "## The three commands" section describes `fill` as
    # listing "the <<FILL>> markers left to write" -- that is not a marker.
    (tmp_path / "README.md").write_text("list the <<FILL>> markers left to write\n")
    assert find_markers(tmp_path) == []


def test_only_generated_files_are_scanned(tmp_path: Path):
    (tmp_path / "notes.md").write_text("<<FILL: ignored>>\n")
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / ".github/workflows/ci.yml").write_text("# <<FILL: seen>>\n")
    assert find_markers(tmp_path) == [Marker(".github/workflows/ci.yml", 1, "seen")]
    assert "AGENTS.md" in FILL_FILES
