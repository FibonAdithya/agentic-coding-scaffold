from pathlib import Path

from agentify.checks import l1_6_notes
from agentify.contract import FAIL, PASS
from agentify.repo import Repo


def test_missing_notes_readme_fails(tmp_path: Path):
    r = l1_6_notes.check(Repo.open(tmp_path))
    assert r.status == FAIL and "docs/ai/README.md missing" in r.reason


def test_readme_must_disclaim_authority(tmp_path: Path):
    (tmp_path / "docs/ai").mkdir(parents=True)
    (tmp_path / "docs/ai/README.md").write_text("# Notes\n\nThe best docs.\n")
    r = l1_6_notes.check(Repo.open(tmp_path))
    assert r.status == FAIL and "not the source of truth" in r.reason
    (tmp_path / "docs/ai/README.md").write_text(
        "# Notes\n\nThese are NOT the source of truth.\n"
    )
    assert l1_6_notes.check(Repo.open(tmp_path)).status == PASS


def test_generate_writes_readme_and_keeps_specs_and_plans_dirs(tmp_path: Path):
    repo = Repo.open(tmp_path)
    assert l1_6_notes.generate(repo, dry_run=False) == [
        "wrote    docs/ai/README.md",
        "wrote    docs/ai/specs/.gitkeep",
        "wrote    docs/ai/plans/.gitkeep",
    ]
    assert l1_6_notes.check(repo).status == PASS
    assert l1_6_notes.generate(repo, dry_run=False) == [
        "exists   docs/ai/README.md",
        "exists   docs/ai/specs/.gitkeep",
        "exists   docs/ai/plans/.gitkeep",
    ]
