from pathlib import Path

from agentify.checks import l1_5_references
from agentify.contract import FAIL, PASS
from agentify.repo import Repo


def test_unresolved_reference_fails_with_location(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("# x\n\nSee `gone.md`.\n")
    r = l1_5_references.check(Repo.open(tmp_path))
    assert r.status == FAIL
    assert "AGENTS.md:3: `gone.md` -- path does not exist" in r.reason


def test_all_resolving_passes(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("# x\n\nSee `README.md#top`.\n")
    (tmp_path / "README.md").write_text("# Top\n")
    r = l1_5_references.check(Repo.open(tmp_path))
    assert r.status == PASS and "2 authoritative docs" in r.reason


def test_generate_for_python_writes_the_docs_test(python_repo: Path):
    repo = Repo.open(python_repo)
    assert l1_5_references.generate(repo, dry_run=False) == [
        "wrote    tests/test_docs_references.py"
    ]
    text = (python_repo / "tests/test_docs_references.py").read_text()
    assert "from agentify.docs_refs import" in text
    assert l1_5_references.generate(repo, dry_run=False) == [
        "exists   tests/test_docs_references.py"
    ]


def test_generate_without_adapter_writes_nothing(tmp_path: Path):
    actions = l1_5_references.generate(Repo.open(tmp_path), dry_run=False)
    assert actions == [
        "skipped  tests/test_docs_references.py (no language adapter; run `agentify check` instead)"
    ]
    assert not (tmp_path / "tests").exists()
