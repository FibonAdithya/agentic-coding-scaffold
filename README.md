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

Run `adopt`, then `fill`, then write the marked sections by hand following
`docs/adopting.md`, then `check`. The converted repo keeps
`tests/test_contract.py`, so its own `make check` re-runs the contract from
then on.

## What a converted repo gets at level 1

`AGENTS.md`, `CLAUDE.md`, `Makefile`, `.github/workflows/ci.yml`,
`docs/ai/README.md`, `.agentify.toml`, an appended `.gitignore` block, and for
Python projects `tests/test_contract.py` and `tests/test_docs_references.py`.
The full list, with what each check enforces, is `CONTRACT.md`.

## Development

    make check

Levels 2 and 3 (operable, self-healing) are specified in
`docs/ai/specs/2026-09-14-agentify-design.md` and not yet built.
