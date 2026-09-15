"""L2.2 Bug channel: the router names a filing label and notify.yml routes it."""

from __future__ import annotations

import re

import yaml

from agentify.checks.l1_3_ci import triggers
from agentify.contract import FAIL, PASS, Item, Result
from agentify.docs_refs import section
from agentify.repo import Repo, write_if_missing
from agentify.templates import render

ID = "L2.2"
WORKFLOW = ".github/workflows/notify.yml"
ROUTER_SECTION = "What requires a human"
LABEL_ARG = re.compile(r"--label[ =]+([A-Za-z0-9_.-]+)")


def router_label(router: str) -> str | None:
    """The label the router's filing command uses, or None."""
    match = LABEL_ARG.search(section(router, ROUTER_SECTION))
    return match.group(1) if match else None


def check(repo: Repo) -> Result:
    router = repo.read("AGENTS.md")
    if router is None:
        return Result(ID, FAIL, "AGENTS.md missing")
    label = router_label(router)
    if label is None:
        return Result(
            ID,
            FAIL,
            f'AGENTS.md: "{ROUTER_SECTION}" names no filing label (`gh issue create --label <name>`)',
        )
    text = repo.read(WORKFLOW)
    if text is None:
        return Result(ID, FAIL, f"{WORKFLOW} missing")
    try:
        workflow = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return Result(ID, FAIL, f"{WORKFLOW}: not valid YAML: {exc}")
    if not isinstance(workflow, dict):
        return Result(ID, FAIL, f"{WORKFLOW}: not a YAML mapping")
    on = triggers(workflow)
    if "issues" not in on:
        return Result(ID, FAIL, f"{WORKFLOW}: no issues trigger")
    types = on["issues"].get("types")
    if types is not None and "opened" not in types:
        return Result(ID, FAIL, f"{WORKFLOW}: issues trigger does not include opened")
    if workflow.get("permissions") != {"issues": "write"}:
        return Result(
            ID, FAIL, f"{WORKFLOW}: top-level permissions must be exactly issues: write"
        )
    jobs = workflow.get("jobs") or {}
    for name, job in jobs.items():
        job = job or {}
        if "timeout-minutes" not in job:
            return Result(ID, FAIL, f"{WORKFLOW}: job {name} has no timeout-minutes")
        if "permissions" in job:
            return Result(
                ID,
                FAIL,
                f"{WORKFLOW}: job {name} declares permissions; this workflow's "
                "permissions are set at the top level only",
            )
    gates = [str((job or {}).get("if", "")) for job in jobs.values()]
    if not any(label in gate for gate in gates):
        return Result(
            ID,
            FAIL,
            f"{WORKFLOW}: no job is gated on the label the router names ({label})",
        )
    return Result(ID, PASS, f"router files with `{label}` and notify.yml routes it")


def generate(repo: Repo, dry_run: bool) -> list[str]:
    return [write_if_missing(repo, WORKFLOW, render("notify.yml"), dry_run)]


ITEM = Item(ID, 2, "Bug channel", check, generate)
