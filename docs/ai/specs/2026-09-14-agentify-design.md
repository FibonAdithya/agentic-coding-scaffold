# agentify: a contract and converter for agent-operable repositories — Design

Date: 2026-09-14

Take any project and convert it into a form that any coding agent can read,
operate, and eventually keep healthy on its own. The pattern is lifted from two
projects that already work this way, `wgan-synthetic` and
`gpu-queue-management`, and turned into a written contract, a checker that
reports how far a repo is from that contract, and a generator that writes the
missing pieces.

## Decisions already made

These were settled in the design conversation and are not reopened here.

| Question | Decision |
|---|---|
| Form | A reference repo (this one) holding the canonical artifacts, plus a CLI that converts existing repos. |
| Language scope | Python first with a language-neutral core. Router, Makefile contract, workflows and docs tests are neutral; the first concrete gate and symbol resolver are Python. Other languages plug in as adapters. |
| Self-healing trigger | Two doors: a red gate on `main`, and a runtime bug-filing helper for projects with a long-running process. |
| Which agents | Strictly agent-neutral. The router is `AGENTS.md`. Nothing generated into a converted repo depends on any one agent's hooks, skills or settings. |
| Conversion mechanism | Contract + checker + generator. Not a copier template, not a runbook alone. |

## Purpose

An agent dropped into an unfamiliar repo has to answer, before doing anything
useful: what is this, which document is telling the truth, what will break
silently if I get it wrong, what does "done" mean, and what am I not allowed to
decide. `wgan-synthetic` answers those in a 119-line router file and
`gpu-queue-management` answers them across a README, a skill, and a design
doc. Both took several sessions of drift and correction to reach that state.

The aim is to make that state the starting point: `agentify adopt` gets a repo
most of the way in one command, `agentify check` says exactly what is still
missing, and the checks ship into the converted repo so it cannot quietly
regress.

## 1. The contract

`CONTRACT.md` in the reference repo is the authoritative list. Every item has an
id, a level, a one-paragraph rationale, and the name of the check that
enforces it. Items are grouped in three levels so a repo can be converted
incrementally; `agentify check` reports the highest level fully passed.

### Level 1 — legible

An agent can read the repo and know what is true.

| Id | Requirement | Check |
|---|---|---|
| L1.1 Router | `AGENTS.md` at the repo root containing, as `##` headings in this order: *What this project is*, *Source of truth, in order*, *Invariants*, *What "done" means*, *What requires a human*, *Where to look*. `CLAUDE.md` is either absent or exactly `See AGENTS.md.` | Headings present in order; no `<<FILL` marker remains anywhere in the file. |
| L1.2 Gate | A `Makefile` with a `check` target. No recipe line in the file uses `\|\| true`, `\|\| exit 0`, or a leading `-` that ignores the exit status. | Parse the Makefile; `make -n check` exits 0. |
| L1.3 CI runs the gate | `.github/workflows/ci.yml` runs `make check` on pull requests and on pushes to `main`. Top-level `permissions` is `contents: read` only. A `concurrency` group with `cancel-in-progress: true` and a `timeout-minutes` on every job. | YAML parse and field assertions. |
| L1.4 Authority order | Every document named in the router's *Source of truth* section exists. | Path resolution. |
| L1.5 References resolve | In every authoritative document, every backticked reference of the form `path`, `path#anchor`, or `path::symbol` resolves. Line-number citations (`path:123`) are forbidden because they rot silently. | `tests/test_docs_references.py`, ported from `wgan-synthetic`, is copied into the repo and run by its own `make check`. Symbol resolution needs a language adapter; without one only paths and anchors are checked. |
| L1.6 AI notes quarantined | `docs/ai/README.md` exists and states that everything under `docs/ai/` is non-authoritative and loses to the code and the human-maintained docs. Specs go in `docs/ai/specs/`, plans in `docs/ai/plans/`. | File exists and contains the phrase `not the source of truth`. |
| L1.7 Ignore hygiene | `.gitignore` covers agent scratch state and local settings: `.superpowers/`, `.claude/worktrees/`, `.claude/settings.local.json`, plus the language adapter's caches. | Required patterns present. |

Authoritative documents, for L1.5, are: `AGENTS.md`, `CLAUDE.md`, `README.md`,
and every document the router's *Source of truth* section names. Nothing under
`docs/ai/` is checked.

### Level 2 — operable

An agent can set up, run, and report on the project.

| Id | Requirement | Check |
|---|---|---|
| L2.1 Setup | One idempotent setup entry point (`make setup` or `bootstrap.sh`) that accepts `--dry-run`, named in the router's *Where to look* table. | Target or script exists; dry-run exits 0 in a subprocess. |
| L2.2 Bug channel | The router's *What requires a human* or *Where to look* section says how to file a bug against the project and names the label (`agent-reported`) that routes it. `.github/workflows/notify.yml` assigns the repository owner when an issue opens with that label or with `auto-bug`. | The label named in the router equals the label the workflow gates on. |
| L2.3 Review bots | Optional. `.github/workflows/review.yml` and `docs-review.yml` review pull requests and are instructed to read `AGENTS.md` first. Permissions are `contents: read` and `pull-requests: write`; nothing pushes. The model step is one `uses:` block so it can be swapped. | If present: workflow parses, permissions are as stated, the prompt mentions `AGENTS.md`. Absence is reported as *not applicable*, not as failure. |

### Level 3 — self-healing

Failures file themselves and get diagnosed. Detailed in §4.

| Id | Requirement | Check |
|---|---|---|
| L3.1 CI files bugs | `ci.yml` has a `file-bug` job that runs only when `check` fails on a push to `main`, computes a signature, deduplicates, and opens or updates an `auto-bug` issue. | Job present with `if: failure() && github.event_name == 'push'`; `permissions` on that job include `issues: write` and nothing else beyond `contents: read`. |
| L3.2 Runtime bug filing | For projects with a long-running process: `tools/bugreport.py` is present and its `report()` is called from the process's top-level exception handler. | File present and byte-identical to the template, or marked `# agentify: modified` on line 2. A repo can declare `no-daemon` in a `.agentify.toml` and the item is *not applicable*. |
| L3.3 Fixer | `.github/workflows/autofix.yml` present with the gate expression, the off switch, the throttle label, and diagnosis-only tool grants. | `tests/test_workflows.py`, copied in, asserts the structural properties in §4.5. |

### Fill markers

The parts of the router that carry the most value — the invariants nothing
tests, and the decisions reserved for a human — cannot be generated from a
tree. `adopt` writes those sections as:

    <<FILL: List the things that are silently wrong when violated and that no
    test catches. One numbered item each, with a pointer to where the truth
    lives. See docs/adopting.md#finding-invariants.>>

`check` fails L1.1 while any marker remains. `docs/adopting.md` in the reference
repo is the runbook for filling them: read the tests to find what is covered,
read the configs and data contracts to find what is not, and write down the
mistake an agent would make while believing it was making progress.

## 2. Repository layout

The reference repo is `agentic-coding`. It passes its own level 3 check, and
that check is part of its own `make check`.

    agentic-coding/
      AGENTS.md            its own router
      CLAUDE.md            "See AGENTS.md."
      CONTRACT.md          the contract, §1 of this spec, kept current
      README.md            what this is and the three commands
      Makefile             check = lint + format-check + test + self-check
      pyproject.toml       package `agentify`, Python >= 3.11, deps: pyyaml
      src/agentify/
        cli.py             argparse: check | adopt | fill
        contract.py        registry of items: id, level, check fn, generate fn
        checks/            one module per item, named by id
        adapters/
          base.py          Adapter protocol: detect, gate_recipe, resolve_symbol,
                           test_ids_from_junit, ignore_patterns
          python.py        pyproject/requirements detection, ruff + pytest gate,
                           ast-based symbol resolution
        templates/         verbatim files written by adopt, see §3
      tests/
        fixtures/          minimal repos: empty-python, adopted-python,
                           non-python, and one broken fixture per check
        test_check_*.py    one per contract item
        test_adopt.py      idempotence, no-overwrite, fill-then-pass
        test_integration.py  generated `make check` runs green
        test_docs_references.py, test_workflows.py   the same guards it ships
      docs/
        adopting.md        runbook: converting a repo, filling markers,
                           upgrading the fixer to write access
        ai/README.md       non-authoritative notice
        ai/specs/          this document
        ai/plans/          implementation plans
      .github/workflows/   ci.yml, notify.yml, autofix.yml

## 3. The CLI

Three verbs. All take a repo path, default `.`.

**`agentify check <repo> [--level N] [--json]`.** Runs every item up to the
level (default 3) and prints one row per item: id, `pass` / `fail` /
`n/a`, and one line of reason. Exit status is 1 if any item at or below the
requested level fails. The same function is what the shipped
`tests/test_contract.py` calls, so a converted repo re-checks itself on every
`make check`.

That test is the one place a converted repo depends on agentify. Adopt adds
it as a pinned dev dependency (a git URL at a tagged release) and the generated
`setup` target and `ci.yml` install it. Every other file adopt writes —
the docs-reference test, the workflows test, `bugreport.py` — is stdlib-only
and keeps working if agentify is uninstalled, so the dependency is confined to
one test and one pin.

**`agentify adopt <repo> [--level N] [--dry-run]`.** For each item up to the
level, calls its generator. Generators only create files that do not exist. The
single exception is `.gitignore`, which is appended to, never rewritten, with
a `# agentify` comment line above the added block. Every file written is
printed; every file skipped because it exists is printed with `exists`. Running
adopt twice produces no change on the second run, and the test suite asserts
this by hashing the tree.

Templates are rendered with a minimal substitution (`{{project_name}}`,
`{{gate_recipe}}`, `{{ignore_patterns}}`) and nothing else. No template
language, no conditionals; branching lives in the adapter.

**`agentify fill <repo>`.** Lists every remaining `<<FILL ...>>` marker with its
file, line, and prompt text. This is the worklist for whoever finishes the
conversion. Exit status 1 if any remain.

### Adapter detection

Shallow by design. The Python adapter fires when `pyproject.toml` or
`requirements.txt` exists at the root. It supplies the gate recipe
(`ruff check`, `ruff format --check`, `pytest`), the ruff config block for
`pyproject.toml` if no `[tool.ruff]` exists, symbol resolution via `ast` for
L1.5, junit parsing for L3.1 signatures, and ignore patterns (`__pycache__/`,
`.venv/`, `.ruff_cache/`, `.pytest_cache/`).

With no adapter, adopt writes a Makefile whose `check` target contains a
`<<FILL>>` marker in place of the recipe, and the docs test checks paths and
anchors only. Adding a language is one file implementing the `Adapter`
protocol and registering it in `adapters/__init__.py`.

### What adopt writes, by level

| Level | Files |
|---|---|
| 1 | `AGENTS.md`, `CLAUDE.md`, `Makefile`, `.github/workflows/ci.yml`, `docs/ai/README.md`, `tests/test_docs_references.py`, `tests/test_contract.py`, `.gitignore` block, and for Python a `[tool.ruff]` block appended to `pyproject.toml` if absent. |
| 2 | `.github/workflows/notify.yml`; `make setup` target appended to the generated Makefile only (an existing Makefile is never edited, and `check` reports what to add). |
| 3 | `file-bug` job in the generated `ci.yml` only; `.github/workflows/autofix.yml`; `tools/bugreport.py`; `tests/test_workflows.py`. |

Where a file already exists and lacks something (an existing `ci.yml` with no
`file-bug` job, an existing Makefile with no `setup`), adopt does not touch it.
`check` reports the gap and the reason names the template file to copy from.
Merging into hand-written files is a judgement, and the tool does not make it.

## 4. The self-healing loop

Three doors, ordered by how much trust each carries. Structural evidence runs
autonomously; prose waits for a human. Nothing merges itself.

### 4.1 Door 1 — a red gate on `main`

A `file-bug` job in `ci.yml`, `needs: check`, `if: failure() &&
github.event_name == 'push'`. Pull-request failures never file: a red PR is a
person's problem at that moment.

The signature is `sha256` of the workflow name, the job name, and the sorted
failing test ids, truncated to 12 hex. The Python adapter reads test ids from
`--junitxml`, which the generated `check` target always writes to
`.agentify/junit.xml`. With no adapter, the job hashes the last 40 lines of the
step log with digits and paths normalised. The signature is written into the
issue body as `sig: <hex>`.

Dedup, in order, via `gh issue list --label auto-bug --search "sig:<hex>"`:

1. Open issue with this signature: bump `occurrences` and `last seen` in the
   body; comment at most once per 24 hours; dispatch nothing.
2. Open PR whose body references the signature: comment on the PR; dispatch
   nothing.
3. Issue closed within 30 days: file new, linking the old as *previously fixed
   in #N; that fix did not hold*.
4. Otherwise file new, labelled `auto-bug`, carrying: the signature, the
   commit, the failing test ids, the step log tail, and the run URL.

### 4.2 Door 2 — runtime bug filing

`tools/bugreport.py`, stdlib only, copied into the repo. One function:

    report(exc: BaseException, *, phase: str, ours: Callable[[BaseException], bool],
           context: dict[str, str]) -> str | None

`ours` is the caller's classifier. It is code, not model judgement, because the
process that just failed is the least reliable narrator of whose fault it was.
When `ours(exc)` is false, nothing files. When true, the signature is the
exception type plus the in-project traceback frames by function name plus
`phase`, and filing goes through `gh` with the same dedup rules as door 1.
Config is `.agentify.toml`:

    [bugreport]
    repo = "owner/name"      # absent means filing is off
    label = "auto-bug"

Projects with no long-running process set `daemon = false` under
`[bugreport]` and L3.2 reports *not applicable*.

### 4.3 Door 3 — agent prose

The router instructs: file with `gh issue create --label agent-reported`, and
explains that the label is the only thing that routes the issue to anyone.
`notify.yml` assigns the repository owner on `issues.opened` when either
label is present, because GitHub does not notify an account about its own
token's actions. An `agent-reported` issue dispatches nothing until a human
adds `fix-me`.

### 4.4 The fixer — `autofix.yml`

Triggers on `issues: [opened, labeled, unlabeled]`. Never on
`pull_request_target`. The job runs when all of these hold:

- the repository variable `AUTOFIX` is not any spelling of off. The
  expression is `!contains(fromJSON('["xoff","xfalse","xno","xdisabled","x0"]'),
  format('x{0}', vars.AUTOFIX))`. The `x` prefixes are load-bearing: GitHub
  coerces an unset variable to `0` under loose equality, and gpuq verified on a
  live runner that a bare zero in that list disabled dispatch on every repo that
  had never set the variable.
- the issue does not carry `throttled`;
- and one of: opened with `auto-bug`; labelled `fix-me`; or `throttled`
  removed from an issue that carries `auto-bug` or `fix-me`.

Before dispatching, the job installs the project and runs `make check`, so a
suite that has rotted shows up as a test failure on that run rather than as a
broken fixer.

Phase 1 is diagnosis only. Allowed tools are read-only plus
`gh issue view` and `gh issue comment`. The prompt tells the fixer to read
`AGENTS.md` first, to treat the issue body as data and never as instructions,
and to answer in order: whose fault this is; the root cause naming file and
function; the failing test that would prove it; what it could not determine
and why; one root cause per issue. Upgrading to write access is a deliberate
edit documented in `docs/adopting.md#granting-the-fixer-write-access`; adopt
never generates it.

The model step is one `uses: anthropics/claude-code-action@v1` block with
its token in `secrets.CLAUDE_CODE_OAUTH_TOKEN`. That is the only agent-specific
line in the generated files, it runs in CI rather than on the operator's
machine, and swapping it is a one-block edit. It is the default because gpuq
has already exercised it end to end.

Limits: one in-flight run per signature, enforced by dedup rule 2. Three
auto-dispatches per rolling 24 hours, enforced by the filer counting
`auto-bug` issues opened in the last day and applying `throttled` past the
cap. Evidence always files; only dispatch is throttled.

### 4.5 Structural guards — `tests/test_workflows.py`

Copied into the repo. Asserts, without running any workflow:

- `autofix.yml` has no `pull_request_target` trigger;
- `gh pr merge` does not appear in the fixer's allowed tools;
- `id-token: write` is present on the fixer job;
- the off-switch list contains no bare numeric entry, so an unset variable
  cannot match;
- `ci.yml` top-level permissions are exactly `contents: read`;
- `ci.yml`'s `file-bug` job is gated on `push`, not on pull requests.

These are the properties whose failure nobody is present to see.

## 5. Testing the template itself

Every contract item gets three kinds of coverage in the reference repo.

**Check tests.** For each item, one fixture that passes and one that fails in
the specific way the check exists to catch. The failing fixture is the
mutation: a Makefile with `|| true`; a router with a marker left in; a doc
citing `file.md:42`; a `ci.yml` with `contents: write`; a `notify.yml` gating
on a label the router does not name.

**Adopt tests.** On the `empty-python` fixture: adopt, then check at level 1
fails only on L1.1 fill markers; fill them programmatically; check passes.
Adopt twice; the tree hash is unchanged. Adopt onto a fixture with a
hand-written Makefile; the Makefile is byte-identical afterwards and check
reports the missing `setup` target with the template path.

**Integration.** After adopt on `empty-python`, run the generated `make check`
in a subprocess with a fresh venv and assert exit 0. This proves the generated
gate runs, not just parses.

**Dogfood.** The reference repo's `make check` runs ruff, pytest, and
`agentify check . --level 3`. CI runs the same on Python 3.11 and 3.12.

**Mutation check.** After implementation each new test is broken deliberately
(delete the code it guards, confirm red, restore) before the plan marks it
done.

## 6. Verified by hand, once

The tests cannot exercise a workflow on a real runner. These are done once on
the reference repo and the result recorded here:

1. Push a commit to `main` that breaks a test; confirm an `auto-bug` issue
   files with a signature and the owner is assigned.
2. Push the same break again; confirm one issue, `occurrences: 2`, no second
   dispatch.
3. Confirm the fixer posts a single diagnosis comment and changes nothing.
4. Set `AUTOFIX=off`; confirm filing continues and dispatch stops.
5. Open an issue with `agent-reported` by hand; confirm assignment and no
   dispatch until `fix-me` is added.

## 7. Out of scope

- Auto-merge. The owner merges; the PR is the gate.
- Write access for the fixer in the generated files. Documented, not generated.
- Merging generated content into hand-written files. `check` reports the gap.
- Languages other than Python in the first version. The adapter boundary is
  designed so the second language is one file.
- Any agent-specific hook, skill, or settings file in a converted repo.
- Migrating the two reference projects. They are the source of the pattern;
  converting them is a follow-up run of the tool once it exists.

## 8. Known failure modes

- A fill marker is replaced with vague prose. `check` cannot tell a weak
  invariant from a strong one; that is what `docs/adopting.md` and human review
  are for.
- A project's `ours` classifier is too permissive and files caller errors. The
  fixer's first question exists to catch this; watch for diagnoses that
  recommend loosening a check.
- A repo already has a `ci.yml`, `Makefile`, or `AGENTS.md` in a different
  shape. Adopt leaves them alone, so a partially converted repo can sit at
  level 0 with every generated file skipped. `check` is the answer: it says
  what is missing and where the template is.
- The filer's dedup reads a bounded page of open issues. Past that, old
  signatures fall out and recur as duplicates. The filer logs when the page is
  full.

## Amendments made while planning (2026-09-14)

Decisions taken when the level 1 plan was written, recorded here so the spec
and the plan agree. Each overrides the section it names.

- **§3, dependencies.** Both shipped tests, `tests/test_contract.py` and
  `tests/test_docs_references.py`, import agentify; the reference scanner is
  one module, not duplicated into every repo. Only `bugreport.py` (level 3)
  is stdlib-only. The converted repo's dependency on agentify is the pinned
  git URL its generated CI installs.
- **§3, adopt's edit rule.** `.agentify.toml` is owned by adopt: written if
  absent, its `level` raised if lower than requested, never lowered. It is
  the third in-place edit alongside `.gitignore` and the `[tool.ruff]` block.
- **§3, `fill`.** Scans only the files adopt writes (`AGENTS.md`,
  `README.md`, `Makefile`, `.github/workflows/ci.yml`), so the agentify repo's
  own template sources do not appear in its worklist.
- **§1, L1.2.** For Python repos the gate item also requires
  `tests/test_contract.py` to exist, since the self-check is what makes the
  gate re-run the contract. L1.2 and L1.3 fail while a fill marker remains
  in their file, as L1.1 does.
- **§1, L1.4.** Adopt writes a minimal `README.md` if none exists, so the
  generated router's authority list resolves on a fresh repo. L1.6 also
  writes `docs/ai/specs/.gitkeep` and `docs/ai/plans/.gitkeep`.
- **§2, environment.** Development and CI use uv-managed Python 3.12
  (`uv venv --python 3.12`); the host's system Python is 3.10. The
  integration test needs `uv` on PATH and fails, not skips, without it.
- **§5, integration.** The generated `make check` runs in a fresh uv venv
  with agentify installed from the local checkout, not from the pin.
