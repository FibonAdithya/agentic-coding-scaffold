# agentify

A contract for repositories that coding agents can read, operate, and keep
healthy; a checker that says how far a repo is from it; and a converter that
writes the missing pieces. If you are an agent, read `AGENTS.md` first.

## Install

    uv venv --python 3.12 .venv
    uv pip install --python .venv/bin/python -e '.[dev]'
    export PATH=$PWD/.venv/bin:$PATH

## The three commands

    agentify check <repo> [--level N]    # one row per contract item; exit 1 on any failure
    agentify adopt <repo> [--level N]    # write the missing files; never overwrites
    agentify fill  <repo>                # list the <<FILL>> markers left to write

`check` runs `make -n check` on the target repo (with a 30 s timeout), which
lets GNU make expand `$(shell …)` forms in that repo's Makefile before any
recipe runs; point `check` only at repositories you have read.

Run `adopt`, then `fill`, then write the marked sections by hand following
`docs/adopting.md`, then `check`. The converted repo keeps
`tests/test_contract.py`, so its own `make check` re-runs the contract from
then on.

## What a converted repo gets at level 1

`AGENTS.md`, `CLAUDE.md`, `Makefile`, `.github/workflows/ci.yml`,
`docs/ai/README.md`, `.agentify.toml`, an appended `.gitignore` block, and for
Python projects `tests/test_contract.py` and `tests/test_docs_references.py`.
The full list, with what each check enforces, is `CONTRACT.md`.

## What a converted repo gets at level 2

    agentify adopt <repo> --level 2

Adds `.github/workflows/notify.yml` (an issue filed with the router's label
reaches the owner) and `.github/workflows/branch-hygiene.yml` (a merged
branch is deleted when it is finished, and a manual run sweeps the backlog).
Level 2 also checks that `make setup` exists and that any PR review bot reads
`AGENTS.md` and cannot push. Three labels must exist on GitHub before the
workflows are useful: without `agent-reported` and `auto-bug` nothing
routes, and without `keep-branch` there is no way to opt a branch out
before its first merge; `docs/adopting.md#labels` creates them.

## Development

    make check

This repo installs itself with `uv pip install -e '.[dev]'` (see Install
above), not with the generated `requirements-dev.txt` -- that file exists
here only so this repo's own contract self-check has one, the same as any
converted repo's.

Level 3 (self-healing) is specified in
`docs/ai/specs/2026-09-14-agentify-design.md` and not yet built.
