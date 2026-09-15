# Agent guide

Read this first, then follow the links. This file is a router: it says which
document is authoritative, what must not be broken, and what needs a human.
It restates as little as possible, because a second copy of a fact is a copy
that goes stale.

## What this project is

`agentify` is a written contract for what a repository must contain before a
coding agent can read it, operate it, and eventually keep it healthy; a checker
that reports how far a repo is from that contract; and a converter that writes
the missing pieces. The contract is `CONTRACT.md`. This repo passes its own
check: `tests/test_contract.py` here is the same file adopt writes into any
other repo.

It is not a framework and not an agent. It writes plain files: a router, a
Makefile, a CI workflow, two tests. Nothing it generates depends on any one
agent's hooks, skills, or settings.

## Source of truth, in order

When two documents disagree, the one higher in this list wins.

1. **The code** in `src/agentify/` and the templates in
   `src/agentify/templates/`. A check is whatever its module's check function
   does; a generated file is whatever its template says.
2. **`CONTRACT.md`** — the items, their levels, and the check each names.
3. **`README.md`** and **`docs/adopting.md`** — the three commands, and the
   runbook for finishing a conversion.
4. **`docs/ai/`** — *not authoritative*. Design specs and plans written by
   agents during development, kept for the reasoning. They are not updated as
   the code changes. See `docs/ai/README.md`. Agents writing a new design
   spec put it in `docs/ai/specs/`; implementation plans go in
   `docs/ai/plans/`; nowhere else.

## Invariants

These are silent until violated. Nothing in the test suite catches them, and
each is easy to break while believing you are making progress.

1. **Adopt never overwrites.** The only in-place edits are appending to
   `.gitignore`, appending a ruff block to `pyproject.toml`, appending the
   agentify pin to `requirements-dev.txt`, and raising the level in
   `.agentify.toml`. A generator that "fixes" an existing file has
   changed a repo someone else owns. `tests/test_cli.py` checks this for the
   files it knows about; a new generator is not covered until its test is.
2. **Item ids are stable.** `L1.1` through `L1.7` are named in `CONTRACT.md`,
   in every converted repo's test output, and in the design spec. Renumbering
   silently changes what a converted repo's failures mean.
3. **Templates are the product.** A converted repo is made of them. A change
   to a template changes every future conversion and none of the past ones.
   The prose in `src/agentify/templates/AGENTS.md` is read by agents who have
   never seen this repo; write it for them.
4. **The placeholder syntax is `@@name@@` and nothing else.** Workflow files
   contain `${{ }}`; a template engine that used braces would corrupt them.
   `src/agentify/templates.py::render` raises on an unknown placeholder, so a
   typo fails at adopt time rather than shipping.
5. **Generated Python must be lint- and format-clean under the generated
   ruff config.** It lands in another repo's `make check`. The template test
   in `tests/test_templates.py` checks this with ruff's defaults, which are
   not quite the generated config; the integration test is the real proof.

## What "done" means

Run from the repo root, inside the venv (`uv venv --python 3.12 .venv`, then
`uv pip install --python .venv/bin/python -e '.[dev]'`):

    make check

That is ruff lint, ruff format check, and pytest, including the contract
self-check and an integration test that converts a throwaway Python project
and runs its generated gate in a fresh venv (needs `uv` on PATH). It is the
same command CI runs (`.github/workflows/ci.yml`). No target uses `|| true`.

`make format` rewrites files and is not part of `check`. Only format the files
you touched.

## What requires a human

Do not decide these yourself. Raise them and stop.

- Adding, removing, or renumbering a contract item, or moving one between
  levels. The contract is the promise converted repos rely on.
- Changing the pin in `src/agentify/__init__.py`, or tagging a release. Every
  converted repo installs that pin.
- Granting the self-healing fixer write access. That is a level 3 concern;
  see the design spec under `docs/ai/specs/`.
- Adding a runtime dependency beyond PyYAML.

To report a bug in this project, file an issue with the `agent-reported`
label:

    gh issue create --label agent-reported --title "..." --body "..."

The label is what routes the issue to a person. An issue without it notifies
nobody.

## Where to look

| Task | Start here |
|---|---|
| The contract and what each check enforces | `CONTRACT.md` |
| Run the three commands | `README.md` |
| Set up a development environment | `make setup` (a target in `Makefile`) |
| Convert a repo and fill its markers | `docs/adopting.md` |
| What a check does | `src/agentify/checks/`, one module per item |
| What adopt writes | `src/agentify/templates/`, `src/agentify/contract.py::run_adopt` |
| Language-specific behaviour | `src/agentify/adapters/python.py` |
| Reference resolution in docs | `src/agentify/docs_refs.py::scan_docs` |
| Why a decision was made (non-authoritative) | `docs/ai/specs/` |
