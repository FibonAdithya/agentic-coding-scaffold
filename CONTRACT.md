# The agentify contract

A repository meets a level when every item at that level and below passes
`agentify check`. Each item names the module whose check enforces it. Level
3 is specified in `docs/ai/specs/2026-09-14-agentify-design.md` and is not
yet implemented; `agentify check` reports only what exists.

## Level 1 — legible

An agent can read the repo and know what is true.

| Id | Requirement | Enforced by |
|---|---|---|
| L1.1 Router | `AGENTS.md` at the root with these `##` headings in this order: *What this project is*, *Source of truth, in order*, *Invariants*, *What "done" means*, *What requires a human*, *Where to look*. No fill marker remains. `CLAUDE.md` is absent or exactly "See AGENTS.md." | `src/agentify/checks/l1_1_router.py::check` |
| L1.2 Gate | A `Makefile` with a `check` target. No non-comment line uses `\|\| true`, `\|\| exit 0`, or a recipe line beginning with `-`. No fill marker. For Python repos, `tests/test_contract.py` exists. `make -n check` exits 0 within 30 s. This catches the three named forms; it is a lint, not a proof (e.g. `.IGNORE:` is not detected). `check` runs `make -n check`, which lets GNU make expand `$(shell …)` in the target Makefile; point `check` only at repositories you have read. | `src/agentify/checks/l1_2_gate.py::check` |
| L1.3 CI runs the gate | `.github/workflows/ci.yml` triggers on pull requests and pushes to main, has top-level `permissions: contents: read` and nothing else, a `concurrency` group with cancel-in-progress, a timeout on every job, and a step that runs `make check`. When `requirements-dev.txt` exists, some step must install it (or otherwise mention `agentify`), since the contract self-check imports agentify. | `src/agentify/checks/l1_3_ci.py::check` |
| L1.4 Authority order | Every backticked path in the router's *Source of truth* section exists, and the section names at least one. A backticked `*.md` glob (for example a directory of per-dataset pages) counts as present when it matches at least one file. | `src/agentify/checks/l1_4_authority.py::check` |
| L1.5 References resolve | In `AGENTS.md`, `CLAUDE.md`, `README.md`, and every `.md` the authority section names or globs outside `docs/ai/`: every backticked path exists (resolved against the citing document's directory first, then the repository root), every `#anchor` is a heading in its target, every `::symbol` is defined there (Python only), and no citation uses a line number. Prefixes under `[docs] ignore_references` in `.agentify.toml` are exempt. | `src/agentify/checks/l1_5_references.py::check`, scanner in `src/agentify/docs_refs.py::scan_docs` |
| L1.6 AI notes quarantined | `docs/ai/README.md` exists and contains the phrase "not the source of truth". | `src/agentify/checks/l1_6_notes.py::check` |
| L1.7 Ignore hygiene | `.gitignore` lists `.superpowers/`, `.claude/worktrees/`, `.claude/settings.local.json`, `.agentify/`, plus the language adapter's cache directories. Patterns are matched textually; `.venv` does not satisfy `.venv/`. | `src/agentify/checks/l1_7_ignore.py::check` |

## Level 2 — operable

An agent can set up, run, and report on the project, and the repository
stays tidy without a person sweeping it.

| Id | Requirement | Enforced by |
|---|---|---|
| L2.1 Setup | The `Makefile` has a `setup` target that is idempotent (every step skips what exists), and the router's *Where to look* table names `make setup`. `make -n setup` exits 0 within 30 s. The Python gate body carries the target from level 1 on; a hand-written Makefile adds it by copying from `src/agentify/adapters/python.py::GATE_BODY`. | `src/agentify/checks/l2_1_setup.py::check` |
| L2.2 Bug channel | The router's *What requires a human* section shows the filing command with `--label <name>`. `.github/workflows/notify.yml` triggers on issues opened, has top-level permissions exactly `issues: write`, a timeout on every job, and a job gated on that label. The labels themselves are repository state: create them as `docs/adopting.md#labels` says. | `src/agentify/checks/l2_2_notify.py::check` |
| L2.3 Review bots | Optional. Every workflow under `.github/workflows/` that triggers on `pull_request` and has a step with a `prompt` input must grant no `contents: write` at any level, have a timeout on every job, and tell the model to read `AGENTS.md`. None present reports n/a. Nothing is generated. | `src/agentify/checks/l2_3_review.py::check` |
| L2.4 Branch hygiene | `.github/workflows/branch-hygiene.yml` triggers on `pull_request` type `closed` and on `workflow_dispatch`, never on `pull_request_target`; permissions are exactly `contents: write` and `pull-requests: read`; every job has a timeout; a job is gated on `merged == true`; the `keep-branch` label is honoured. The script deletes a merged head branch unless a rule says it lives on, and the dispatch form sweeps branches whose tip is a merged PR's head with `apply` off by default. The check verifies the workflow's shape; it is a lint of the script, not a proof. | `src/agentify/checks/l2_4_branches.py::check` |

## What adopt writes for level 2

| File | From |
|---|---|
| `.github/workflows/notify.yml` | `src/agentify/templates/notify.yml` |
| `.github/workflows/branch-hygiene.yml` | `src/agentify/templates/branch-hygiene.yml` |

Nothing else. The setup target is in the level 1 Makefile, and review bots
are copied by hand from the reference named in `docs/adopting.md#review-bots`.

## What adopt writes for level 1

Only files that do not exist. The four exceptions, all append-or-raise and
never rewrite: `.gitignore`, the ruff block in `pyproject.toml`, the agentify
pin in `requirements-dev.txt`, and the level in `.agentify.toml`.

| File | From |
|---|---|
| `AGENTS.md` | `src/agentify/templates/AGENTS.md` |
| `CLAUDE.md` | `src/agentify/templates/CLAUDE.md` |
| `README.md` | `src/agentify/templates/README.md` |
| `Makefile` | `src/agentify/templates/Makefile`, body from the adapter |
| `.github/workflows/ci.yml` | `src/agentify/templates/ci.yml`, setup steps from the adapter |
| `docs/ai/README.md` | `src/agentify/templates/docs-ai-README.md` |
| `.agentify.toml` | `src/agentify/templates/agentify.toml` |
| `tests/test_contract.py` (Python) | `src/agentify/templates/test_contract.py.tmpl` |
| `tests/test_docs_references.py` (Python) | `src/agentify/templates/test_docs_references.py.tmpl` |
| `requirements-dev.txt` (Python) | `src/agentify/templates/requirements-dev.txt` |

## Fill markers

Sections only someone who has read the project can write are generated as
`<<FILL: prompt>>`. L1.1, L1.2 and L1.3 fail while one remains in their file.
`agentify fill` lists them. `docs/adopting.md` says how to write each one.
