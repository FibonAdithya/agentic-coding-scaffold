"""L1.5 References resolve: every backticked path, anchor and symbol in the authoritative docs."""

from __future__ import annotations

from agentify.contract import FAIL, PASS, Item, Result
from agentify.docs_refs import authoritative_docs, scan_docs
from agentify.repo import Repo, write_if_missing
from agentify.templates import render

ID = "L1.5"
TEST_FILE = "tests/test_docs_references.py"


def check(repo: Repo) -> Result:
    unresolved = scan_docs(repo)
    if unresolved:
        shown = "; ".join(
            f"{u.doc}:{u.line}: `{u.ref}` -- {u.reason}" for u in unresolved[:3]
        )
        more = f" (+{len(unresolved) - 3} more)" if len(unresolved) > 3 else ""
        return Result(
            ID, FAIL, f"{len(unresolved)} unresolved reference(s): {shown}{more}"
        )
    count = len(authoritative_docs(repo))
    return Result(ID, PASS, f"every reference in {count} authoritative docs resolves")


def generate(repo: Repo, dry_run: bool) -> list[str]:
    if repo.adapter is None or repo.adapter.name != "python":
        return [
            f"skipped  {TEST_FILE} (no language adapter; run `agentify check` instead)"
        ]
    return [
        write_if_missing(
            repo, TEST_FILE, render("test_docs_references.py.tmpl"), dry_run
        )
    ]


ITEM = Item(ID, 1, "References resolve", check, generate)
