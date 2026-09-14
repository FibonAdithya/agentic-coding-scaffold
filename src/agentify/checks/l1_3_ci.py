"""L1.3 CI runs the gate: ci.yml runs `make check` with least privilege."""

from __future__ import annotations

from typing import Any

import yaml

from agentify import AGENTIFY_PIN
from agentify.contract import FAIL, PASS, Item, Result
from agentify.repo import Repo, write_if_missing
from agentify.templates import render

ID = "L1.3"
WORKFLOW = ".github/workflows/ci.yml"

NO_ADAPTER_STEPS = """\
      # <<FILL: install the toolchain and the project's dependencies here, then delete this marker>>
"""


def triggers(workflow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """The `on:` block as a dict. PyYAML parses the bare key `on` as True."""
    on = workflow.get("on", workflow.get(True))
    if isinstance(on, str):
        return {on: {}}
    if isinstance(on, list):
        return {name: {} for name in on}
    if isinstance(on, dict):
        return {name: (value or {}) for name, value in on.items()}
    return {}


def check(repo: Repo) -> Result:
    text = repo.read(WORKFLOW)
    if text is None:
        return Result(ID, FAIL, f"{WORKFLOW} missing")
    if "<<FILL" in text:
        return Result(ID, FAIL, f"{WORKFLOW}: a <<FILL>> marker remains")
    try:
        workflow = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return Result(ID, FAIL, f"{WORKFLOW}: not valid YAML: {exc}")
    on = triggers(workflow)
    if "pull_request" not in on:
        return Result(ID, FAIL, f"{WORKFLOW}: no pull_request trigger")
    branches = on.get("push", {}).get("branches") if "push" in on else None
    if "push" not in on or (branches is not None and "main" not in branches):
        return Result(ID, FAIL, f"{WORKFLOW}: no push to main trigger")
    if workflow.get("permissions") != {"contents": "read"}:
        return Result(
            ID,
            FAIL,
            f"{WORKFLOW}: top-level permissions must be exactly contents: read",
        )
    concurrency = workflow.get("concurrency")
    if (
        not isinstance(concurrency, dict)
        or concurrency.get("cancel-in-progress") is not True
    ):
        return Result(
            ID,
            FAIL,
            f"{WORKFLOW}: concurrency with cancel-in-progress: true is required",
        )
    jobs = workflow.get("jobs") or {}
    for name, job in jobs.items():
        job = job or {}
        if "timeout-minutes" not in job:
            return Result(ID, FAIL, f"{WORKFLOW}: job {name} has no timeout-minutes")
    runs = [
        str(step.get("run", ""))
        for job in jobs.values()
        for step in (job or {}).get("steps") or []
    ]
    if not any("make check" in run for run in runs):
        return Result(ID, FAIL, f"{WORKFLOW}: no step runs `make check`")
    return Result(
        ID, PASS, "ci.yml runs `make check` on PRs and main with read-only permissions"
    )


def generate(repo: Repo, dry_run: bool) -> list[str]:
    adapter = repo.adapter
    steps = (
        adapter.ci_setup_steps(AGENTIFY_PIN)
        if adapter is not None
        else NO_ADAPTER_STEPS
    )
    return [
        write_if_missing(repo, WORKFLOW, render("ci.yml", setup_steps=steps), dry_run)
    ]


ITEM = Item(ID, 1, "CI runs the gate", check, generate)
