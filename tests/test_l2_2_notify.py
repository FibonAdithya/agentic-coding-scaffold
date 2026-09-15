from pathlib import Path

import pytest

from agentify.checks import l2_2_notify
from agentify.contract import FAIL, PASS
from agentify.repo import Repo

ROUTER = """\
# Agent guide

## What requires a human

To report a bug in this project, file an issue with the `agent-reported`
label:

    gh issue create --label agent-reported --title "..." --body "..."

## Where to look
"""

GOOD = """\
name: notify
on:
  issues:
    types: [opened]
permissions:
  issues: write
jobs:
  assign:
    if: >-
      contains(github.event.issue.labels.*.name, 'agent-reported')
      || contains(github.event.issue.labels.*.name, 'auto-bug')
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - run: echo assign
"""


def write(root: Path, workflow: str | None, router: str | None = ROUTER) -> Repo:
    if workflow is not None:
        (root / ".github/workflows").mkdir(parents=True, exist_ok=True)
        (root / l2_2_notify.WORKFLOW).write_text(workflow)
    if router is not None:
        (root / "AGENTS.md").write_text(router)
    return Repo.open(root)


def test_router_label_reads_the_filing_command():
    assert l2_2_notify.router_label(ROUTER) == "agent-reported"
    assert (
        l2_2_notify.router_label("# x\n\n## What requires a human\n\nnothing\n") is None
    )
    # The label must come from that section, not from anywhere in the file.
    elsewhere = "# x\n\n## Where to look\n\n    gh issue create --label oops\n"
    assert l2_2_notify.router_label(elsewhere) is None


def test_missing_router_fails(tmp_path: Path):
    r = l2_2_notify.check(write(tmp_path, GOOD, router=None))
    assert r.status == FAIL and "AGENTS.md missing" in r.reason


def test_router_without_a_label_fails(tmp_path: Path):
    r = l2_2_notify.check(
        write(tmp_path, GOOD, router="# x\n\n## What requires a human\n\n")
    )
    assert r.status == FAIL and "names no filing label" in r.reason


def test_missing_workflow_fails(tmp_path: Path):
    r = l2_2_notify.check(write(tmp_path, None))
    assert r.status == FAIL and "notify.yml missing" in r.reason


def test_good_workflow_passes(tmp_path: Path):
    assert l2_2_notify.check(write(tmp_path, GOOD)).status == PASS


@pytest.mark.parametrize(
    "mutation, expected",
    [
        (("  issues:\n    types: [opened]\n", "  push:\n"), "issues"),
        (("    types: [opened]\n", "    types: [labeled]\n"), "opened"),
        (("  issues: write\n", "  issues: write\n  contents: write\n"), "permissions"),
        (("    timeout-minutes: 5\n", ""), "timeout-minutes"),
        (("'agent-reported'", "'other-label'"), "agent-reported"),
    ],
)
def test_each_required_property_is_enforced(tmp_path: Path, mutation, expected):
    old, new = mutation
    assert old in GOOD
    r = l2_2_notify.check(write(tmp_path, GOOD.replace(old, new)))
    assert r.status == FAIL and expected in r.reason


def test_job_level_permissions_override_fails(tmp_path: Path):
    text = GOOD.replace(
        "  assign:\n    if:", "  assign:\n    permissions: write-all\n    if:"
    )
    r = l2_2_notify.check(write(tmp_path, text))
    assert r.status == FAIL and "permissions" in r.reason


def test_issues_trigger_without_types_is_accepted(tmp_path: Path):
    text = GOOD.replace("  issues:\n    types: [opened]\n", "  issues:\n")
    assert l2_2_notify.check(write(tmp_path, text)).status == PASS


def test_invalid_yaml_fails_cleanly(tmp_path: Path):
    r = l2_2_notify.check(write(tmp_path, "on: [\n"))
    assert r.status == FAIL and "not valid YAML" in r.reason


def test_generate_writes_the_template_once(python_repo: Path):
    repo = Repo.open(python_repo)
    assert l2_2_notify.generate(repo, dry_run=False) == [
        f"wrote    {l2_2_notify.WORKFLOW}"
    ]
    (python_repo / "AGENTS.md").write_text(ROUTER)
    assert l2_2_notify.check(repo).status == PASS
    assert l2_2_notify.generate(repo, dry_run=False) == [
        f"exists   {l2_2_notify.WORKFLOW}"
    ]
