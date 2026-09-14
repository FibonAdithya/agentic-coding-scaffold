"""Convert a throwaway Python project and run its generated `make check` for real.

Everything else in the suite checks that generated files parse. This checks
that they run: ruff lints the generated tests, pytest runs the contract
self-check and the docs-reference test inside a fresh venv that has only
what the generated CI would install.
"""

import os
import shutil
import subprocess
from pathlib import Path

from agentify.contract import run_adopt
from agentify.repo import Repo
from helpers import fill_all

AGENTIFY_ROOT = Path(__file__).resolve().parent.parent


def test_generated_gate_runs_green(python_repo: Path):
    uv = shutil.which("uv")
    assert uv, (
        "uv is required: it builds the fixture's venv (https://docs.astral.sh/uv/)"
    )
    run_adopt(Repo.open(python_repo), level=1, dry_run=False)
    fill_all(python_repo)

    venv = python_repo / ".venv"
    subprocess.run([uv, "venv", "--quiet", "--python", "3.12", str(venv)], check=True)
    subprocess.run(
        [
            uv,
            "pip",
            "install",
            "--quiet",
            "--python",
            str(venv / "bin/python"),
            "ruff",
            "pytest",
            "-e",
            str(AGENTIFY_ROOT),
            "-e",
            str(python_repo),
        ],
        check=True,
    )
    env = {
        **os.environ,
        "PATH": f"{venv / 'bin'}{os.pathsep}{os.environ['PATH']}",
        "VIRTUAL_ENV": str(venv),
    }
    proc = subprocess.run(
        ["make", "check"], cwd=python_repo, env=env, capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
