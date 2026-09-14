"""The contract registry and the two operations over it: check and adopt."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from agentify.config import ensure_level
from agentify.repo import Repo, write_if_missing
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
    from agentify.checks import l1_1_router, l1_2_gate, l1_3_ci

    return [l1_1_router.ITEM, l1_2_gate.ITEM, l1_3_ci.ITEM]


def max_level() -> int:
    return max((item.level for item in registry()), default=1)


def run_checks(repo: Repo, level: int) -> list[Result]:
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
    return actions
