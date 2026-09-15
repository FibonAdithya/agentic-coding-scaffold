"""L2.1 Setup: one idempotent `make setup`, named in the router."""

from __future__ import annotations

import re
import shutil
import subprocess

from agentify.checks.l1_2_gate import MAKE_TIMEOUT_S
from agentify.contract import FAIL, PASS, Item, Result
from agentify.docs_refs import section
from agentify.repo import Repo

ID = "L2.1"
TEMPLATE = "src/agentify/templates/Makefile"
ROW_TEXT = "make setup"
ROUTER_SECTION = "Where to look"


def check(repo: Repo) -> Result:
    text = repo.read("Makefile")
    if text is None:
        return Result(ID, FAIL, "Makefile missing")
    if not re.search(r"(?m)^setup\s*:", text):
        return Result(
            ID,
            FAIL,
            f"Makefile: no `setup` target; copy it from {TEMPLATE} "
            "(the Python adapter's gate body carries one)",
        )
    router = repo.read("AGENTS.md")
    if router is None:
        return Result(ID, FAIL, "AGENTS.md missing")
    if ROW_TEXT not in section(router, ROUTER_SECTION):
        return Result(
            ID,
            FAIL,
            f'AGENTS.md: the "{ROUTER_SECTION}" table has no row naming `{ROW_TEXT}`',
        )
    if shutil.which("make") is None:
        return Result(ID, FAIL, "make is not installed")
    try:
        proc = subprocess.run(
            ["make", "-n", "setup"],
            cwd=repo.root,
            capture_output=True,
            text=True,
            timeout=MAKE_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return Result(
            ID, FAIL, f"`make -n setup` did not finish within {MAKE_TIMEOUT_S} s"
        )
    if proc.returncode != 0:
        return Result(ID, FAIL, f"`make -n setup` failed: {proc.stderr.strip()[:200]}")
    return Result(
        ID, PASS, "`make setup` exists, dry-runs cleanly, and the router names it"
    )


def generate(repo: Repo, dry_run: bool) -> list[str]:
    """Nothing to write: the target is part of the level 1 Makefile."""
    return []


ITEM = Item(ID, 2, "Setup", check, generate)
