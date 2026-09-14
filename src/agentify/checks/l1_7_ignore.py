"""L1.7 Ignore hygiene: agent scratch state and tool caches never reach a commit."""

from __future__ import annotations

from agentify.contract import FAIL, PASS, Item, Result
from agentify.repo import Repo, append_text

ID = "L1.7"
BASE_PATTERNS = (
    ".superpowers/",
    ".claude/worktrees/",
    ".claude/settings.local.json",
    ".agentify/",
)
HEADER = "# agentify: agent scratch state and tool caches"


def required(repo: Repo) -> list[str]:
    extra = repo.adapter.ignore_patterns() if repo.adapter is not None else []
    return [*BASE_PATTERNS, *extra]


def missing(repo: Repo) -> list[str]:
    text = repo.read(".gitignore") or ""
    present = {
        line.strip() for line in text.splitlines() if not line.lstrip().startswith("#")
    }
    return [pattern for pattern in required(repo) if pattern not in present]


def check(repo: Repo) -> Result:
    absent = missing(repo)
    if absent:
        return Result(
            ID, FAIL, f".gitignore lacks {len(absent)} pattern(s): {', '.join(absent)}"
        )
    return Result(
        ID, PASS, f".gitignore covers all {len(required(repo))} required patterns"
    )


def generate(repo: Repo, dry_run: bool) -> list[str]:
    absent = missing(repo)
    if not absent:
        return ["exists   .gitignore (all patterns present)"]
    block = HEADER + "\n" + "\n".join(absent) + "\n"
    return [append_text(repo, ".gitignore", block, dry_run)]


ITEM = Item(ID, 1, "Ignore hygiene", check, generate)
