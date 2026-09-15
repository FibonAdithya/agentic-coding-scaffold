"""L2.4 Branch hygiene: a merged branch is deleted when it is finished, by rule."""

from __future__ import annotations

import yaml

from agentify.checks.l1_3_ci import triggers
from agentify.contract import FAIL, PASS, Item, Result
from agentify.repo import Repo, write_if_missing
from agentify.templates import render

ID = "L2.4"
WORKFLOW = ".github/workflows/branch-hygiene.yml"
PERMISSIONS = {"contents": "write", "pull-requests": "read"}
KEEP_LABEL = "keep-branch"
MERGED_GATE = "merged == true"


def check(repo: Repo) -> Result:
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
    if "pull_request_target" in on:
        return Result(
            ID, FAIL, f"{WORKFLOW}: must never trigger on pull_request_target"
        )
    if "pull_request" not in on:
        return Result(ID, FAIL, f"{WORKFLOW}: no pull_request trigger")
    if "closed" not in (on["pull_request"].get("types") or []):
        return Result(
            ID, FAIL, f"{WORKFLOW}: pull_request trigger must include type closed"
        )
    if "workflow_dispatch" not in on:
        return Result(
            ID, FAIL, f"{WORKFLOW}: no workflow_dispatch trigger for the sweep"
        )
    if workflow.get("permissions") != PERMISSIONS:
        return Result(
            ID,
            FAIL,
            f"{WORKFLOW}: top-level permissions must be exactly contents: write and pull-requests: read",
        )
    jobs = workflow.get("jobs") or {}
    for name, job in jobs.items():
        if "timeout-minutes" not in (job or {}):
            return Result(ID, FAIL, f"{WORKFLOW}: job {name} has no timeout-minutes")
    if not any(MERGED_GATE in str((job or {}).get("if", "")) for job in jobs.values()):
        return Result(ID, FAIL, f"{WORKFLOW}: no job is gated on `{MERGED_GATE}`")
    if KEEP_LABEL not in text:
        return Result(ID, FAIL, f"{WORKFLOW}: does not honour the `{KEEP_LABEL}` label")
    return Result(
        ID, PASS, "branch-hygiene.yml deletes only finished branches, by rule"
    )


def generate(repo: Repo, dry_run: bool) -> list[str]:
    return [write_if_missing(repo, WORKFLOW, render("branch-hygiene.yml"), dry_run)]


ITEM = Item(ID, 2, "Branch hygiene", check, generate)
