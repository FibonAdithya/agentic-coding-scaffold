"""L1.4 Authority order: every document the router's source-of-truth list names exists."""

from __future__ import annotations

from agentify.contract import FAIL, PASS, Item, Result
from agentify.docs_refs import GLOB_REFERENCE, REFERENCE, expand_glob, section
from agentify.repo import Repo, write_if_missing
from agentify.templates import render

ID = "L1.4"
HEADING = "Source of truth, in order"


def check(repo: Repo) -> Result:
    text = repo.read("AGENTS.md")
    if text is None:
        return Result(ID, FAIL, "AGENTS.md missing")
    body = section(text, HEADING)
    paths = [m["path"] for m in REFERENCE.finditer(body)]
    globs = [m["pattern"] for m in GLOB_REFERENCE.finditer(body)]
    if not paths and not globs:
        return Result(ID, FAIL, f'AGENTS.md "## {HEADING}" names no documents')
    expanded = {pattern: expand_glob(repo, pattern) for pattern in globs}
    missing = [
        path for path in paths if not repo.contains(path) or not repo.exists(path)
    ] + [pattern for pattern, files in expanded.items() if not files]
    if missing:
        shown = ", ".join(f"`{p}`" for p in missing[:3])
        more = f" (+{len(missing) - 3} more)" if len(missing) > 3 else ""
        return Result(
            ID, FAIL, f"authority list names paths that do not exist: {shown}{more}"
        )
    count = len(paths) + sum(len(files) for files in expanded.values())
    return Result(ID, PASS, f"all {count} documents in the authority list exist")


def generate(repo: Repo, dry_run: bool) -> list[str]:
    return [
        write_if_missing(
            repo, "README.md", render("README.md", project_name=repo.name), dry_run
        )
    ]


ITEM = Item(ID, 1, "Authority order", check, generate)
