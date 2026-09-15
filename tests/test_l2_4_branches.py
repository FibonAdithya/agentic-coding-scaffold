from pathlib import Path

import pytest

from agentify.checks import l2_4_branches
from agentify.contract import FAIL, PASS
from agentify.repo import Repo
from agentify.templates import load

GOOD = """\
name: branch-hygiene
on:
  pull_request:
    types: [closed]
  workflow_dispatch:
    inputs:
      apply:
        type: boolean
        default: false
permissions:
  contents: write
  pull-requests: read
env:
  KEEP_LABEL: keep-branch
jobs:
  prune:
    if: github.event_name == 'workflow_dispatch' || github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - run: echo prune
"""


def write(root: Path, text: str) -> Repo:
    (root / ".github/workflows").mkdir(parents=True, exist_ok=True)
    (root / l2_4_branches.WORKFLOW).write_text(text)
    return Repo.open(root)


def test_missing_workflow_fails(tmp_path: Path):
    r = l2_4_branches.check(Repo.open(tmp_path))
    assert r.status == FAIL and "branch-hygiene.yml missing" in r.reason


def test_good_workflow_passes(tmp_path: Path):
    assert l2_4_branches.check(write(tmp_path, GOOD)).status == PASS


def test_the_shipped_template_passes(tmp_path: Path):
    assert (
        l2_4_branches.check(write(tmp_path, load("branch-hygiene.yml"))).status == PASS
    )


@pytest.mark.parametrize(
    "mutation, expected",
    [
        (("  pull_request:\n    types: [closed]\n", "  push:\n"), "pull_request"),
        (("    types: [closed]\n", "    types: [opened]\n"), "closed"),
        (("  pull_request:\n", "  pull_request_target:\n"), "pull_request_target"),
        (
            (
                "  workflow_dispatch:\n    inputs:\n      apply:\n        type: boolean\n        default: false\n",
                "",
            ),
            "workflow_dispatch",
        ),
        (("  pull-requests: read\n", "  pull-requests: write\n"), "permissions"),
        (
            ("  contents: write\n", "  contents: write\n  issues: write\n"),
            "permissions",
        ),
        (("    timeout-minutes: 10\n", ""), "timeout-minutes"),
        (("github.event.pull_request.merged == true", "true"), "merged == true"),
        (("keep-branch", "other"), "keep-branch"),
    ],
)
def test_each_required_property_is_enforced(tmp_path: Path, mutation, expected):
    old, new = mutation
    assert old in GOOD
    r = l2_4_branches.check(write(tmp_path, GOOD.replace(old, new)))
    assert r.status == FAIL and expected in r.reason


def test_job_level_permissions_override_fails(tmp_path: Path):
    text = GOOD.replace(
        "  prune:\n    if:", "  prune:\n    permissions: write-all\n    if:"
    )
    r = l2_4_branches.check(write(tmp_path, text))
    assert r.status == FAIL and "permissions" in r.reason


def test_second_ungated_job_fails(tmp_path: Path):
    text = GOOD + (
        "  other:\n"
        "    runs-on: ubuntu-latest\n"
        "    timeout-minutes: 5\n"
        "    steps:\n"
        "      - run: echo other\n"
    )
    r = l2_4_branches.check(write(tmp_path, text))
    assert r.status == FAIL and "other" in r.reason and "merged == true" in r.reason


def test_invalid_yaml_fails_cleanly(tmp_path: Path):
    r = l2_4_branches.check(write(tmp_path, "on: [\n"))
    assert r.status == FAIL and "not valid YAML" in r.reason


def test_generate_writes_the_template_once(python_repo: Path):
    repo = Repo.open(python_repo)
    assert l2_4_branches.generate(repo, dry_run=False) == [
        f"wrote    {l2_4_branches.WORKFLOW}"
    ]
    assert l2_4_branches.check(repo).status == PASS
    assert l2_4_branches.generate(repo, dry_run=False) == [
        f"exists   {l2_4_branches.WORKFLOW}"
    ]


def test_template_script_never_uses_a_blind_delete(tmp_path: Path):
    """The whole point: nothing deletes without passing the skip chain."""
    text = load("branch-hygiene.yml")
    assert text.count("git/refs/heads/") == 1
    assert 'if [ "$APPLY" = true ]; then' in text
    assert "pull_request_target" not in text
