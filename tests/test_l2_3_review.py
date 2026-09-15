from pathlib import Path

from agentify.checks import l2_3_review
from agentify.contract import FAIL, NA, PASS
from agentify.repo import Repo

REVIEW = """\
name: review
on:
  pull_request:
    types: [opened, synchronize]
jobs:
  review:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions:
      contents: read
      pull-requests: write
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: anthropics/claude-code-action@v1
        with:
          prompt: |
            Read AGENTS.md first. Then review the pull request.
"""

CI = """\
name: ci
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - run: make check
"""


def write(root: Path, **files: str) -> Repo:
    (root / ".github/workflows").mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (root / ".github/workflows" / name).write_text(text)
    return Repo.open(root)


def test_no_workflows_is_not_applicable(tmp_path: Path):
    r = l2_3_review.check(Repo.open(tmp_path))
    assert r.status == NA


def test_a_pull_request_workflow_without_a_prompt_is_ignored(tmp_path: Path):
    assert l2_3_review.check(write(tmp_path, **{"ci.yml": CI})).status == NA


def test_review_workflows_are_found_by_shape_not_name(tmp_path: Path):
    repo = write(tmp_path, **{"claude-review.yml": REVIEW, "ci.yml": CI})
    assert [path for path, _ in l2_3_review.review_workflows(repo)] == [
        ".github/workflows/claude-review.yml"
    ]


def test_good_review_workflow_passes(tmp_path: Path):
    r = l2_3_review.check(write(tmp_path, **{"docs-review.yml": REVIEW}))
    assert r.status == PASS and "docs-review.yml" in r.reason


def test_job_level_contents_write_fails(tmp_path: Path):
    text = REVIEW.replace("      contents: read\n", "      contents: write\n")
    r = l2_3_review.check(write(tmp_path, **{"review.yml": text}))
    assert r.status == FAIL and "contents: write" in r.reason


def test_top_level_contents_write_fails(tmp_path: Path):
    text = REVIEW.replace("jobs:\n", "permissions:\n  contents: write\njobs:\n")
    r = l2_3_review.check(write(tmp_path, **{"review.yml": text}))
    assert r.status == FAIL and "contents: write" in r.reason


def test_job_level_write_all_shorthand_fails(tmp_path: Path):
    text = REVIEW.replace(
        "    permissions:\n      contents: read\n      pull-requests: write\n      id-token: write\n",
        "    permissions: write-all\n",
    )
    assert "permissions: write-all" in text
    r = l2_3_review.check(write(tmp_path, **{"review.yml": text}))
    assert r.status == FAIL and "contents: write" in r.reason


def test_top_level_write_all_shorthand_fails(tmp_path: Path):
    text = REVIEW.replace("jobs:\n", "permissions: write-all\njobs:\n")
    r = l2_3_review.check(write(tmp_path, **{"review.yml": text}))
    assert r.status == FAIL and "contents: write" in r.reason


def test_review_workflow_without_any_permissions_block_fails(tmp_path: Path):
    text = REVIEW.replace(
        "    permissions:\n      contents: read\n      pull-requests: write\n      id-token: write\n",
        "",
    )
    r = l2_3_review.check(write(tmp_path, **{"review.yml": text}))
    assert r.status == FAIL and "permissions" in r.reason


def test_top_level_read_only_permissions_with_no_job_block_passes(tmp_path: Path):
    text = REVIEW.replace(
        "    permissions:\n      contents: read\n      pull-requests: write\n      id-token: write\n",
        "",
    )
    text = text.replace(
        "jobs:\n",
        "permissions:\n  contents: read\n  pull-requests: write\njobs:\n",
    )
    r = l2_3_review.check(write(tmp_path, **{"review.yml": text}))
    assert r.status == PASS


def test_read_all_shorthand_passes(tmp_path: Path):
    text = REVIEW.replace(
        "    permissions:\n      contents: read\n      pull-requests: write\n      id-token: write\n",
        "",
    )
    text = text.replace("jobs:\n", "permissions: read-all\njobs:\n")
    r = l2_3_review.check(write(tmp_path, **{"review.yml": text}))
    assert r.status == PASS


def test_pull_request_target_review_workflow_fails(tmp_path: Path):
    text = REVIEW.replace("  pull_request:\n", "  pull_request_target:\n")
    assert [
        path
        for path, _ in l2_3_review.review_workflows(
            write(tmp_path, **{"review.yml": text})
        )
    ] == [".github/workflows/review.yml"]
    r = l2_3_review.check(write(tmp_path, **{"review.yml": text}))
    assert r.status == FAIL and "pull_request_target" in r.reason


def test_prompt_that_does_not_mention_the_router_fails(tmp_path: Path):
    text = REVIEW.replace("Read AGENTS.md first. ", "")
    r = l2_3_review.check(write(tmp_path, **{"review.yml": text}))
    assert r.status == FAIL and "AGENTS.md" in r.reason


def test_missing_timeout_fails(tmp_path: Path):
    text = REVIEW.replace("    timeout-minutes: 15\n", "")
    r = l2_3_review.check(write(tmp_path, **{"review.yml": text}))
    assert r.status == FAIL and "timeout-minutes" in r.reason


def test_invalid_yaml_anywhere_in_workflows_fails(tmp_path: Path):
    r = l2_3_review.check(write(tmp_path, **{"broken.yml": "on: [\n"}))
    assert r.status == FAIL and "not valid YAML" in r.reason


def test_generate_writes_nothing(python_repo: Path):
    assert l2_3_review.generate(Repo.open(python_repo), dry_run=False) == []
