"""The contract registry and the two operations over it: check and adopt."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from agentify import AGENTIFY_PIN
from agentify.config import ensure_level
from agentify.repo import Repo, append_text, write_if_missing
from agentify.templates import render

PASS = "pass"
FAIL = "fail"
NA = "n/a"


@dataclass(frozen=True)
class Result:
    item: str
    status: str
    reason: str


@dataclass(frozen=True)
class Item:
    id: str
    level: int
    title: str
    check: Callable[[Repo], Result]
    generate: Callable[[Repo, bool], list[str]]


def registry() -> list[Item]:
    """Every contract item, in id order. Imported lazily: items import this module."""
    from agentify.checks import (
        l1_1_router,
        l1_2_gate,
        l1_3_ci,
        l1_4_authority,
        l1_5_references,
        l1_6_notes,
        l1_7_ignore,
        l2_1_setup,
    )

    return [
        l1_1_router.ITEM,
        l1_2_gate.ITEM,
        l1_3_ci.ITEM,
        l1_4_authority.ITEM,
        l1_5_references.ITEM,
        l1_6_notes.ITEM,
        l1_7_ignore.ITEM,
        l2_1_setup.ITEM,
    ]


def max_level() -> int:
    return max((item.level for item in registry()), default=1)


def _check_level_in_range(level: int) -> None:
    top = max_level()
    if not 1 <= level <= top:
        raise ValueError(f"level must be 1..{top}")


def run_checks(repo: Repo, level: int) -> list[Result]:
    _check_level_in_range(level)
    results: list[Result] = []
    for item in registry():
        if item.level > level:
            continue
        try:
            results.append(item.check(repo))
        except (
            Exception
        ) as exc:  # a crashed check is a failed check, and must not hide the rest
            results.append(
                Result(item.id, FAIL, f"check raised {type(exc).__name__}: {exc}")
            )
    return results


def run_adopt(repo: Repo, level: int, dry_run: bool) -> list[str]:
    _check_level_in_range(level)
    actions: list[str] = []
    for item in registry():
        if item.level > level:
            continue
        actions.extend(item.generate(repo, dry_run))
    actions.append(ensure_level(repo.root, level, dry_run))
    if repo.adapter is not None and repo.adapter.name == "python":
        actions.append(
            write_if_missing(
                repo, "tests/test_contract.py", render("test_contract.py.tmpl"), dry_run
            )
        )
        actions.append(_ensure_requirements_dev(repo, dry_run))
    return actions


def _ensure_requirements_dev(repo: Repo, dry_run: bool) -> str:
    """A fourth in-place-edit exception (see AGENTS.md Invariant 1): the
    converted repo must install agentify itself to run its own contract
    self-check, so the pin is appended to an existing file rather than
    silently skipped."""
    rel = "requirements-dev.txt"
    if not repo.path(rel).exists():
        return write_if_missing(
            repo, rel, render(rel, agentify_pin=AGENTIFY_PIN), dry_run
        )
    existing = repo.read(rel) or ""
    if "agentify @" in existing:
        return f"exists   {rel} (agentify pinned)"
    return append_text(repo, rel, f"# agentify\n{AGENTIFY_PIN}\n", dry_run)
