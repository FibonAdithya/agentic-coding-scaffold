"""L2.3 Review bots (optional): a model that reviews PRs reads the router
first and can never push."""

from __future__ import annotations

from typing import Any

import yaml

from agentify.checks.l1_3_ci import triggers
from agentify.contract import FAIL, NA, PASS, Item, Result
from agentify.repo import Repo

ID = "L2.3"
WORKFLOWS_DIR = ".github/workflows"


class WorkflowError(ValueError):
    pass


def _prompts(workflow: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for job in (workflow.get("jobs") or {}).values():
        for step in (job or {}).get("steps") or []:
            with_ = (step or {}).get("with") or {}
            if isinstance(with_, dict) and "prompt" in with_:
                out.append(str(with_["prompt"]))
    return out


def review_workflows(repo: Repo) -> list[tuple[str, dict[str, Any]]]:
    """(relative path, parsed) for every pull_request workflow with a prompt step.

    Raises WorkflowError on a file that is not a YAML mapping: a workflow
    that does not parse cannot be classified, and GitHub would reject it too.
    """
    found: list[tuple[str, dict[str, Any]]] = []
    directory = repo.path(WORKFLOWS_DIR)
    if not directory.is_dir():
        return found
    for path in sorted(directory.iterdir()):
        if path.suffix not in (".yml", ".yaml") or not path.is_file():
            continue
        rel = f"{WORKFLOWS_DIR}/{path.name}"
        try:
            workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise WorkflowError(f"{rel}: not valid YAML: {exc}") from exc
        if not isinstance(workflow, dict):
            raise WorkflowError(f"{rel}: not a YAML mapping")
        if "pull_request" in triggers(workflow) and _prompts(workflow):
            found.append((rel, workflow))
    return found


def _grants_contents_write(permissions: Any) -> bool:
    return isinstance(permissions, dict) and permissions.get("contents") == "write"


def check(repo: Repo) -> Result:
    try:
        workflows = review_workflows(repo)
    except WorkflowError as exc:
        return Result(ID, FAIL, str(exc))
    if not workflows:
        return Result(ID, NA, "no pull_request workflow with a prompt step")
    for rel, workflow in workflows:
        if _grants_contents_write(workflow.get("permissions")):
            return Result(
                ID, FAIL, f"{rel}: top-level permissions grant contents: write"
            )
        for name, job in (workflow.get("jobs") or {}).items():
            job = job or {}
            if _grants_contents_write(job.get("permissions")):
                return Result(ID, FAIL, f"{rel}: job {name} grants contents: write")
            if "timeout-minutes" not in job:
                return Result(ID, FAIL, f"{rel}: job {name} has no timeout-minutes")
        if not all("AGENTS.md" in prompt for prompt in _prompts(workflow)):
            return Result(
                ID, FAIL, f"{rel}: a prompt does not tell the model to read AGENTS.md"
            )
    names = ", ".join(rel.removeprefix(f"{WORKFLOWS_DIR}/") for rel, _ in workflows)
    return Result(
        ID, PASS, f"review workflows read the router and cannot push: {names}"
    )


def generate(repo: Repo, dry_run: bool) -> list[str]:
    """Nothing to write: review bots are optional and agent-specific."""
    return []


ITEM = Item(ID, 2, "Review bots", check, generate)
