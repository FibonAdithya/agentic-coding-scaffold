from pathlib import Path

from agentify.checks import l1_1_router
from agentify.contract import FAIL, PASS
from agentify.repo import Repo
from helpers import fill_all

GOOD = """\
# Agent guide

## What this project is
x
## Source of truth, in order
x
## Invariants
x
## What "done" means
x
## What requires a human
x
## Where to look
x
"""


def test_missing_router_fails(tmp_path: Path):
    r = l1_1_router.check(Repo.open(tmp_path))
    assert r.status == FAIL and "AGENTS.md missing" in r.reason


def test_complete_router_passes(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text(GOOD)
    assert l1_1_router.check(Repo.open(tmp_path)).status == PASS


def test_extra_headings_are_allowed_but_order_is_enforced(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text(
        GOOD.replace("## Invariants\n", "## Extra\nx\n## Invariants\n")
    )
    assert l1_1_router.check(Repo.open(tmp_path)).status == PASS
    swapped = GOOD.replace("## Invariants\nx\n", "").replace(
        "## Where to look\n", "## Where to look\nx\n## Invariants\n"
    )
    (tmp_path / "AGENTS.md").write_text(swapped)
    r = l1_1_router.check(Repo.open(tmp_path))
    assert r.status == FAIL and "missing or out of order" in r.reason
    (tmp_path / "AGENTS.md").write_text(GOOD.replace("## Invariants\nx\n", ""))
    r = l1_1_router.check(Repo.open(tmp_path))
    assert r.status == FAIL and '"## Invariants" missing or out of order' in r.reason


def test_a_remaining_fill_marker_fails(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text(GOOD + "\n<<FILL: something>>\n")
    r = l1_1_router.check(Repo.open(tmp_path))
    assert r.status == FAIL and "1 <<FILL>> marker" in r.reason


def test_claude_md_must_defer_to_agents_md(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text(GOOD)
    (tmp_path / "CLAUDE.md").write_text("See `AGENTS.md`.\n")
    assert l1_1_router.check(Repo.open(tmp_path)).status == PASS
    (tmp_path / "CLAUDE.md").write_text("# Real instructions here\n")
    r = l1_1_router.check(Repo.open(tmp_path))
    assert r.status == FAIL and "CLAUDE.md" in r.reason


def test_generate_writes_router_with_markers_then_passes_once_filled(python_repo: Path):
    repo = Repo.open(python_repo)
    actions = l1_1_router.generate(repo, dry_run=False)
    assert actions == ["wrote    AGENTS.md", "wrote    CLAUDE.md"]
    text = (python_repo / "AGENTS.md").read_text()
    assert (
        l1_1_router.missing_in_order(
            l1_1_router.headings(text), l1_1_router.REQUIRED_HEADINGS
        )
        is None
    )
    assert text.count("<<FILL:") >= 4
    assert "agent-reported" in text
    assert l1_1_router.check(repo).status == FAIL
    fill_all(python_repo)
    assert l1_1_router.check(repo).status == PASS
    assert l1_1_router.generate(repo, dry_run=False) == [
        "exists   AGENTS.md",
        "exists   CLAUDE.md",
    ]


def test_headings_inside_fenced_code_do_not_count(tmp_path: Path):
    text = GOOD.replace("## Invariants\nx\n", "") + "\n```\n## Invariants\n```\n"
    (tmp_path / "AGENTS.md").write_text(text)
    r = l1_1_router.check(Repo.open(tmp_path))
    assert r.status == FAIL and '"## Invariants" missing or out of order' in r.reason
