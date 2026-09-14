from pathlib import Path

from agentify.checks import l1_4_authority
from agentify.contract import FAIL, PASS
from agentify.repo import Repo

AGENTS = """\
## Source of truth, in order

1. The code in `src/`.
2. `README.md`.
3. `docs/ai/` -- see `docs/ai/README.md`.

## Where to look

`nowhere.md` is not in the authority section and is not this item's concern.
"""


def test_missing_router_fails(tmp_path: Path):
    r = l1_4_authority.check(Repo.open(tmp_path))
    assert r.status == FAIL and "AGENTS.md missing" in r.reason


def test_empty_section_fails(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("## Source of truth, in order\n\nprose only\n")
    r = l1_4_authority.check(Repo.open(tmp_path))
    assert r.status == FAIL and "names no documents" in r.reason


def test_every_listed_path_must_exist(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text(AGENTS)
    r = l1_4_authority.check(Repo.open(tmp_path))
    assert r.status == FAIL and "`src/`" in r.reason
    (tmp_path / "src").mkdir()
    (tmp_path / "README.md").write_text("")
    (tmp_path / "docs/ai").mkdir(parents=True)
    (tmp_path / "docs/ai/README.md").write_text("")
    r = l1_4_authority.check(Repo.open(tmp_path))
    assert r.status == PASS and "4 documents" in r.reason


def test_generate_writes_readme_once(python_repo: Path):
    repo = Repo.open(python_repo)
    assert l1_4_authority.generate(repo, dry_run=False) == ["wrote    README.md"]
    text = (python_repo / "README.md").read_text()
    assert text.startswith(f"# {python_repo.name}\n")
    assert "<<FILL:" in text and "`AGENTS.md`" in text
    assert l1_4_authority.generate(repo, dry_run=False) == ["exists   README.md"]
