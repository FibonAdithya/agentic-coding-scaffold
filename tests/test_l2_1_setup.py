from pathlib import Path

from agentify.checks import l1_1_router, l1_2_gate, l2_1_setup
from agentify.contract import FAIL, PASS
from agentify.repo import Repo

ROUTER_WITH_ROW = """\
# Agent guide

## Where to look

| Task | Start here |
|---|---|
| Set up a development environment | `make setup` (a target in `Makefile`) |
"""

MAKEFILE = """\
.PHONY: check setup

check:
\techo check

setup:
\techo setup
"""


def repo_with(root: Path, makefile: str | None, router: str | None) -> Repo:
    if makefile is not None:
        (root / "Makefile").write_text(makefile)
    if router is not None:
        (root / "AGENTS.md").write_text(router)
    return Repo.open(root)


def test_missing_makefile_fails(tmp_path: Path):
    r = l2_1_setup.check(repo_with(tmp_path, None, ROUTER_WITH_ROW))
    assert r.status == FAIL and "Makefile missing" in r.reason


def test_makefile_without_setup_fails_and_names_the_template(tmp_path: Path):
    r = l2_1_setup.check(repo_with(tmp_path, "check:\n\techo check\n", ROUTER_WITH_ROW))
    assert r.status == FAIL
    assert "no `setup` target" in r.reason
    assert "src/agentify/adapters/python.py::GATE_BODY" in r.reason


def test_router_without_the_row_fails(tmp_path: Path):
    r = l2_1_setup.check(
        repo_with(tmp_path, MAKEFILE, "# x\n\n## Where to look\n\n| a | b |\n")
    )
    assert r.status == FAIL and "make setup" in r.reason and "Where to look" in r.reason


def test_missing_router_fails(tmp_path: Path):
    r = l2_1_setup.check(repo_with(tmp_path, MAKEFILE, None))
    assert r.status == FAIL and "AGENTS.md missing" in r.reason


def test_setup_target_whose_dry_run_fails_is_reported(tmp_path: Path):
    broken = "setup: missing-prerequisite\n\techo setup\n"
    r = l2_1_setup.check(repo_with(tmp_path, broken, ROUTER_WITH_ROW))
    assert r.status == FAIL and "`make -n setup` failed" in r.reason


def test_good_repo_passes(tmp_path: Path):
    assert (
        l2_1_setup.check(repo_with(tmp_path, MAKEFILE, ROUTER_WITH_ROW)).status == PASS
    )


def test_generate_writes_nothing(python_repo: Path):
    assert l2_1_setup.generate(Repo.open(python_repo), dry_run=False) == []


def test_generated_python_makefile_and_router_pass(python_repo: Path):
    """The level 1 generators already produce everything L2.1 needs."""
    repo = Repo.open(python_repo)
    l1_2_gate.generate(repo, dry_run=False)
    l1_1_router.generate(repo, dry_run=False)
    assert l2_1_setup.check(repo).status == PASS
    text = (python_repo / "Makefile").read_text()
    assert "grep -q '^\\[project\\]' pyproject.toml" in text
