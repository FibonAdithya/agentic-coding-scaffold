"""L1.4 Authority order: every document the router's source-of-truth list names exists."""

from __future__ import annotations

from agentify.contract import FAIL, PASS, Item, Result
from agentify.docs_refs import REFERENCE, section
from agentify.repo import Repo, write_if_missing
from agentify.templates import render

ID = "L1.4"
HEADING = "Source of truth, in order"


def check(repo: Repo) -> Result:
    text = repo.read("AGENTS.md")
    if text is None:
        return Result(ID, FAIL, "AGENTS.md missing")
    listed = [m["path"] for m in REFERENCE.finditer(section(text, HEADING))]
    if not listed:
        return Result(ID, FAIL, f'AGENTS.md "## {HEADING}" names no documents')
    missing = [
        path for path in listed if not repo.contains(path) or not repo.exists(path)
    ]
    if missing:
        shown = ", ".join(f"`{p}`" for p in missing[:3])
        more = f" (+{len(missing) - 3} more)" if len(missing) > 3 else ""
        return Result(
            ID, FAIL, f"authority list names paths that do not exist: {shown}{more}"
        )
    return Result(ID, PASS, f"all {len(listed)} documents in the authority list exist")


def generate(repo: Repo, dry_run: bool) -> list[str]:
    return [
        write_if_missing(
            repo, "README.md", render("README.md", project_name=repo.name), dry_run
        )
    ]


ITEM = Item(ID, 1, "Authority order", check, generate)
