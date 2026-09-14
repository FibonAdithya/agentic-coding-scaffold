from pathlib import Path

import pytest

from agentify.repo import Repo, append_text, write_if_missing


def test_open_resolves_root_and_has_no_adapter_for_an_empty_dir(tmp_path: Path):
    repo = Repo.open(tmp_path)
    assert repo.root == tmp_path.resolve()
    assert repo.adapter is None
    assert repo.name == tmp_path.name


def test_open_rejects_a_file(tmp_path: Path):
    f = tmp_path / "x"
    f.write_text("")
    with pytest.raises(FileNotFoundError):
        Repo.open(f)


def test_contains_is_true_for_root_and_paths_under_it_false_for_escapes(
    tmp_path: Path,
):
    repo = Repo.open(tmp_path)
    assert repo.contains(".")
    assert repo.contains("a/b.md")
    (tmp_path / "a").mkdir()
    (tmp_path / "a/b.md").write_text("")
    assert repo.contains("a/b.md")
    assert not repo.contains("../outside.md")
    assert not repo.contains("a/../../outside.md")


def test_read_returns_none_for_missing_and_text_for_present(tmp_path: Path):
    repo = Repo.open(tmp_path)
    assert repo.read("a.txt") is None
    (tmp_path / "a.txt").write_text("hi\n")
    assert repo.read("a.txt") == "hi\n"
    assert repo.exists("a.txt")


def test_write_if_missing_writes_once_and_reports(tmp_path: Path):
    repo = Repo.open(tmp_path)
    assert (
        write_if_missing(repo, "d/f.txt", "one\n", dry_run=False) == "wrote    d/f.txt"
    )
    assert (tmp_path / "d/f.txt").read_text() == "one\n"
    assert (
        write_if_missing(repo, "d/f.txt", "two\n", dry_run=False) == "exists   d/f.txt"
    )
    assert (tmp_path / "d/f.txt").read_text() == "one\n"


def test_write_if_missing_dry_run_writes_nothing(tmp_path: Path):
    repo = Repo.open(tmp_path)
    assert write_if_missing(repo, "f.txt", "x", dry_run=True) == "would write f.txt"
    assert not (tmp_path / "f.txt").exists()


def test_append_text_creates_then_appends_with_blank_line(tmp_path: Path):
    repo = Repo.open(tmp_path)
    assert (
        append_text(repo, ".gitignore", "a/\n", dry_run=False) == "appended .gitignore"
    )
    assert (tmp_path / ".gitignore").read_text() == "a/\n"
    append_text(repo, ".gitignore", "b/\n", dry_run=False)
    assert (tmp_path / ".gitignore").read_text() == "a/\n\nb/\n"


def test_append_text_adds_newline_to_a_file_without_one(tmp_path: Path):
    repo = Repo.open(tmp_path)
    (tmp_path / ".gitignore").write_text("a/")
    append_text(repo, ".gitignore", "b/\n", dry_run=False)
    assert (tmp_path / ".gitignore").read_text() == "a/\n\nb/\n"


def test_append_text_dry_run_writes_nothing(tmp_path: Path):
    repo = Repo.open(tmp_path)
    assert append_text(repo, "g", "x\n", dry_run=True) == "would append g"
    assert not (tmp_path / "g").exists()
