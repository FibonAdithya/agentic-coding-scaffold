"""L1 CRITICAL fix: adopt writes requirements-dev.txt so a converted repo can
install agentify itself and run its own contract self-check."""

from pathlib import Path

from agentify import AGENTIFY_PIN
from agentify.contract import run_adopt
from agentify.repo import Repo

REL = "requirements-dev.txt"


def test_missing_requirements_dev_is_written_with_the_pin(python_repo: Path):
    actions = run_adopt(Repo.open(python_repo), level=1, dry_run=False)
    assert f"wrote    {REL}" in actions
    text = (python_repo / REL).read_text()
    assert AGENTIFY_PIN in text
    assert "ruff" in text and "pytest" in text


def test_existing_requirements_dev_without_pin_gets_the_pin_appended(
    python_repo: Path,
):
    (python_repo / REL).write_text("ruff\npytest\n")
    actions = run_adopt(Repo.open(python_repo), level=1, dry_run=False)
    assert f"appended {REL}" in actions
    text = (python_repo / REL).read_text()
    assert "ruff\npytest\n" in text
    assert "# agentify" in text
    assert AGENTIFY_PIN in text


def test_existing_requirements_dev_with_pin_is_left_alone(python_repo: Path):
    original = f"ruff\npytest\n{AGENTIFY_PIN}\n"
    (python_repo / REL).write_text(original)
    actions = run_adopt(Repo.open(python_repo), level=1, dry_run=False)
    assert f"exists   {REL} (agentify pinned)" in actions
    assert (python_repo / REL).read_text() == original
