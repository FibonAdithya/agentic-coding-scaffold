# agentify Level 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add contract level 2 (operable) to `agentify`: a setup target, a bug channel that reaches a person, a review-bot check, and a branch-hygiene workflow that deletes a branch only when it is finished; then convert this repo to level 2.

**Architecture:** Four new check modules under `src/agentify/checks/`, each an `Item` with `check(repo) -> Result` and `generate(repo, dry_run) -> list[str]`, registered in `contract.registry()` after the level 1 items. Two new verbatim templates (`notify.yml`, `branch-hygiene.yml`). The setup target lives in the Python adapter's level 1 gate body, so adopt writes one Makefile once and never edits it. `check` with no `--level` uses the level `.agentify.toml` declares.

**Tech Stack:** Python 3.11+ (3.12 for development, via uv), PyYAML, ruff, pytest, GNU make, GitHub Actions, `gh`.

**Spec:** `docs/ai/specs/2026-09-14-agentify-design.md`, sections §1 Level 2, §3, and "Amendments made while planning level 2 (2026-09-15)". The amendments override the level 2 table where they differ; this plan follows the amendments.

## Global Constraints

- Python floor `>=3.11`. Development venv is 3.12: `uv venv --python 3.12 .venv`, then `uv pip install --python .venv/bin/python -e '.[dev]'`, then `export PATH=$PWD/.venv/bin:$PATH`.
- Runtime dependency: `pyyaml>=6` only. No new runtime dependencies (AGENTS.md, "What requires a human").
- Placeholder syntax in templates is `@@name@@`. Never `{{ }}`. The two new templates contain no placeholders; `render()` still passes through them.
- `adopt` never overwrites an existing file. The in-place edits stay exactly the four in AGENTS.md invariant 1. No new generator edits any existing file.
- Contract item ids are `L2.1` Setup, `L2.2` Bug channel, `L2.3` Review bots, `L2.4` Branch hygiene. Level 1 ids do not change.
- Nothing in any Makefile uses `|| true`, `|| exit 0`, or a leading `-` on a recipe line.
- Every backticked path in an authoritative doc must resolve. Cite docs by `#anchor`, code by `::symbol`, never by `:line`.
- Generated Python and YAML must pass the generated repo's `make check`. The generated workflow files are parsed by PyYAML in the checks; the `on` key parses as `True` and is read through `l1_3_ci.triggers`.
- Before every commit: `git status --short`; stage explicit paths only. After touching Python files run `ruff format <those files>` then `make check`.
- Commit messages end with the attribution lines the session provides.
- Deadline discipline for subagents: each task states what artifact counts as done; report partial progress rather than wait.

## File structure

```
src/agentify/cli.py                         check's default level comes from .agentify.toml
src/agentify/contract.py                    registry gains four level 2 items
src/agentify/adapters/python.py             GATE_BODY gains `setup` and a venv rule
src/agentify/checks/l2_1_setup.py           ID, check, generate (no-op), ITEM
src/agentify/checks/l2_2_notify.py          ID, WORKFLOW, router_label, check, generate, ITEM
src/agentify/checks/l2_3_review.py          ID, review_workflows, check, generate (no-op), ITEM
src/agentify/checks/l2_4_branches.py        ID, WORKFLOW, check, generate, ITEM
src/agentify/templates/AGENTS.md            Where-to-look row naming `make setup`
src/agentify/templates/notify.yml           new
src/agentify/templates/branch-hygiene.yml   new
tests/test_level_bounds.py                  rewritten against max_level()
tests/test_cli.py                           default-level test added
tests/test_adapters.py                      setup target assertions added
tests/test_templates.py                     template list updated
tests/test_l2_1_setup.py .. test_l2_4_branches.py   new
tests/test_integration.py                   adopt at level 2
CONTRACT.md, README.md, docs/adopting.md    level 2 documented
Makefile, AGENTS.md, .agentify.toml, .github/workflows/notify.yml,
.github/workflows/branch-hygiene.yml        dogfood
```

---

### Task 1: Level bounds follow `max_level()`; `check` defaults to the declared level

**Files:**
- Modify: `src/agentify/cli.py` (`main`)
- Modify: `tests/test_level_bounds.py` (rewrite)
- Test: `tests/test_cli.py` (two new tests)

**Interfaces:**
- Consumes: `agentify.contract.max_level()`, `agentify.config.load_config(root).level`.
- Produces: `cli.main(["check", repo])` runs at `load_config(repo).level` when that is within `1..max_level()`, else at `max_level()`. Later tasks raise `max_level()` to 2 and rely on this so a level 1 repo's bare `agentify check` does not report level 2 items.

- [ ] **Step 1: Rewrite `tests/test_level_bounds.py`**

Replace the whole file:

```python
"""--level must stay inside 1..max_level(): adopt must never stamp a level
this codebase does not implement, and check must never run one."""

from pathlib import Path

import pytest

from agentify.cli import main
from agentify.contract import max_level, run_adopt, run_checks
from agentify.repo import Repo


def test_check_level_zero_is_rejected_by_argparse(python_repo: Path):
    with pytest.raises(SystemExit) as exc:
        main(["check", str(python_repo), "--level", "0"])
    assert exc.value.code == 2


def test_adopt_level_above_max_is_rejected_by_argparse(python_repo: Path):
    with pytest.raises(SystemExit) as exc:
        main(["adopt", str(python_repo), "--level", str(max_level() + 1)])
    assert exc.value.code == 2


def test_run_adopt_rejects_an_out_of_range_level(tmp_path: Path):
    top = max_level()
    with pytest.raises(ValueError, match=rf"level must be 1\.\.{top}"):
        run_adopt(Repo.open(tmp_path), top + 1, False)


def test_run_checks_rejects_an_out_of_range_level(tmp_path: Path):
    top = max_level()
    with pytest.raises(ValueError, match=rf"level must be 1\.\.{top}"):
        run_checks(Repo.open(tmp_path), 0)
```

- [ ] **Step 2: Add the default-level tests to `tests/test_cli.py`**

Append at the end of the file:

```python
def _two_level_registry(monkeypatch):
    import agentify.contract as c
    from agentify.contract import PASS, Item, Result

    items = [
        Item("T.1", 1, "one", lambda r: Result("T.1", PASS, "ok"), lambda r, d: []),
        Item("T.2", 2, "two", lambda r: Result("T.2", PASS, "ok"), lambda r, d: []),
    ]
    monkeypatch.setattr(c, "registry", lambda: items)


def test_check_defaults_to_the_declared_level(tmp_path: Path, monkeypatch, capsys):
    _two_level_registry(monkeypatch)
    (tmp_path / ".agentify.toml").write_text("[contract]\nlevel = 1\n")
    assert main(["check", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "T.1" in out and "T.2" not in out and "level 1:" in out


def test_check_defaults_to_the_highest_level_without_a_config(
    tmp_path: Path, monkeypatch, capsys
):
    _two_level_registry(monkeypatch)
    assert main(["check", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "T.2" in out and "level 2:" in out


def test_check_ignores_a_declared_level_above_the_maximum(
    tmp_path: Path, monkeypatch, capsys
):
    _two_level_registry(monkeypatch)
    (tmp_path / ".agentify.toml").write_text("[contract]\nlevel = 9\n")
    assert main(["check", str(tmp_path)]) == 0
    assert "level 2:" in capsys.readouterr().out
```

- [ ] **Step 3: Run the new tests; the two default-level tests must fail**

Run: `pytest tests/test_level_bounds.py tests/test_cli.py -v`
Expected: `test_check_defaults_to_the_declared_level` FAILS (T.2 is printed because `main` uses `max_level()`); the bounds tests pass.

- [ ] **Step 4: Implement the default in `src/agentify/cli.py`**

Add the import and change the `check` branch of `main`:

```python
from agentify.config import load_config
```

```python
    if args.command == "check":
        level = args.level if args.level is not None else _default_level(repo)
        return cmd_check(repo, level, args.json)
```

Add above `main`:

```python
def _default_level(repo: Repo) -> int:
    """The level .agentify.toml declares, when it is one this agentify knows;
    otherwise the highest known. A level 1 repo must not exit 1 on level 2
    items it never adopted."""
    declared = load_config(repo.root).level
    top = max_level()
    return declared if 1 <= declared <= top else top
```

Update the `--level` help string on the `check` parser to `f"1..{max_level()} (default: the level .agentify.toml declares, else the highest known)"`.

- [ ] **Step 5: Run the tests and the full gate**

Run: `pytest tests/test_level_bounds.py tests/test_cli.py -v` then `make check`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/agentify/cli.py tests/test_level_bounds.py tests/test_cli.py
git commit -m "feat: check defaults to the declared contract level; level-bound tests follow max_level()"
```

---

### Task 2: L2.1 Setup — `make setup` in the Python gate body, the router row, and the check

**Files:**
- Modify: `src/agentify/adapters/python.py` (`GATE_BODY`)
- Modify: `src/agentify/templates/AGENTS.md` (Where to look table)
- Create: `src/agentify/checks/l2_1_setup.py`
- Modify: `src/agentify/contract.py` (`registry`)
- Test: `tests/test_adapters.py` (append), `tests/test_l2_1_setup.py` (new)

**Interfaces:**
- Consumes: `agentify.docs_refs.section(text, heading) -> str`, `l1_2_gate.MAKE_TIMEOUT_S`.
- Produces: `l2_1_setup.ID = "L2.1"`, `l2_1_setup.ITEM`, `l2_1_setup.check`, `l2_1_setup.generate` (returns `[]`). `max_level()` becomes 2 once `ITEM` is registered.

- [ ] **Step 1: Append the adapter test to `tests/test_adapters.py`**

```python
def test_python_gate_body_has_an_idempotent_setup_target(tmp_path):
    body = PythonAdapter().gate_body()
    assert "\nsetup: $(VENV)/bin/python\n" in body
    assert "$(VENV)/bin/python:\n\t$(PYTHON) -m venv $(VENV)\n" in body
    assert "-r requirements-dev.txt" in body
    assert "setup" in body.split(".PHONY:")[1].splitlines()[0]
    for forbidden in ("|| true", "|| exit 0", "\n\t-"):
        assert forbidden not in body
```

Check the top of `tests/test_adapters.py` already imports `PythonAdapter` from `agentify.adapters.python`; add the import if it does not.

- [ ] **Step 2: Run it; expect failure**

Run: `pytest tests/test_adapters.py -v -k setup`
Expected: FAIL on the first assertion.

- [ ] **Step 3: Extend `GATE_BODY` in `src/agentify/adapters/python.py`**

Replace the constant with:

```python
GATE_BODY = """\
PYTHON ?= python
RUFF ?= ruff
VENV ?= .venv

.PHONY: check lint format-check format test setup

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

# One idempotent entry point for a fresh checkout. The venv rule below only
# fires when $(VENV) is absent; every install step is a no-op the second
# time. `make -n setup` shows what would run without running it.
setup: $(VENV)/bin/python
\t$(VENV)/bin/python -m pip install --quiet --upgrade pip
\t$(VENV)/bin/python -m pip install --quiet -r requirements-dev.txt
\tif [ -f requirements.txt ]; then $(VENV)/bin/python -m pip install --quiet -r requirements.txt; fi
\tif grep -q '^\\[project\\]' pyproject.toml 2>/dev/null; then $(VENV)/bin/python -m pip install --quiet -e .; fi

$(VENV)/bin/python:
\t$(PYTHON) -m venv $(VENV)
"""
```

`GATE_BODY` is a non-raw string, so `\\[` in the source is `\[` in the Makefile; inside single quotes the shell hands grep `^\[project\]`, a literal bracket. The recipe line in a generated Makefile must read exactly `if grep -q '^\[project\]' pyproject.toml 2>/dev/null; then ...`; the test in Step 5 asserts it, so verify there and not by reasoning.

- [ ] **Step 4: Add the router row to `src/agentify/templates/AGENTS.md`**

In the *Where to look* table, insert after the `Run the gate` row:

```
| Set up a development environment | `make setup` (a target in `Makefile`) |
```

- [ ] **Step 5: Write `tests/test_l2_1_setup.py`**

```python
from pathlib import Path

from agentify.checks import l1_1_router, l1_2_gate, l2_1_setup
from agentify.contract import FAIL, PASS
from agentify.repo import Repo

ROUTER_WITH_ROW = """\
# Agent guide

## Where to look

| Task | Start here |
|---|---|
| Set up a development environment | `make setup` (a target in `Makefile`) |
"""

MAKEFILE = """\
.PHONY: check setup

check:
\techo check

setup:
\techo setup
"""


def repo_with(root: Path, makefile: str | None, router: str | None) -> Repo:
    if makefile is not None:
        (root / "Makefile").write_text(makefile)
    if router is not None:
        (root / "AGENTS.md").write_text(router)
    return Repo.open(root)


def test_missing_makefile_fails(tmp_path: Path):
    r = l2_1_setup.check(repo_with(tmp_path, None, ROUTER_WITH_ROW))
    assert r.status == FAIL and "Makefile missing" in r.reason


def test_makefile_without_setup_fails_and_names_the_template(tmp_path: Path):
    r = l2_1_setup.check(
        repo_with(tmp_path, "check:\n\techo check\n", ROUTER_WITH_ROW)
    )
    assert r.status == FAIL
    assert "no `setup` target" in r.reason
    assert "src/agentify/templates/Makefile" in r.reason


def test_router_without_the_row_fails(tmp_path: Path):
    r = l2_1_setup.check(
        repo_with(tmp_path, MAKEFILE, "# x\n\n## Where to look\n\n| a | b |\n")
    )
    assert r.status == FAIL and "make setup" in r.reason and "Where to look" in r.reason


def test_missing_router_fails(tmp_path: Path):
    r = l2_1_setup.check(repo_with(tmp_path, MAKEFILE, None))
    assert r.status == FAIL and "AGENTS.md missing" in r.reason


def test_setup_target_whose_dry_run_fails_is_reported(tmp_path: Path):
    broken = "setup: missing-prerequisite\n\techo setup\n"
    r = l2_1_setup.check(repo_with(tmp_path, broken, ROUTER_WITH_ROW))
    assert r.status == FAIL and "`make -n setup` failed" in r.reason


def test_good_repo_passes(tmp_path: Path):
    assert l2_1_setup.check(repo_with(tmp_path, MAKEFILE, ROUTER_WITH_ROW)).status == PASS


def test_generate_writes_nothing(python_repo: Path):
    assert l2_1_setup.generate(Repo.open(python_repo), dry_run=False) == []


def test_generated_python_makefile_and_router_pass(python_repo: Path):
    """The level 1 generators already produce everything L2.1 needs."""
    repo = Repo.open(python_repo)
    l1_2_gate.generate(repo, dry_run=False)
    l1_1_router.generate(repo, dry_run=False)
    assert l2_1_setup.check(repo).status == PASS
    text = (python_repo / "Makefile").read_text()
    assert "grep -q '^\\[project\\]' pyproject.toml" in text
```

- [ ] **Step 6: Run it; expect ImportError**

Run: `pytest tests/test_l2_1_setup.py -v`
Expected: FAIL, `cannot import name 'l2_1_setup'`.

- [ ] **Step 7: Write `src/agentify/checks/l2_1_setup.py`**

```python
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
        return Result(ID, FAIL, f"`make -n setup` did not finish within {MAKE_TIMEOUT_S} s")
    if proc.returncode != 0:
        return Result(ID, FAIL, f"`make -n setup` failed: {proc.stderr.strip()[:200]}")
    return Result(ID, PASS, "`make setup` exists, dry-runs cleanly, and the router names it")


def generate(repo: Repo, dry_run: bool) -> list[str]:
    """Nothing to write: the target is part of the level 1 Makefile."""
    return []


ITEM = Item(ID, 2, "Setup", check, generate)
```

- [ ] **Step 8: Register the item in `src/agentify/contract.py`**

In `registry()`, add `l2_1_setup` to the import list and `l2_1_setup.ITEM` after `l1_7_ignore.ITEM`.

- [ ] **Step 9: Run the new tests, then the full gate**

Run: `pytest tests/test_l2_1_setup.py tests/test_adapters.py -v` then `make check`
Expected: all PASS. If `test_generated_python_makefile_and_router_pass` fails on the grep line, the escaping in Step 3 is wrong: open the generated Makefile and adjust until the recipe line reads exactly `if grep -q '^\[project\]' pyproject.toml 2>/dev/null; then ...`.

`make check` on this repo runs `tests/test_contract.py`, which checks at the level `.agentify.toml` declares (1), so registering a level 2 item does not make the dogfood red yet.

- [ ] **Step 10: Commit**

```bash
git add src/agentify/adapters/python.py src/agentify/templates/AGENTS.md src/agentify/checks/l2_1_setup.py src/agentify/contract.py tests/test_adapters.py tests/test_l2_1_setup.py
git commit -m "feat(L2.1): make setup in the Python gate body, named in the router, checked by make -n"
```

---

### Task 3: L2.2 Bug channel — `notify.yml` template and the label-aware check

**Files:**
- Create: `src/agentify/templates/notify.yml`, `src/agentify/checks/l2_2_notify.py`
- Modify: `src/agentify/contract.py` (`registry`), `tests/test_templates.py` (`test_all_templates_are_present`)
- Test: `tests/test_l2_2_notify.py`

**Interfaces:**
- Consumes: `l1_3_ci.triggers(workflow) -> dict`, `docs_refs.section`.
- Produces: `l2_2_notify.ID = "L2.2"`, `l2_2_notify.WORKFLOW = ".github/workflows/notify.yml"`, `l2_2_notify.router_label(text: str) -> str | None`, `l2_2_notify.ITEM`. Task 6 documents the labels `agent-reported` and `auto-bug`.

- [ ] **Step 1: Write `src/agentify/templates/notify.yml`**

```yaml
# Makes a filed bug reach a human.
#
# GitHub does not notify an account about its own token's actions. An agent
# filing with the owner's token, or a workflow filing with GITHUB_TOKEN,
# produces an issue nobody is told about. Verified on gpu-queue-management:
# a runner-filed issue produced no notification while CI failures on the
# same repository notified normally. A *different actor* touching the issue
# is what notifies, and that is all this workflow is: github-actions[bot]
# assigns the owner.
#
# Not gated on any autofix switch or throttle. Those switch off dispatch;
# a bug nobody may auto-fix is still a bug somebody needs to know about.
name: notify

on:
  issues:
    types: [opened]

permissions:
  issues: write

jobs:
  assign:
    # `agent-reported` is an agent's prose (the label AGENTS.md tells it to
    # use); `auto-bug` is structural evidence from CI (level 3). Labels are
    # the gate because only someone with triage permission can set them:
    # GitHub silently drops labels from anyone else, so a stranger opening
    # an issue cannot route themselves into the owner's notifications.
    if: >-
      contains(github.event.issue.labels.*.name, 'agent-reported')
      || contains(github.event.issue.labels.*.name, 'auto-bug')
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - name: Assign the owner so the filing reaches them
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          REPO: ${{ github.repository }}
          NUMBER: ${{ github.event.issue.number }}
          OWNER: ${{ github.repository_owner }}
        run: |
          gh issue edit "$NUMBER" --repo "$REPO" --add-assignee "$OWNER"
          echo "assigned $OWNER to #$NUMBER"
```

- [ ] **Step 2: Write `tests/test_l2_2_notify.py`**

```python
from pathlib import Path

import pytest

from agentify.checks import l2_2_notify
from agentify.contract import FAIL, PASS
from agentify.repo import Repo

ROUTER = """\
# Agent guide

## What requires a human

To report a bug in this project, file an issue with the `agent-reported`
label:

    gh issue create --label agent-reported --title "..." --body "..."

## Where to look
"""

GOOD = """\
name: notify
on:
  issues:
    types: [opened]
permissions:
  issues: write
jobs:
  assign:
    if: >-
      contains(github.event.issue.labels.*.name, 'agent-reported')
      || contains(github.event.issue.labels.*.name, 'auto-bug')
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - run: echo assign
"""


def write(root: Path, workflow: str | None, router: str | None = ROUTER) -> Repo:
    if workflow is not None:
        (root / ".github/workflows").mkdir(parents=True, exist_ok=True)
        (root / l2_2_notify.WORKFLOW).write_text(workflow)
    if router is not None:
        (root / "AGENTS.md").write_text(router)
    return Repo.open(root)


def test_router_label_reads_the_filing_command():
    assert l2_2_notify.router_label(ROUTER) == "agent-reported"
    assert l2_2_notify.router_label("# x\n\n## What requires a human\n\nnothing\n") is None
    # The label must come from that section, not from anywhere in the file.
    elsewhere = "# x\n\n## Where to look\n\n    gh issue create --label oops\n"
    assert l2_2_notify.router_label(elsewhere) is None


def test_missing_router_fails(tmp_path: Path):
    r = l2_2_notify.check(write(tmp_path, GOOD, router=None))
    assert r.status == FAIL and "AGENTS.md missing" in r.reason


def test_router_without_a_label_fails(tmp_path: Path):
    r = l2_2_notify.check(write(tmp_path, GOOD, router="# x\n\n## What requires a human\n\n"))
    assert r.status == FAIL and "names no filing label" in r.reason


def test_missing_workflow_fails(tmp_path: Path):
    r = l2_2_notify.check(write(tmp_path, None))
    assert r.status == FAIL and "notify.yml missing" in r.reason


def test_good_workflow_passes(tmp_path: Path):
    assert l2_2_notify.check(write(tmp_path, GOOD)).status == PASS


@pytest.mark.parametrize(
    "mutation, expected",
    [
        (("  issues:\n    types: [opened]\n", "  push:\n"), "issues"),
        (("    types: [opened]\n", "    types: [labeled]\n"), "opened"),
        (("  issues: write\n", "  issues: write\n  contents: write\n"), "permissions"),
        (("    timeout-minutes: 5\n", ""), "timeout-minutes"),
        (("'agent-reported'", "'other-label'"), "agent-reported"),
    ],
)
def test_each_required_property_is_enforced(tmp_path: Path, mutation, expected):
    old, new = mutation
    assert old in GOOD
    r = l2_2_notify.check(write(tmp_path, GOOD.replace(old, new)))
    assert r.status == FAIL and expected in r.reason


def test_issues_trigger_without_types_is_accepted(tmp_path: Path):
    text = GOOD.replace("  issues:\n    types: [opened]\n", "  issues:\n")
    assert l2_2_notify.check(write(tmp_path, text)).status == PASS


def test_invalid_yaml_fails_cleanly(tmp_path: Path):
    r = l2_2_notify.check(write(tmp_path, "on: [\n"))
    assert r.status == FAIL and "not valid YAML" in r.reason


def test_generate_writes_the_template_once(python_repo: Path):
    repo = Repo.open(python_repo)
    assert l2_2_notify.generate(repo, dry_run=False) == [f"wrote    {l2_2_notify.WORKFLOW}"]
    (python_repo / "AGENTS.md").write_text(ROUTER)
    assert l2_2_notify.check(repo).status == PASS
    assert l2_2_notify.generate(repo, dry_run=False) == [f"exists   {l2_2_notify.WORKFLOW}"]
```

- [ ] **Step 3: Run it; expect ImportError**

Run: `pytest tests/test_l2_2_notify.py -v`
Expected: FAIL, `cannot import name 'l2_2_notify'`.

- [ ] **Step 4: Write `src/agentify/checks/l2_2_notify.py`**

```python
"""L2.2 Bug channel: the router names a filing label and notify.yml routes it."""

from __future__ import annotations

import re

import yaml

from agentify.checks.l1_3_ci import triggers
from agentify.contract import FAIL, PASS, Item, Result
from agentify.docs_refs import section
from agentify.repo import Repo, write_if_missing
from agentify.templates import render

ID = "L2.2"
WORKFLOW = ".github/workflows/notify.yml"
ROUTER_SECTION = "What requires a human"
LABEL_ARG = re.compile(r"--label[ =]+([A-Za-z0-9_.-]+)")


def router_label(router: str) -> str | None:
    """The label the router's filing command uses, or None."""
    match = LABEL_ARG.search(section(router, ROUTER_SECTION))
    return match.group(1) if match else None


def check(repo: Repo) -> Result:
    router = repo.read("AGENTS.md")
    if router is None:
        return Result(ID, FAIL, "AGENTS.md missing")
    label = router_label(router)
    if label is None:
        return Result(
            ID,
            FAIL,
            f'AGENTS.md: "{ROUTER_SECTION}" names no filing label (`gh issue create --label <name>`)',
        )
    text = repo.read(WORKFLOW)
    if text is None:
        return Result(ID, FAIL, f"{WORKFLOW} missing")
    try:
        workflow = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return Result(ID, FAIL, f"{WORKFLOW}: not valid YAML: {exc}")
    if not isinstance(workflow, dict):
        return Result(ID, FAIL, f"{WORKFLOW}: not a YAML mapping")
    on = triggers(workflow)
    if "issues" not in on:
        return Result(ID, FAIL, f"{WORKFLOW}: no issues trigger")
    types = on["issues"].get("types")
    if types is not None and "opened" not in types:
        return Result(ID, FAIL, f"{WORKFLOW}: issues trigger does not include opened")
    if workflow.get("permissions") != {"issues": "write"}:
        return Result(
            ID, FAIL, f"{WORKFLOW}: top-level permissions must be exactly issues: write"
        )
    jobs = workflow.get("jobs") or {}
    for name, job in jobs.items():
        if "timeout-minutes" not in (job or {}):
            return Result(ID, FAIL, f"{WORKFLOW}: job {name} has no timeout-minutes")
    gates = [str((job or {}).get("if", "")) for job in jobs.values()]
    if not any(label in gate for gate in gates):
        return Result(
            ID,
            FAIL,
            f"{WORKFLOW}: no job is gated on the label the router names ({label})",
        )
    return Result(ID, PASS, f"router files with `{label}` and notify.yml routes it")


def generate(repo: Repo, dry_run: bool) -> list[str]:
    return [write_if_missing(repo, WORKFLOW, render("notify.yml"), dry_run)]


ITEM = Item(ID, 2, "Bug channel", check, generate)
```

- [ ] **Step 5: Register the item and update the template list**

In `src/agentify/contract.py::registry`, import `l2_2_notify` and append `l2_2_notify.ITEM` after `l2_1_setup.ITEM`.

In `tests/test_templates.py::test_all_templates_are_present`, the sorted list becomes:

```python
        "AGENTS.md",
        "CLAUDE.md",
        "Makefile",
        "README.md",
        "agentify.toml",
        "ci.yml",
        "docs-ai-README.md",
        "notify.yml",
        "requirements-dev.txt",
        "test_contract.py.tmpl",
        "test_docs_references.py.tmpl",
```

- [ ] **Step 6: Run the tests, then the gate**

Run: `pytest tests/test_l2_2_notify.py tests/test_templates.py -v` then `make check`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add src/agentify/templates/notify.yml src/agentify/checks/l2_2_notify.py src/agentify/contract.py tests/test_l2_2_notify.py tests/test_templates.py
git commit -m "feat(L2.2): notify.yml template and a check that ties its gate to the router's filing label"
```

---

### Task 4: L2.3 Review bots — file-name-agnostic check, no generator

**Files:**
- Create: `src/agentify/checks/l2_3_review.py`
- Modify: `src/agentify/contract.py` (`registry`)
- Test: `tests/test_l2_3_review.py`

**Interfaces:**
- Consumes: `l1_3_ci.triggers`.
- Produces: `l2_3_review.ID = "L2.3"`, `l2_3_review.review_workflows(repo) -> list[tuple[str, dict]]` (relative path, parsed mapping) for every workflow that triggers on `pull_request` and has a step with a `prompt` input; `l2_3_review.ITEM`; `generate` returns `[]`.

- [ ] **Step 1: Write `tests/test_l2_3_review.py`**

```python
from pathlib import Path

from agentify.checks import l2_3_review
from agentify.contract import FAIL, NA, PASS
from agentify.repo import Repo

REVIEW = """\
name: review
on:
  pull_request:
    types: [opened, synchronize]
jobs:
  review:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    permissions:
      contents: read
      pull-requests: write
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: anthropics/claude-code-action@v1
        with:
          prompt: |
            Read AGENTS.md first. Then review the pull request.
"""

CI = """\
name: ci
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  check:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - run: make check
"""


def write(root: Path, **files: str) -> Repo:
    (root / ".github/workflows").mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (root / ".github/workflows" / name).write_text(text)
    return Repo.open(root)


def test_no_workflows_is_not_applicable(tmp_path: Path):
    r = l2_3_review.check(Repo.open(tmp_path))
    assert r.status == NA


def test_a_pull_request_workflow_without_a_prompt_is_ignored(tmp_path: Path):
    assert l2_3_review.check(write(tmp_path, **{"ci.yml": CI})).status == NA


def test_review_workflows_are_found_by_shape_not_name(tmp_path: Path):
    repo = write(tmp_path, **{"claude-review.yml": REVIEW, "ci.yml": CI})
    assert [path for path, _ in l2_3_review.review_workflows(repo)] == [
        ".github/workflows/claude-review.yml"
    ]


def test_good_review_workflow_passes(tmp_path: Path):
    r = l2_3_review.check(write(tmp_path, **{"docs-review.yml": REVIEW}))
    assert r.status == PASS and "docs-review.yml" in r.reason


def test_job_level_contents_write_fails(tmp_path: Path):
    text = REVIEW.replace("      contents: read\n", "      contents: write\n")
    r = l2_3_review.check(write(tmp_path, **{"review.yml": text}))
    assert r.status == FAIL and "contents: write" in r.reason


def test_top_level_contents_write_fails(tmp_path: Path):
    text = REVIEW.replace("jobs:\n", "permissions:\n  contents: write\njobs:\n")
    r = l2_3_review.check(write(tmp_path, **{"review.yml": text}))
    assert r.status == FAIL and "contents: write" in r.reason


def test_prompt_that_does_not_mention_the_router_fails(tmp_path: Path):
    text = REVIEW.replace("Read AGENTS.md first. ", "")
    r = l2_3_review.check(write(tmp_path, **{"review.yml": text}))
    assert r.status == FAIL and "AGENTS.md" in r.reason


def test_missing_timeout_fails(tmp_path: Path):
    text = REVIEW.replace("    timeout-minutes: 15\n", "")
    r = l2_3_review.check(write(tmp_path, **{"review.yml": text}))
    assert r.status == FAIL and "timeout-minutes" in r.reason


def test_invalid_yaml_anywhere_in_workflows_fails(tmp_path: Path):
    r = l2_3_review.check(write(tmp_path, **{"broken.yml": "on: [\n"}))
    assert r.status == FAIL and "not valid YAML" in r.reason


def test_generate_writes_nothing(python_repo: Path):
    assert l2_3_review.generate(Repo.open(python_repo), dry_run=False) == []
```

- [ ] **Step 2: Run it; expect ImportError**

Run: `pytest tests/test_l2_3_review.py -v`
Expected: FAIL, `cannot import name 'l2_3_review'`.

- [ ] **Step 3: Write `src/agentify/checks/l2_3_review.py`**

```python
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
            return Result(ID, FAIL, f"{rel}: top-level permissions grant contents: write")
        for name, job in (workflow.get("jobs") or {}).items():
            job = job or {}
            if _grants_contents_write(job.get("permissions")):
                return Result(ID, FAIL, f"{rel}: job {name} grants contents: write")
            if "timeout-minutes" not in job:
                return Result(ID, FAIL, f"{rel}: job {name} has no timeout-minutes")
        if not all("AGENTS.md" in prompt for prompt in _prompts(workflow)):
            return Result(ID, FAIL, f"{rel}: a prompt does not tell the model to read AGENTS.md")
    names = ", ".join(rel.removeprefix(f"{WORKFLOWS_DIR}/") for rel, _ in workflows)
    return Result(ID, PASS, f"review workflows read the router and cannot push: {names}")


def generate(repo: Repo, dry_run: bool) -> list[str]:
    """Nothing to write: review bots are optional and agent-specific."""
    return []


ITEM = Item(ID, 2, "Review bots", check, generate)
```

- [ ] **Step 4: Register the item**

In `src/agentify/contract.py::registry`, import `l2_3_review` and append `l2_3_review.ITEM` after `l2_2_notify.ITEM`.

- [ ] **Step 5: Run the tests, then the gate**

Run: `pytest tests/test_l2_3_review.py -v` then `make check`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/agentify/checks/l2_3_review.py src/agentify/contract.py tests/test_l2_3_review.py
git commit -m "feat(L2.3): review-bot check finds PR workflows by shape, forbids contents: write, requires the router in the prompt"
```

---

### Task 5: L2.4 Branch hygiene — the workflow template and its check

**Files:**
- Create: `src/agentify/templates/branch-hygiene.yml`, `src/agentify/checks/l2_4_branches.py`
- Modify: `src/agentify/contract.py` (`registry`), `tests/test_templates.py` (template list)
- Test: `tests/test_l2_4_branches.py`

**Interfaces:**
- Consumes: `l1_3_ci.triggers`.
- Produces: `l2_4_branches.ID = "L2.4"`, `l2_4_branches.WORKFLOW = ".github/workflows/branch-hygiene.yml"`, `l2_4_branches.ITEM`. Task 6 documents the `keep-branch` label and the dispatch procedure.

- [ ] **Step 1: Write `src/agentify/templates/branch-hygiene.yml`**

```yaml
# Deletes a branch when it is finished, and only then.
#
# GitHub's delete-on-merge setting deletes the head branch the moment a PR
# merges, with no way to say "this one continues". This workflow applies a
# rule instead. A branch is finished when its PR merged and nothing says it
# lives on: no `keep-branch` label, no keep pattern, no open PR based on it,
# no commit past the merged one, and it is this repository's own branch.
# Every skip is printed with its reason.
#
# Two triggers, one script:
#   - a PR closing as merged: decide about that PR's head branch;
#   - manual dispatch: sweep every branch already merged into the default
#     branch. `apply` defaults to false, so the first run only lists.
# The sweep also catches heads of squash- or rebase-merged PRs, which git
# ancestry cannot see: a branch whose tip is still the commit its merged PR
# had is finished too.
#
# It is a rule and not a model judgement because the action is a deletion.
name: branch-hygiene

on:
  pull_request:
    types: [closed]
  workflow_dispatch:
    inputs:
      apply:
        description: "Delete the finished branches. Off lists them and stops."
        type: boolean
        default: false

# The only write this workflow makes is deleting a ref. Never widen this.
permissions:
  contents: write
  pull-requests: read

concurrency:
  group: branch-hygiene
  cancel-in-progress: false

env:
  # Space-separated shell globs. A branch matching one is never deleted.
  KEEP_PATTERNS: "release/* hotfix/*"
  # A PR carrying this label keeps its branch after merge.
  KEEP_LABEL: keep-branch

jobs:
  prune:
    if: github.event_name == 'workflow_dispatch' || github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Decide per branch, then delete only what is finished
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          EVENT: ${{ github.event_name }}
          APPLY: ${{ github.event_name == 'pull_request' || inputs.apply }}
          DEFAULT_BRANCH: ${{ github.event.repository.default_branch }}
          PR_HEAD: ${{ github.event.pull_request.head.ref }}
          PR_HEAD_SHA: ${{ github.event.pull_request.head.sha }}
          PR_HEAD_REPO: ${{ github.event.pull_request.head.repo.full_name }}
          PR_LABELS: ${{ join(github.event.pull_request.labels.*.name, ' ') }}
        run: |
          set -euo pipefail
          git fetch --prune --quiet origin

          open_prs=$(gh pr list --state open --limit 500 --json headRefName,baseRefName \
            --jq '.[] | "\(.headRefName) \(.baseRefName)"')
          merged_tips=$(gh pr list --state merged --limit 500 --json headRefName,headRefOid \
            --jq '.[] | "\(.headRefName) \(.headRefOid)"')

          if [ "$EVENT" = pull_request ]; then
            candidates="$PR_HEAD"
          else
            candidates=$(git for-each-ref 'refs/remotes/origin/*' --format='%(refname:lstrip=3)')
          fi

          deleted=0
          for branch in $candidates; do
            reason=""
            tip=""
            if git rev-parse --verify --quiet "origin/$branch" >/dev/null; then
              tip=$(git rev-parse "origin/$branch")
            fi
            for pattern in $KEEP_PATTERNS; do
              case "$branch" in
                $pattern) reason="matches keep pattern $pattern" ;;
              esac
            done
            if [ "$branch" = "$DEFAULT_BRANCH" ] || [ "$branch" = HEAD ]; then
              reason="default branch"
            elif [ -z "$tip" ]; then
              reason="already gone"
            elif [ -n "$reason" ]; then
              :
            elif [ "$EVENT" = pull_request ] && [ "$PR_HEAD_REPO" != "$GITHUB_REPOSITORY" ]; then
              reason="head is on a fork"
            elif [ "$EVENT" = pull_request ] && [[ " $PR_LABELS " == *" $KEEP_LABEL "* ]]; then
              reason="labelled $KEEP_LABEL"
            elif [ "$EVENT" = pull_request ] && [ "$tip" != "$PR_HEAD_SHA" ]; then
              reason="moved past the merged commit"
            elif grep -q " $branch\$" <<<"$open_prs"; then
              reason="an open PR is based on it"
            elif grep -q "^$branch " <<<"$open_prs"; then
              reason="an open PR is from it"
            elif [ "$EVENT" = workflow_dispatch ] \
              && ! git merge-base --is-ancestor "$tip" "origin/$DEFAULT_BRANCH" \
              && ! grep -q "^$branch $tip\$" <<<"$merged_tips"; then
              reason="has commits not on $DEFAULT_BRANCH and no merged PR at its tip"
            fi

            if [ -n "$reason" ]; then
              echo "keep    $branch: $reason"
              continue
            fi
            if [ "$APPLY" = true ]; then
              gh api --method DELETE "repos/$GITHUB_REPOSITORY/git/refs/heads/$branch"
              echo "deleted $branch"
              deleted=$((deleted + 1))
            else
              echo "would delete $branch (run again with apply=true)"
            fi
          done
          echo "done: $deleted deleted"
```

- [ ] **Step 2: Write `tests/test_l2_4_branches.py`**

```python
from pathlib import Path

import pytest

from agentify.checks import l2_4_branches
from agentify.contract import FAIL, PASS
from agentify.repo import Repo
from agentify.templates import load

GOOD = """\
name: branch-hygiene
on:
  pull_request:
    types: [closed]
  workflow_dispatch:
    inputs:
      apply:
        type: boolean
        default: false
permissions:
  contents: write
  pull-requests: read
env:
  KEEP_LABEL: keep-branch
jobs:
  prune:
    if: github.event_name == 'workflow_dispatch' || github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - run: echo prune
"""


def write(root: Path, text: str) -> Repo:
    (root / ".github/workflows").mkdir(parents=True, exist_ok=True)
    (root / l2_4_branches.WORKFLOW).write_text(text)
    return Repo.open(root)


def test_missing_workflow_fails(tmp_path: Path):
    r = l2_4_branches.check(Repo.open(tmp_path))
    assert r.status == FAIL and "branch-hygiene.yml missing" in r.reason


def test_good_workflow_passes(tmp_path: Path):
    assert l2_4_branches.check(write(tmp_path, GOOD)).status == PASS


def test_the_shipped_template_passes(tmp_path: Path):
    assert l2_4_branches.check(write(tmp_path, load("branch-hygiene.yml"))).status == PASS


@pytest.mark.parametrize(
    "mutation, expected",
    [
        (("  pull_request:\n    types: [closed]\n", "  push:\n"), "pull_request"),
        (("    types: [closed]\n", "    types: [opened]\n"), "closed"),
        (("  pull_request:\n", "  pull_request_target:\n"), "pull_request_target"),
        (("  workflow_dispatch:\n    inputs:\n      apply:\n        type: boolean\n        default: false\n", ""), "workflow_dispatch"),
        (("  pull-requests: read\n", "  pull-requests: write\n"), "permissions"),
        (("  contents: write\n", "  contents: write\n  issues: write\n"), "permissions"),
        (("    timeout-minutes: 10\n", ""), "timeout-minutes"),
        (("github.event.pull_request.merged == true", "true"), "merged == true"),
        (("keep-branch", "other"), "keep-branch"),
    ],
)
def test_each_required_property_is_enforced(tmp_path: Path, mutation, expected):
    old, new = mutation
    assert old in GOOD
    r = l2_4_branches.check(write(tmp_path, GOOD.replace(old, new)))
    assert r.status == FAIL and expected in r.reason


def test_invalid_yaml_fails_cleanly(tmp_path: Path):
    r = l2_4_branches.check(write(tmp_path, "on: [\n"))
    assert r.status == FAIL and "not valid YAML" in r.reason


def test_generate_writes_the_template_once(python_repo: Path):
    repo = Repo.open(python_repo)
    assert l2_4_branches.generate(repo, dry_run=False) == [
        f"wrote    {l2_4_branches.WORKFLOW}"
    ]
    assert l2_4_branches.check(repo).status == PASS
    assert l2_4_branches.generate(repo, dry_run=False) == [
        f"exists   {l2_4_branches.WORKFLOW}"
    ]


def test_template_script_never_uses_a_blind_delete(tmp_path: Path):
    """The whole point: nothing deletes without passing the skip chain."""
    text = load("branch-hygiene.yml")
    assert text.count("git/refs/heads/") == 1
    assert 'if [ "$APPLY" = true ]; then' in text
    assert "pull_request_target" not in text
```

The `pull_request_target` mutation replaces the trigger key and so also removes the `pull_request` trigger; the check must report `pull_request_target` first, so order the checks in the implementation accordingly.

- [ ] **Step 3: Run it; expect ImportError**

Run: `pytest tests/test_l2_4_branches.py -v`
Expected: FAIL, `cannot import name 'l2_4_branches'`.

- [ ] **Step 4: Write `src/agentify/checks/l2_4_branches.py`**

```python
"""L2.4 Branch hygiene: a merged branch is deleted when it is finished, by rule."""

from __future__ import annotations

import yaml

from agentify.checks.l1_3_ci import triggers
from agentify.contract import FAIL, PASS, Item, Result
from agentify.repo import Repo, write_if_missing
from agentify.templates import render

ID = "L2.4"
WORKFLOW = ".github/workflows/branch-hygiene.yml"
PERMISSIONS = {"contents": "write", "pull-requests": "read"}
KEEP_LABEL = "keep-branch"
MERGED_GATE = "merged == true"


def check(repo: Repo) -> Result:
    text = repo.read(WORKFLOW)
    if text is None:
        return Result(ID, FAIL, f"{WORKFLOW} missing")
    try:
        workflow = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return Result(ID, FAIL, f"{WORKFLOW}: not valid YAML: {exc}")
    if not isinstance(workflow, dict):
        return Result(ID, FAIL, f"{WORKFLOW}: not a YAML mapping")
    on = triggers(workflow)
    if "pull_request_target" in on:
        return Result(ID, FAIL, f"{WORKFLOW}: must never trigger on pull_request_target")
    if "pull_request" not in on:
        return Result(ID, FAIL, f"{WORKFLOW}: no pull_request trigger")
    if "closed" not in (on["pull_request"].get("types") or []):
        return Result(ID, FAIL, f"{WORKFLOW}: pull_request trigger must include type closed")
    if "workflow_dispatch" not in on:
        return Result(ID, FAIL, f"{WORKFLOW}: no workflow_dispatch trigger for the sweep")
    if workflow.get("permissions") != PERMISSIONS:
        return Result(
            ID,
            FAIL,
            f"{WORKFLOW}: top-level permissions must be exactly contents: write and pull-requests: read",
        )
    jobs = workflow.get("jobs") or {}
    for name, job in jobs.items():
        if "timeout-minutes" not in (job or {}):
            return Result(ID, FAIL, f"{WORKFLOW}: job {name} has no timeout-minutes")
    if not any(MERGED_GATE in str((job or {}).get("if", "")) for job in jobs.values()):
        return Result(ID, FAIL, f"{WORKFLOW}: no job is gated on `{MERGED_GATE}`")
    if KEEP_LABEL not in text:
        return Result(ID, FAIL, f"{WORKFLOW}: does not honour the `{KEEP_LABEL}` label")
    return Result(ID, PASS, "branch-hygiene.yml deletes only finished branches, by rule")


def generate(repo: Repo, dry_run: bool) -> list[str]:
    return [write_if_missing(repo, WORKFLOW, render("branch-hygiene.yml"), dry_run)]


ITEM = Item(ID, 2, "Branch hygiene", check, generate)
```

- [ ] **Step 5: Register the item and update the template list**

In `src/agentify/contract.py::registry`, import `l2_4_branches` and append `l2_4_branches.ITEM` after `l2_3_review.ITEM`.

In `tests/test_templates.py::test_all_templates_are_present`, insert `"branch-hygiene.yml"` between `"agentify.toml"` and `"ci.yml"` (sorted order).

- [ ] **Step 6: Shell-check the template script**

Run:

```bash
python - <<'EOF'
import yaml, pathlib
wf = yaml.safe_load(pathlib.Path("src/agentify/templates/branch-hygiene.yml").read_text())
script = wf["jobs"]["prune"]["steps"][1]["run"]
pathlib.Path("/tmp/branch-hygiene.sh").write_text("#!/usr/bin/env bash\n" + script)
EOF
bash -n /tmp/branch-hygiene.sh && echo SYNTAX OK
```

Expected: `SYNTAX OK`. If `shellcheck` is installed, also run `shellcheck /tmp/branch-hygiene.sh` and fix anything at error level; warnings about `$KEEP_PATTERNS` being unquoted are intended (the split is the point).

- [ ] **Step 7: Run the tests, then the gate**

Run: `pytest tests/test_l2_4_branches.py tests/test_templates.py -v` then `make check`
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add src/agentify/templates/branch-hygiene.yml src/agentify/checks/l2_4_branches.py src/agentify/contract.py tests/test_l2_4_branches.py tests/test_templates.py
git commit -m "feat(L2.4): branch-hygiene workflow deletes a merged branch only when it is finished, by rule"
```

---

### Task 6: Adopt at level 2 end to end — CLI tests and the integration test

**Files:**
- Modify: `tests/test_cli.py` (append), `tests/test_integration.py` (level 2)

**Interfaces:**
- Consumes: everything Tasks 2 to 5 registered; `run_adopt(repo, level=2, dry_run)`.
- Produces: proof that `adopt --level 2` on a fresh Python project yields a repo whose own `make check` passes the contract at level 2. Task 7 converts this repo and documents the contract.

- [ ] **Step 1: Append adopt-at-level-2 tests to `tests/test_cli.py`**

```python
def test_adopt_at_level_2_writes_the_two_workflows_and_passes(python_repo: Path, capsys):
    assert main(["adopt", str(python_repo), "--level", "2"]) == 0
    out = capsys.readouterr().out
    assert "wrote    .github/workflows/notify.yml" in out
    assert "wrote    .github/workflows/branch-hygiene.yml" in out
    fill_all(python_repo)
    assert main(["check", str(python_repo)]) == 0
    out = capsys.readouterr().out
    assert "level 2: PASS" in out
    assert "L2.3  n/a" in out


def test_adopt_at_level_2_is_idempotent(python_repo: Path, capsys):
    main(["adopt", str(python_repo), "--level", "2"])
    fill_all(python_repo)
    before = tree_hash(python_repo)
    main(["adopt", str(python_repo), "--level", "2"])
    out = capsys.readouterr().out
    assert "wrote" not in out and "appended" not in out
    assert tree_hash(python_repo) == before


def test_level_1_adopt_then_level_2_adopt_only_adds(python_repo: Path, capsys):
    main(["adopt", str(python_repo)])
    capsys.readouterr()
    main(["adopt", str(python_repo), "--level", "2"])
    out = capsys.readouterr().out
    assert out.count("wrote") == 2
    assert "raised   .agentify.toml level 1 -> 2" in out
```

- [ ] **Step 2: Run them**

Run: `pytest tests/test_cli.py -v -k "level_2 or level_1_adopt"`
Expected: PASS. If `L2.3  n/a` does not match, check `cmd_check`'s format string `f"{r.item:<5} {r.status:<4} {r.reason}"`: `L2.3` padded to 5 then `n/a` gives `L2.3  n/a `. Adjust the assertion to the real spacing rather than the format.

- [ ] **Step 3: Raise the integration test to level 2**

In `tests/test_integration.py`, change both `run_adopt(Repo.open(python_repo), level=1, dry_run=False)` calls to `level=2`. Update the module docstring's last sentence to: "... runs the contract self-check at level 2 and the docs-reference test inside a fresh venv that has only what the generated CI would install."

- [ ] **Step 4: Run the integration test**

Run: `pytest tests/test_integration.py -v`
Expected: PASS. The generated `make check` now runs the contract at level 2 in the fixture venv: L2.1 dry-runs `setup`, L2.2 and L2.4 parse the two written workflows, L2.3 is n/a.

- [ ] **Step 5: Run the gate**

Run: `make check`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/test_cli.py tests/test_integration.py
git commit -m "test: adopt --level 2 end to end, and the generated gate runs the contract at level 2"
```

---

### Task 7: Dogfood — convert this repo to level 2 and document the contract

**Files:**
- Modify: `Makefile`, `AGENTS.md`, `.agentify.toml`
- Create (via adopt): `.github/workflows/notify.yml`, `.github/workflows/branch-hygiene.yml`
- Modify: `CONTRACT.md`, `README.md`, `docs/adopting.md`

**Interfaces:**
- Consumes: `agentify adopt . --level 2`.
- Produces: this repo passes `agentify check .` at level 2, `make check` is green with `.agentify.toml` at level 2, and the level 2 contract is documented. The docs come after the adopt step on purpose: `CONTRACT.md` cites the two workflow files, and the docs-reference test fails until they exist.

- [ ] **Step 1: Add `setup` to this repo's `Makefile`**

This repo installs with uv, not pip (README, Install). Append to the `Makefile`:

```make

# One idempotent entry point for a fresh checkout; mirrors README "Install".
# The venv rule fires only when .venv is absent.
setup: .venv/bin/python
	uv pip install --python .venv/bin/python -e '.[dev]'

.venv/bin/python:
	uv venv --python 3.12 .venv
```

Add `setup` to the `.PHONY` line.

- [ ] **Step 2: Add the router row to `AGENTS.md`**

In *Where to look*, after the "Run the three commands" row, add:

```
| Set up a development environment | `make setup` (a target in `Makefile`) |
```

- [ ] **Step 3: Adopt at level 2**

Run: `agentify adopt . --level 2`
Expected output includes:

```
wrote    .github/workflows/notify.yml
wrote    .github/workflows/branch-hygiene.yml
raised   .agentify.toml level 1 -> 2
```

and `exists` for everything else. If anything else says `wrote` or `appended`, stop: adopt has touched a file it should not have. Revert with `git checkout -- <file>` and report.

- [ ] **Step 4: Check at level 2**

Run: `agentify check .`
Expected: every item `pass` except `L2.3 n/a`, last line `level 2: PASS`.

- [ ] **Step 5: Document level 2 in `CONTRACT.md`**

Replace the opening paragraph's last two sentences ("Levels 2 and 3 are specified ... reports only what exists.") with: "Level 3 is specified in `docs/ai/specs/2026-09-14-agentify-design.md` and is not yet implemented; `agentify check` reports only what exists."

After the level 1 table's paragraph and before "## What adopt writes for level 1", insert:

```markdown
## Level 2 — operable

An agent can set up, run, and report on the project, and the repository
stays tidy without a person sweeping it.

| Id | Requirement | Enforced by |
|---|---|---|
| L2.1 Setup | The `Makefile` has a `setup` target that is idempotent (every step skips what exists), and the router's *Where to look* table names `make setup`. `make -n setup` exits 0 within 30 s. The Python gate body carries the target from level 1 on; a hand-written Makefile adds it by copying from the template. | `src/agentify/checks/l2_1_setup.py::check` |
| L2.2 Bug channel | The router's *What requires a human* section shows the filing command with `--label <name>`. `.github/workflows/notify.yml` triggers on issues opened, has top-level permissions exactly `issues: write`, a timeout on every job, and a job gated on that label. The labels themselves are repository state: create them as `docs/adopting.md#labels` says. | `src/agentify/checks/l2_2_notify.py::check` |
| L2.3 Review bots | Optional. Every workflow under `.github/workflows/` that triggers on `pull_request` and has a step with a `prompt` input must grant no `contents: write` at any level, have a timeout on every job, and tell the model to read `AGENTS.md`. None present reports n/a. Nothing is generated. | `src/agentify/checks/l2_3_review.py::check` |
| L2.4 Branch hygiene | `.github/workflows/branch-hygiene.yml` triggers on `pull_request` type `closed` and on `workflow_dispatch`, never on `pull_request_target`; permissions are exactly `contents: write` and `pull-requests: read`; every job has a timeout; a job is gated on `merged == true`; the `keep-branch` label is honoured. The script deletes a merged head branch unless a rule says it lives on, and the dispatch form sweeps already-merged branches with `apply` off by default. | `src/agentify/checks/l2_4_branches.py::check` |

## What adopt writes for level 2

| File | From |
|---|---|
| `.github/workflows/notify.yml` | `src/agentify/templates/notify.yml` |
| `.github/workflows/branch-hygiene.yml` | `src/agentify/templates/branch-hygiene.yml` |

Nothing else. The setup target is in the level 1 Makefile, and review bots
are copied by hand from the reference named in `docs/adopting.md#review-bots`.
```

Rename the heading "## What adopt writes for level 1" stays as is.

- [ ] **Step 6: Document level 2 in `README.md`**

After the "What a converted repo gets at level 1" section, insert:

```markdown
## What a converted repo gets at level 2

    agentify adopt <repo> --level 2

Adds `.github/workflows/notify.yml` (an issue filed with the router's label
reaches the owner) and `.github/workflows/branch-hygiene.yml` (a merged
branch is deleted when it is finished, and a manual run sweeps the backlog).
Level 2 also checks that `make setup` exists and that any PR review bot reads
`AGENTS.md` and cannot push. Three labels must exist on GitHub for the
workflows to do anything; `docs/adopting.md#labels` creates them.
```

Replace the final paragraph ("Levels 2 and 3 (operable, self-healing) ... not yet built.") with: "Level 3 (self-healing) is specified in `docs/ai/specs/2026-09-14-agentify-design.md` and not yet built."

- [ ] **Step 7: Extend `docs/adopting.md`**

Append at the end of the file:

```markdown
## Level 2

    agentify adopt <repo> --level 2

writes two workflows and raises the level in `.agentify.toml`. Three things
then need a person, because they are repository state and not files.

### Labels

The router tells agents to file with `--label agent-reported`; `notify.yml`
routes that label and `auto-bug` to the owner; `branch-hygiene.yml` keeps a
branch whose PR carries `keep-branch`. `gh issue create --label X` fails
when `X` does not exist, so create all three once:

    gh label create agent-reported --color D93F0B --description "Filed by a coding agent; routes to the owner"
    gh label create auto-bug       --color B60205 --description "Filed by CI on a red main; routes to the owner"
    gh label create keep-branch    --color 0E8A16 --description "Keep this PR's branch after merge"

### Branch hygiene

From then on a merged PR's head branch is deleted unless the PR carries
`keep-branch`, the branch matches a pattern in the workflow's
`KEEP_PATTERNS`, another open PR is based on it, or commits were pushed
after the merge. Edit `KEEP_PATTERNS` in the generated file for long-lived
branches; adopt never rewrites it.

For a repository that already has a backlog, run the sweep by hand. The
first run lists; nothing is deleted until you pass `apply`:

    gh workflow run branch-hygiene.yml
    gh run watch            # read the `keep` and `would delete` lines
    gh workflow run branch-hygiene.yml -f apply=true

Do not enable GitHub's own "automatically delete head branches" setting
alongside this; that setting deletes first and asks nothing.

### Review bots

L2.3 checks review workflows but does not write one, because a review bot is
a model choice. The reference is wgan-synthetic
(github.com/FibonAdithya/wgan-synthetic), whose workflows directory holds
claude-review.yml and docs-review.yml: copy one, keep contents read-only,
and keep "Read AGENTS.md first" in the prompt. The check fails on any
`contents: write`, because a confidently wrong rewrite must cost a comment
and never a commit.

### A hand-written Makefile

L2.1 needs a `setup` target. Copy the one the Python adapter writes
(`src/agentify/adapters/python.py::GATE_BODY`; it creates `.venv` if absent
and installs the requirements files), then add a row to the router's *Where
to look* table whose second column says `make setup`.
```

- [ ] **Step 8: Run the gate**

Run: `make check`
Expected: PASS, including `tests/test_contract.py` now at level 2. `tests/test_docs_references.py` resolves every backticked path the new prose cites: `docs/adopting.md#labels`, `docs/adopting.md#review-bots`, `src/agentify/checks/l2_*.py::check`, the two templates. If an anchor fails, the slug is the heading lower-cased with spaces as hyphens (`docs_refs.slug`).

- [ ] **Step 9: Confirm the setup target is idempotent on this repo**

Run: `make -n setup` (must print only the `uv pip install` line, since `.venv/bin/python` exists), then `make setup` twice and confirm the second run's output is the same as the first and exits 0.

- [ ] **Step 10: Commit**

```bash
git status --short
git add Makefile AGENTS.md .agentify.toml .github/workflows/notify.yml .github/workflows/branch-hygiene.yml CONTRACT.md README.md docs/adopting.md
git commit -m "chore: convert this repo to contract level 2 and document the level 2 contract"
```

---

### Task 8: Labels, push, tag, and pin (needs the user)

Creating labels on the GitHub repository, pushing, and tagging are outward-facing. Bumping the pin in `src/agentify/__init__.py` is reserved for a human by `AGENTS.md`.

- [ ] **Step 1: Report** that Tasks 1 to 7 are done, `make check` is green, and list the three commands from `docs/adopting.md#labels` plus the tag and pin bump. Ask for a go.
- [ ] **Step 2: On approval**, probe transport first (`timeout 10 ssh -o BatchMode=yes -o ConnectTimeout=8 -T git@github.com`; fall back to the HTTPS remote if it hangs). Create the three labels on `FibonAdithya/agentic-coding-scaffold` with the commands in the runbook. Push `main`. Watch CI: `gh run list --limit 1` then `gh run watch`; paste the raw result.
- [ ] **Step 3: On green**, bump `AGENTIFY_PIN` to `@v0.2.0` and `pyproject.toml` version to `0.2.0`, run `make check`, commit `chore: bump the agentify pin to v0.2.0`, push, then `git tag v0.2.0 && git push origin v0.2.0`. Confirm with `gh release list` or `git ls-remote --tags origin`.
- [ ] **Step 4: Verify the two workflows are live** with `gh workflow list`; both `notify` and `branch-hygiene` must appear. Dispatch the sweep once in list mode (`gh workflow run branch-hygiene.yml`, then `gh run watch`) and paste its output; this repo has one branch, so the expected output is `keep    main: default branch` and `done: 0 deleted`.

Follow-up outside this plan: re-run `agentify adopt --level 2` on wgan-synthetic's `agentify-adopt` branch (PR #53), create its labels, and dispatch the sweep there to clear the 26 finished branches.

## Self-review notes

Spec coverage: L2.1 Task 2; L2.2 Task 3; L2.3 Task 4; L2.4 Task 5; the `check` default-level amendment Task 1; the adopt table for level 2 Tasks 5 and 7; §5 level-bound and integration amendments Tasks 1 and 6; the runbook's labels, sweep, review-bot reference, and hand-written Makefile guidance Task 7; the reference repo passing its own level 2 Task 7; labels and pin Task 8. Not in this plan, by the spec's level 2 out-of-scope list: creating labels from adopt, deleting branches on forks, any level 3 job.

Type consistency: every check module exposes `ID`, `check`, `generate`, `ITEM`; the two workflow modules also expose `WORKFLOW`; `l2_2_notify.router_label` and `l2_3_review.review_workflows` are the only extra public names and are used by their own tests only. All four use `l1_3_ci.triggers` for the `on` block.

Mutation coverage: each check test file has one passing fixture and one parametrised mutation per enforced property, so deleting a property's guard in the check turns exactly one test red. `test_the_shipped_template_passes` ties the branch-hygiene template to its own check, and `test_generated_python_makefile_and_router_pass` ties the level 1 generators to L2.1.
