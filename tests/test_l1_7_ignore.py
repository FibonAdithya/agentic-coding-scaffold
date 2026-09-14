from pathlib import Path

from agentify.checks import l1_7_ignore
from agentify.contract import FAIL, PASS
from agentify.repo import Repo


def test_missing_gitignore_fails_naming_the_first_missing_pattern(tmp_path: Path):
    r = l1_7_ignore.check(Repo.open(tmp_path))
    assert r.status == FAIL and ".superpowers/" in r.reason


def test_base_patterns_suffice_without_an_adapter(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("\n".join(l1_7_ignore.BASE_PATTERNS) + "\n")
    assert l1_7_ignore.check(Repo.open(tmp_path)).status == PASS


def test_adapter_patterns_are_required_too(python_repo: Path):
    (python_repo / ".gitignore").write_text("\n".join(l1_7_ignore.BASE_PATTERNS) + "\n")
    r = l1_7_ignore.check(Repo.open(python_repo))
    assert r.status == FAIL and "__pycache__/" in r.reason


def test_comments_and_whitespace_do_not_count(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("# .superpowers/\n  .claude/worktrees/  \n")
    r = l1_7_ignore.check(Repo.open(tmp_path))
    assert r.status == FAIL and ".superpowers/" in r.reason


def test_generate_appends_only_what_is_missing_and_is_idempotent(python_repo: Path):
    (python_repo / ".gitignore").write_text(".venv/\n")
    repo = Repo.open(python_repo)
    assert l1_7_ignore.generate(repo, dry_run=False) == ["appended .gitignore"]
    text = (python_repo / ".gitignore").read_text()
    assert text.startswith(
        ".venv/\n\n# agentify: agent scratch state and tool caches\n"
    )
    assert text.count(".venv/") == 1
    assert l1_7_ignore.check(repo).status == PASS
    assert l1_7_ignore.generate(repo, dry_run=False) == [
        "exists   .gitignore (all patterns present)"
    ]
    assert (python_repo / ".gitignore").read_text() == text
