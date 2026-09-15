"""--level must stay inside 1..max_level(): adopt must never stamp a level
this codebase does not implement, and check must never run one."""

from pathlib import Path

import pytest

from agentify.cli import main
from agentify.contract import max_level, run_adopt, run_checks
from agentify.repo import Repo


def test_check_level_zero_is_rejected_by_argparse(python_repo: Path):
    with pytest.raises(SystemExit) as exc:
        main(["check", str(python_repo), "--level", "0"])
    assert exc.value.code == 2


def test_adopt_level_above_max_is_rejected_by_argparse(python_repo: Path):
    with pytest.raises(SystemExit) as exc:
        main(["adopt", str(python_repo), "--level", str(max_level() + 1)])
    assert exc.value.code == 2


def test_run_adopt_rejects_an_out_of_range_level(tmp_path: Path):
    top = max_level()
    with pytest.raises(ValueError, match=rf"level must be 1\.\.{top}"):
        run_adopt(Repo.open(tmp_path), top + 1, False)


def test_run_checks_rejects_an_out_of_range_level(tmp_path: Path):
    top = max_level()
    with pytest.raises(ValueError, match=rf"level must be 1\.\.{top}"):
        run_checks(Repo.open(tmp_path), 0)
