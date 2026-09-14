"""IMPORTANT fix: --level accepted any integer, so `adopt --level 3` could
stamp a level this codebase does not implement yet (only level 1 exists)."""

from pathlib import Path

import pytest

from agentify.cli import main
from agentify.contract import max_level, run_adopt, run_checks
from agentify.repo import Repo


def test_check_level_zero_is_rejected_by_argparse(python_repo: Path, capsys):
    assert max_level() == 1, "this test assumes level 2 does not exist yet"
    with pytest.raises(SystemExit) as exc:
        main(["check", str(python_repo), "--level", "0"])
    assert exc.value.code == 2


def test_adopt_level_above_max_is_rejected_by_argparse(python_repo: Path):
    assert max_level() == 1
    with pytest.raises(SystemExit) as exc:
        main(["adopt", str(python_repo), "--level", "3"])
    assert exc.value.code == 2


def test_run_adopt_rejects_an_out_of_range_level(tmp_path: Path):
    assert max_level() == 1
    with pytest.raises(ValueError, match=r"level must be 1\.\.1"):
        run_adopt(Repo.open(tmp_path), 3, False)


def test_run_checks_rejects_an_out_of_range_level(tmp_path: Path):
    assert max_level() == 1
    with pytest.raises(ValueError, match=r"level must be 1\.\.1"):
        run_checks(Repo.open(tmp_path), 0)
