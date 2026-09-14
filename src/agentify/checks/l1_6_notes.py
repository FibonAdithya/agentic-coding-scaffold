"""L1.6 AI notes quarantined: docs/ai/README.md declares itself non-authoritative."""

from __future__ import annotations

from agentify.contract import FAIL, PASS, Item, Result
from agentify.repo import Repo, write_if_missing
from agentify.templates import render

ID = "L1.6"
README = "docs/ai/README.md"
PHRASE = "not the source of truth"


def check(repo: Repo) -> Result:
    text = repo.read(README)
    if text is None:
        return Result(ID, FAIL, f"{README} missing")
    if PHRASE not in text.lower():
        return Result(ID, FAIL, f'{README} must state that its contents are "{PHRASE}"')
    return Result(ID, PASS, f"{README} declares docs/ai/ non-authoritative")


def generate(repo: Repo, dry_run: bool) -> list[str]:
    return [
        write_if_missing(repo, README, render("docs-ai-README.md"), dry_run),
        write_if_missing(repo, "docs/ai/specs/.gitkeep", "", dry_run),
        write_if_missing(repo, "docs/ai/plans/.gitkeep", "", dry_run),
    ]


ITEM = Item(ID, 1, "AI notes quarantined", check, generate)
