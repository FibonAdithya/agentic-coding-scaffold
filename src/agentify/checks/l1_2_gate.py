"""L1.2 Gate: `make check` exists and nothing in the Makefile swallows a failure."""

from __future__ import annotations

import re
import shutil
import subprocess

from agentify.contract import FAIL, PASS, Item, Result
from agentify.repo import Repo, append_text, write_if_missing
from agentify.templates import render

ID = "L1.2"

# `make -n check` expands $(shell ...) forms while parsing the Makefile, even
# though -n never runs a recipe: a target repo's Makefile can hang or run
# arbitrarily long code before we ever get to the exit code. Bound it.
MAKE_TIMEOUT_S = 30

FORBIDDEN = (
    (re.compile(r"\|\|\s*true\b"), "'|| true'"),
    (re.compile(r"\|\|\s*exit\s+0\b"), "'|| exit 0'"),
    (re.compile(r"^\t\s*-"), "a leading '-' that ignores the exit status"),
)

NO_ADAPTER_BODY = """\
.PHONY: check

check:
\t<<FILL: run the linter and the test suite here, one command per line; each must fail this target when it fails. Finish with: agentify check .>>
"""

RUFF_BLOCK = """\
[tool.ruff]
line-length = 88
# Ruff 0.16+ lints and formats Python code blocks inside *.md by default. Docs
# hold illustrative snippets; the gate is about code.
include = ["*.py", "*.pyi", "*.pyw", "*.ipynb", "**/pyproject.toml"]

[tool.ruff.lint]
# pyflakes (F) catches real defects; E, W, I, UP are mechanical. E501 is the
# formatter's job.
select = ["E", "F", "I", "W", "UP"]
ignore = ["E501"]
"""


def check(repo: Repo) -> Result:
    text = repo.read("Makefile")
    if text is None:
        return Result(ID, FAIL, "Makefile missing")
    if not re.search(r"(?m)^check\s*:", text):
        return Result(ID, FAIL, "Makefile: no `check` target")
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith("#"):
            continue
        for pattern, what in FORBIDDEN:
            if pattern.search(line):
                return Result(ID, FAIL, f"Makefile line {number} uses {what}")
    if "<<FILL" in text:
        return Result(
            ID, FAIL, "Makefile: a <<FILL>> marker remains in the check recipe"
        )
    if repo.adapter is not None and repo.adapter.name == "python":
        if not repo.exists("tests/test_contract.py"):
            return Result(
                ID,
                FAIL,
                "tests/test_contract.py missing; the gate must run the contract self-check",
            )
    if shutil.which("make") is None:
        return Result(ID, FAIL, "make is not installed")
    try:
        proc = subprocess.run(
            ["make", "-n", "check"],
            cwd=repo.root,
            capture_output=True,
            text=True,
            timeout=MAKE_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return Result(ID, FAIL, "`make -n check` did not finish within 30 s")
    if proc.returncode != 0:
        return Result(ID, FAIL, f"`make -n check` failed: {proc.stderr.strip()[:200]}")
    return Result(
        ID, PASS, "Makefile has a `check` target and nothing swallows a failure"
    )


def generate(repo: Repo, dry_run: bool) -> list[str]:
    body = repo.adapter.gate_body() if repo.adapter is not None else NO_ADAPTER_BODY
    actions = [
        write_if_missing(repo, "Makefile", render("Makefile", body=body), dry_run)
    ]
    if repo.adapter is not None and repo.adapter.name == "python":
        pyproject = repo.read("pyproject.toml")
        if pyproject is None:
            actions.append(
                write_if_missing(repo, "pyproject.toml", RUFF_BLOCK, dry_run)
            )
        elif "[tool.ruff]" in pyproject:
            actions.append("exists   pyproject.toml ([tool.ruff])")
        else:
            actions.append(append_text(repo, "pyproject.toml", RUFF_BLOCK, dry_run))
    return actions


ITEM = Item(ID, 1, "Gate", check, generate)
