"""Python: detected by pyproject.toml or requirements.txt; gate is ruff + pytest."""

from __future__ import annotations

import ast
from pathlib import Path

GATE_BODY = """\
PYTHON ?= python
RUFF ?= ruff

.PHONY: check lint format-check format test

check: lint format-check test

lint:
\t$(RUFF) check .

format-check:
\t$(RUFF) format --check .

# Not part of `check` -- this one rewrites files.
format:
\t$(RUFF) format .

test:
\t$(PYTHON) -m pytest
"""

# `pip install -e .` only when there is a [project] table: a pyproject.toml
# that holds tool config alone has nothing to install, and the attempt fails.
CI_SETUP_STEPS = r"""      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install the toolchain and the project
        run: |
          python -m pip install --upgrade pip
          python -m pip install ruff pytest "@@agentify_pin@@"
          if [ -f requirements.txt ]; then python -m pip install -r requirements.txt; fi
          if grep -q '^\[project\]' pyproject.toml 2>/dev/null; then python -m pip install -e .; fi
"""


def _names_of(node: ast.AST) -> set[str]:
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return {node.name}
    if isinstance(node, ast.Assign):
        return {t.id for t in node.targets if isinstance(t, ast.Name)}
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return {node.target.id}
    return set()


class PythonAdapter:
    name = "python"

    def detect(self, root: Path) -> bool:
        return (root / "pyproject.toml").is_file() or (
            root / "requirements.txt"
        ).is_file()

    def gate_body(self) -> str:
        return GATE_BODY

    def ci_setup_steps(self, agentify_pin: str) -> str:
        return CI_SETUP_STEPS.replace("@@agentify_pin@@", agentify_pin)

    def ignore_patterns(self) -> list[str]:
        return ["__pycache__/", ".venv/", ".ruff_cache/", ".pytest_cache/"]

    def resolve_symbol(self, file: Path, symbol: str) -> bool:
        if file.suffix != ".py":
            return False
        try:
            tree = ast.parse(file.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            return False
        head, _, member = symbol.partition(".")
        for node in tree.body:
            if head not in _names_of(node):
                continue
            if not member:
                return True
            if isinstance(node, ast.ClassDef):
                return any(member in _names_of(child) for child in node.body)
            return False
        return False
