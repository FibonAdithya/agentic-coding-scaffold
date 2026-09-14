"""L1.1 Router: AGENTS.md with the six sections, no fill markers, CLAUDE.md deferring."""

from __future__ import annotations

from agentify.contract import FAIL, PASS, Item, Result
from agentify.markdown import lines_outside_fences
from agentify.repo import Repo, write_if_missing
from agentify.templates import render

ID = "L1.1"
REQUIRED_HEADINGS = (
    "What this project is",
    "Source of truth, in order",
    "Invariants",
    'What "done" means',
    "What requires a human",
    "Where to look",
)
FILL = "<<FILL"


def headings(text: str) -> list[str]:
    return [
        line[3:].strip()
        for _, line in lines_outside_fences(text)
        if line.startswith("## ")
    ]


def missing_in_order(found: list[str], required: tuple[str, ...]) -> str | None:
    """The first required heading that is absent or out of order, else None."""
    position = 0
    for want in required:
        try:
            position = found.index(want, position) + 1
        except ValueError:
            return want
    return None


def check(repo: Repo) -> Result:
    text = repo.read("AGENTS.md")
    if text is None:
        return Result(ID, FAIL, "AGENTS.md missing")
    bad = missing_in_order(headings(text), REQUIRED_HEADINGS)
    if bad is not None:
        return Result(
            ID, FAIL, f'AGENTS.md: heading "## {bad}" missing or out of order'
        )
    if FILL in text:
        count = text.count(FILL)
        return Result(
            ID,
            FAIL,
            f"AGENTS.md: {count} <<FILL>> marker(s) remain; run `agentify fill`",
        )
    claude = repo.read("CLAUDE.md")
    if claude is not None and claude.replace("`", "").strip() != "See AGENTS.md.":
        return Result(ID, FAIL, "CLAUDE.md must be absent or exactly 'See AGENTS.md.'")
    return Result(ID, PASS, "router present with all six sections and no fill markers")


def generate(repo: Repo, dry_run: bool) -> list[str]:
    return [
        write_if_missing(
            repo, "AGENTS.md", render("AGENTS.md", project_name=repo.name), dry_run
        ),
        write_if_missing(repo, "CLAUDE.md", render("CLAUDE.md"), dry_run),
    ]


ITEM = Item(ID, 1, "Router", check, generate)
