from pathlib import Path

import pytest

from agentify.checks import l1_2_gate
from agentify.contract import FAIL, PASS
from agentify.repo import Repo

GOOD = "PYTHON ?= python\n\n.PHONY: check test\n\ncheck: test\n\ntest:\n\t$(PYTHON) -m pytest\n"


def test_missing_makefile_fails(tmp_path: Path):
    r = l1_2_gate.check(Repo.open(tmp_path))
    assert r.status == FAIL and "Makefile missing" in r.reason


def test_good_makefile_passes(tmp_path: Path):
    (tmp_path / "Makefile").write_text(GOOD)
    assert l1_2_gate.check(Repo.open(tmp_path)).status == PASS


def test_no_check_target_fails(tmp_path: Path):
    (tmp_path / "Makefile").write_text("test:\n\tpytest\n")
    r = l1_2_gate.check(Repo.open(tmp_path))
    assert r.status == FAIL and "no `check` target" in r.reason


@pytest.mark.parametrize(
    "recipe, what",
    [
        ("\t$(PYTHON) -m pytest || true\n", "'|| true'"),
        ("\t$(PYTHON) -m pytest || exit 0\n", "'|| exit 0'"),
        ("\t-$(PYTHON) -m pytest\n", "leading '-'"),
    ],
)
def test_swallowed_failures_are_rejected(tmp_path: Path, recipe: str, what: str):
    (tmp_path / "Makefile").write_text(GOOD.replace("\t$(PYTHON) -m pytest\n", recipe))
    r = l1_2_gate.check(Repo.open(tmp_path))
    assert r.status == FAIL and what in r.reason and "line 8" in r.reason


def test_comment_lines_mentioning_or_true_are_fine(tmp_path: Path):
    (tmp_path / "Makefile").write_text("# nothing here uses || true\n" + GOOD)
    assert l1_2_gate.check(Repo.open(tmp_path)).status == PASS


def test_fill_marker_in_makefile_fails(tmp_path: Path):
    (tmp_path / "Makefile").write_text("check:\n\t<<FILL: run things>>\n")
    r = l1_2_gate.check(Repo.open(tmp_path))
    assert r.status == FAIL and "<<FILL>>" in r.reason


def test_python_repo_needs_the_contract_self_check(python_repo: Path):
    (python_repo / "Makefile").write_text(GOOD)
    r = l1_2_gate.check(Repo.open(python_repo))
    assert r.status == FAIL and "tests/test_contract.py missing" in r.reason
    (python_repo / "tests/test_contract.py").write_text("")
    assert l1_2_gate.check(Repo.open(python_repo)).status == PASS


def test_unresolvable_target_fails_via_make_n(tmp_path: Path):
    (tmp_path / "Makefile").write_text("check: nonexistent-prereq\n")
    r = l1_2_gate.check(Repo.open(tmp_path))
    assert r.status == FAIL and "make -n check" in r.reason


def test_generate_for_python_writes_makefile_and_ruff_config(python_repo: Path):
    repo = Repo.open(python_repo)
    actions = l1_2_gate.generate(repo, dry_run=False)
    assert actions == ["wrote    Makefile", "appended pyproject.toml"]
    makefile = (python_repo / "Makefile").read_text()
    assert "check: lint format-check test" in makefile
    assert "\n\t$(RUFF) check .\n" in makefile
    assert "[tool.ruff]" in (python_repo / "pyproject.toml").read_text()
    assert l1_2_gate.generate(repo, dry_run=False) == [
        "exists   Makefile",
        "exists   pyproject.toml ([tool.ruff])",
    ]


def test_generate_without_adapter_leaves_a_fill_marker(tmp_path: Path):
    repo = Repo.open(tmp_path)
    assert l1_2_gate.generate(repo, dry_run=False) == ["wrote    Makefile"]
    assert "<<FILL:" in (tmp_path / "Makefile").read_text()


def test_generate_dry_run_writes_nothing(python_repo: Path):
    actions = l1_2_gate.generate(Repo.open(python_repo), dry_run=True)
    assert actions == ["would write Makefile", "would append pyproject.toml"]
    assert not (python_repo / "Makefile").exists()
