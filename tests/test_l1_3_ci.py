from pathlib import Path

import pytest
import yaml

from agentify.checks import l1_3_ci
from agentify.contract import FAIL, PASS
from agentify.repo import Repo

GOOD = """\
name: ci
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  check:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - run: make check
"""


def write(root: Path, text: str) -> Repo:
    (root / ".github/workflows").mkdir(parents=True, exist_ok=True)
    (root / l1_3_ci.WORKFLOW).write_text(text)
    return Repo.open(root)


def test_missing_workflow_fails(tmp_path: Path):
    r = l1_3_ci.check(Repo.open(tmp_path))
    assert r.status == FAIL and "ci.yml missing" in r.reason


def test_good_workflow_passes(tmp_path: Path):
    assert l1_3_ci.check(write(tmp_path, GOOD)).status == PASS


def test_triggers_handles_the_on_key_parsed_as_true():
    assert l1_3_ci.triggers(yaml.safe_load("on: [push, pull_request]\n")) == {
        "push": {},
        "pull_request": {},
    }
    assert l1_3_ci.triggers(yaml.safe_load("on: push\n")) == {"push": {}}
    assert l1_3_ci.triggers(yaml.safe_load(GOOD))["push"] == {"branches": ["main"]}


@pytest.mark.parametrize(
    "mutation, expected",
    [
        (("  pull_request:\n", ""), "pull_request"),
        (("    branches: [main]\n", "    branches: [dev]\n"), "push to main"),
        (("  contents: read\n", "  contents: write\n"), "permissions"),
        (
            (
                "concurrency:\n  group: ci-${{ github.ref }}\n  cancel-in-progress: true\n",
                "",
            ),
            "concurrency",
        ),
        (("    timeout-minutes: 15\n", ""), "timeout-minutes"),
        (("      - run: make check\n", "      - run: pytest\n"), "make check"),
        (
            (
                "      - uses: actions/checkout@v4\n",
                "      # <<FILL: install>>\n      - uses: actions/checkout@v4\n",
            ),
            "<<FILL>>",
        ),
    ],
)
def test_each_required_property_is_enforced(tmp_path: Path, mutation, expected):
    old, new = mutation
    assert old in GOOD
    r = l1_3_ci.check(write(tmp_path, GOOD.replace(old, new)))
    assert r.status == FAIL and expected in r.reason


def test_push_without_branch_filter_is_accepted(tmp_path: Path):
    assert (
        l1_3_ci.check(
            write(tmp_path, GOOD.replace("    branches: [main]\n", ""))
        ).status
        == PASS
    )


def test_generate_for_python_writes_a_workflow_that_passes(python_repo: Path):
    repo = Repo.open(python_repo)
    assert l1_3_ci.generate(repo, dry_run=False) == [
        "wrote    .github/workflows/ci.yml"
    ]
    text = (python_repo / l1_3_ci.WORKFLOW).read_text()
    assert (
        "agentify @ git+https://github.com/FibonAdithya/agentic-coding@v0.1.0" in text
    )
    assert l1_3_ci.check(repo).status == PASS
    assert l1_3_ci.generate(repo, dry_run=False) == [
        "exists   .github/workflows/ci.yml"
    ]


def test_null_steps_fail_cleanly(tmp_path: Path):
    null_steps_workflow = GOOD.replace(
        "    steps:\n      - uses: actions/checkout@v4\n      - run: make check\n",
        "    steps:\n",
    )
    r = l1_3_ci.check(write(tmp_path, null_steps_workflow))
    assert r.status == FAIL and "make check" in r.reason


def test_null_job_fails_cleanly(tmp_path: Path):
    null_job_workflow = """\
name: ci
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  check:
"""
    r = l1_3_ci.check(write(tmp_path, null_job_workflow))
    assert r.status == FAIL and "timeout-minutes" in r.reason


def test_generate_without_adapter_leaves_a_fill_marker(tmp_path: Path):
    repo = Repo.open(tmp_path)
    l1_3_ci.generate(repo, dry_run=False)
    r = l1_3_ci.check(repo)
    assert r.status == FAIL and "<<FILL>>" in r.reason
