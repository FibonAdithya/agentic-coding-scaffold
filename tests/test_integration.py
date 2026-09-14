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

from agentify import AGENTIFY_PIN
from agentify.contract import run_adopt
from agentify.repo import Repo
from helpers import fill_all

AGENTIFY_ROOT = Path(__file__).resolve().parent.parent


def _env_for(venv: Path) -> dict:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PATH"] = f"{venv / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}"
    env["VIRTUAL_ENV"] = str(venv)
    return env


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
    proc = subprocess.run(
        ["make", "check"],
        cwd=python_repo,
        env=_env_for(venv),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_generated_gate_runs_green_from_requirements_dev_only(python_repo: Path):
    """The install step generated CI actually runs: `pip install -r
    requirements-dev.txt` alone, with no separate `ruff`/`pytest`/pin
    arguments. Proves the critical fix (item 1): a converted repo can
    install everything `make check` needs from that one file."""
    uv = shutil.which("uv")
    assert uv, (
        "uv is required: it builds the fixture's venv (https://docs.astral.sh/uv/)"
    )
    run_adopt(Repo.open(python_repo), level=1, dry_run=False)
    fill_all(python_repo)

    req_dev = python_repo / "requirements-dev.txt"
    text = req_dev.read_text()
    assert AGENTIFY_PIN in text, "requirements-dev.txt was not generated with the pin"
    # The tag pinned in AGENTIFY_PIN does not exist yet; only the location
    # differs -- install this checkout in editable mode instead.
    req_dev.write_text(text.replace(AGENTIFY_PIN, f"-e {AGENTIFY_ROOT}"))

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
            "-r",
            str(req_dev),
            "-e",
            str(python_repo),
        ],
        check=True,
    )
    proc = subprocess.run(
        ["make", "check"],
        cwd=python_repo,
        env=_env_for(venv),
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
