# agentify review wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A fourth CLI command, `agentify review`, that writes a PR review workflow from a provider-neutral template and a provider table, so L2.3 gains a generator without `adopt` depending on any one agent.

**Architecture:** One new module `src/agentify/review.py` holds the `Provider` dataclass, the two provider constructors, `render_workflow`, `resolve_provider` (the flag-or-question logic) and `run_review` (the writes). Two new verbatim templates `review.yml` and `docs-review.yml` use five `@@name@@` placeholders. `cli.py` gains the `review` subparser and passes `input` as the question function only when stdin is a TTY. The L2.3 check is not changed; the tests tie the templates to it.

**Tech Stack:** Python 3.12, argparse, PyYAML (already a dependency), pytest, ruff. No new dependencies.

**Spec:** `docs/ai/specs/2026-09-16-review-bot-wizard-design.md`

## Global Constraints

- Placeholder syntax is `@@name@@` and nothing else (AGENTS.md invariant 4). `render` raises `KeyError` on an unsupplied placeholder.
- `review` never overwrites. All writes go through `agentify.repo.write_if_missing`. Output lines are `wrote    <path>`, `exists   <path>`, `would write <path>`.
- The generated workflow triggers on `pull_request` only, never `pull_request_target`. Permissions are job-level `contents: read` and `pull-requests: write`, plus `id-token: write` only for the `claude` provider. `timeout-minutes: 20` on the job.
- Both prompts contain the literal string `AGENTS.md`.
- Non-interactive with a missing required option is a parser error (exit 2), never a hang. Questions are asked only when stdin is a TTY.
- Every backticked path in `AGENTS.md`, `README.md`, `CONTRACT.md` and `docs/adopting.md` must exist in this repo (L1.5). This repo has no `.github/workflows/review.yml`; prose names `src/agentify/templates/review.yml` instead, or drops the backticks.
- New Python must pass `ruff check .` and `ruff format --check .`.
- The gate is `PATH=$PWD/.venv/bin:$PATH make check` from the repo root. Baseline before this plan: 196 passed (measured 2026-09-16).
- No runtime dependency beyond PyYAML (AGENTS.md, "What requires a human").
- Commit trailer on every commit:
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_018o9jrBq3fPjVtQ2egrQdtJ`.
- Stage explicit paths only. Never `git add -A`, `git add .`, or `commit -a`.

## File structure

| File | Responsibility |
|---|---|
| `src/agentify/templates/review.yml` | Create. The code-review workflow, verbatim with five placeholders. |
| `src/agentify/templates/docs-review.yml` | Create. The docs-drift workflow, same placeholders, different name, concurrency group and prompt. |
| `src/agentify/review.py` | Create. `Provider`, `claude()`, `custom()`, `render_workflow()`, `MissingOption`, `resolve_provider()`, `run_review()`. |
| `src/agentify/cli.py` | Modify. `review` subparser, `interactive_ask()`, dispatch. |
| `tests/test_review.py` | Create. Provider table, rendering, L2.3 pass, writes, resolution. |
| `tests/test_templates.py` | Modify. Template list gains two names; render test for the two new templates. |
| `tests/test_cli.py` | Modify. `review` through `main()`. |
| `tests/test_integration.py` | Modify. Level 2 conversion also runs `run_review`; converted repo's own check passes L2.3. |
| `CONTRACT.md`, `README.md`, `docs/adopting.md`, `AGENTS.md` | Modify. Prose per spec section 4. |

---

### Task 1: Templates and the provider table

**Files:**
- Create: `src/agentify/templates/review.yml`
- Create: `src/agentify/templates/docs-review.yml`
- Create: `src/agentify/review.py`
- Create: `tests/test_review.py`
- Modify: `tests/test_templates.py` (the `test_all_templates_are_present` list)

**Interfaces:**
- Consumes: `agentify.templates.render(name, **values) -> str`; `agentify.checks.l2_3_review.check(repo) -> Result`; `agentify.repo.Repo.open(path)`.
- Produces:
  - `review.Provider` frozen dataclass with fields `name: str, uses: str, auth_input: str, secret: str, id_token: bool, extra_with: str`.
  - `review.claude(auth: str) -> Provider` where `auth` is `"oauth"` or `"api-key"`; raises `ValueError` otherwise.
  - `review.custom(uses: str, auth_input: str, secret: str) -> Provider`.
  - `review.render_workflow(template: str, provider: Provider) -> str` where `template` is `"review.yml"` or `"docs-review.yml"`.
  - Constants `review.REVIEW = ".github/workflows/review.yml"`, `review.DOCS_REVIEW = ".github/workflows/docs-review.yml"`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_review.py`:

```python
from pathlib import Path

import pytest
import yaml

from agentify import review
from agentify.checks import l2_3_review
from agentify.contract import PASS
from agentify.repo import Repo

PROVIDERS = {
    "claude-oauth": review.claude("oauth"),
    "claude-api-key": review.claude("api-key"),
    "custom": review.custom("acme/reviewer@v2", "acme_token", "ACME_TOKEN"),
}


def _repo_with(tmp_path: Path, **files: str) -> Repo:
    for rel, text in files.items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    return Repo.open(tmp_path)


@pytest.mark.parametrize("template", ["review.yml", "docs-review.yml"])
@pytest.mark.parametrize("provider", PROVIDERS.values(), ids=list(PROVIDERS))
def test_rendered_workflow_parses_and_passes_l2_3(
    tmp_path: Path, template: str, provider: review.Provider
):
    text = review.render_workflow(template, provider)
    parsed = yaml.safe_load(text)
    assert isinstance(parsed, dict)
    assert "pull_request_target" not in text
    repo = _repo_with(tmp_path, **{f".github/workflows/{template}": text})
    result = l2_3_review.check(repo)
    assert result.status == PASS, result.reason
    assert template in result.reason


def test_claude_oauth_uses_the_subscription_token():
    text = review.render_workflow("review.yml", review.claude("oauth"))
    assert "anthropics/claude-code-action@v1" in text
    assert "claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_AUTH_TOKEN }}" in text
    assert "id-token: write" in text
    assert "github_token: ${{ secrets.GITHUB_TOKEN }}" in text
    assert "mcp__github_inline_comment__create_inline_comment" in text
    assert "@@" not in text


def test_claude_api_key_uses_the_api_key_secret():
    text = review.render_workflow("review.yml", review.claude("api-key"))
    assert "anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}" in text
    assert "claude_code_oauth_token" not in text


def test_claude_rejects_an_unknown_auth():
    with pytest.raises(ValueError, match="api-key"):
        review.claude("password")


def test_custom_writes_the_three_values_verbatim_and_no_id_token():
    text = review.render_workflow("review.yml", PROVIDERS["custom"])
    assert "uses: acme/reviewer@v2" in text
    assert "acme_token: ${{ secrets.ACME_TOKEN }}" in text
    assert "id-token" not in text
    assert "claude_args" not in text
    assert "github_token" not in text


@pytest.mark.parametrize("template", ["review.yml", "docs-review.yml"])
def test_rendered_workflow_shape(template: str):
    parsed = yaml.safe_load(review.render_workflow(template, review.claude("oauth")))
    # PyYAML reads the bare `on` key as boolean True.
    assert parsed[True] == {"pull_request": {"types": ["opened", "synchronize"]}}
    job = parsed["jobs"]["review"]
    assert job["timeout-minutes"] == 20
    assert job["permissions"] == {
        "contents": "read",
        "pull-requests": "write",
        "id-token": "write",
    }
    step = job["steps"][1]
    assert "AGENTS.md" in step["with"]["prompt"]
    assert parsed["concurrency"]["cancel-in-progress"] is True
    assert parsed["concurrency"]["group"].startswith(
        template.removesuffix(".yml") + "-"
    )
```

In `tests/test_templates.py`, change the expected list in `test_all_templates_are_present` to:

```python
    assert sorted(p.name for p in _template_dir().iterdir()) == [
        "AGENTS.md",
        "CLAUDE.md",
        "Makefile",
        "README.md",
        "agentify.toml",
        "branch-hygiene.yml",
        "ci.yml",
        "docs-ai-README.md",
        "docs-review.yml",
        "notify.yml",
        "requirements-dev.txt",
        "review.yml",
        "test_contract.py.tmpl",
        "test_docs_references.py.tmpl",
    ]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PATH=$PWD/.venv/bin:$PATH pytest tests/test_review.py tests/test_templates.py -q`
Expected: `tests/test_review.py` errors at import with `ModuleNotFoundError: No module named 'agentify.review'`; `test_all_templates_are_present` fails on the list.

- [ ] **Step 3: Write the two templates**

Create `src/agentify/templates/review.yml` (the `@@id_token@@` and `@@extra_with@@` lines are whole-line placeholders; the provider supplies indented text or an empty string):

```yaml
# Reviews a pull request with a model and can never push.
#
# The job's token has pull-requests: write and nothing more. A confidently
# wrong review must cost a comment, never a commit; L2.3 in the agentify
# contract fails this file on any `contents: write`. Never switch the
# trigger to pull_request_target: a fork PR would then run with a write
# token and this repository's secrets.
name: review

on:
  pull_request:
    types: [opened, synchronize]

# A second push supersedes the review of the first; don't pay for both.
concurrency:
  group: review-${{ github.ref }}
  cancel-in-progress: true

jobs:
  review:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    permissions:
      contents: read
      pull-requests: write
@@id_token@@
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 1

      - uses: @@uses@@
        with:
          @@auth_input@@: ${{ secrets.@@secret@@ }}
@@extra_with@@
          prompt: |
            REPO: ${{ github.repository }}
            PR NUMBER: ${{ github.event.pull_request.number }}

            Review this pull request. The PR branch is checked out in the working
            directory. Read AGENTS.md first: it is the project's router. Its
            "Invariants" section lists what nothing in the test suite catches, its
            "Source of truth, in order" section says which document wins when two
            disagree, and its "What requires a human" section lists decisions you
            must not make.

            Prioritise, in order:
            - A change that breaks an invariant named in AGENTS.md.
            - Correctness bugs: wrong logic, silent type or shape errors, broken
              seeding or reproducibility, off-by-one errors.
            - A document that this diff has just made false. Decide which side is
              wrong using the "Source of truth, in order" section. Flag the stale
              claim; do not rewrite it.
            - New behaviour with no test.

            Do not flag style that `make check` already enforces. Do not propose
            anything the "What requires a human" section reserves; name the section
            and stop.

            Be concise and specific. If the diff is clean, say so in one short
            comment rather than manufacturing findings.

            Use `gh pr comment` for top-level feedback.
            Use `mcp__github_inline_comment__create_inline_comment` (with
            `confirmed: true`) for issues tied to specific lines.
            Only post GitHub comments; do not return review text as a message.
```

Create `src/agentify/templates/docs-review.yml`:

```yaml
# Reviews a pull request for documentation drift and can never push.
#
# Same shape and the same permission rule as review.yml: this job comments
# and never commits, and it must never trigger on pull_request_target.
name: docs-review

on:
  pull_request:
    types: [opened, synchronize]

# A second push supersedes the review of the first; don't pay for both.
concurrency:
  group: docs-review-${{ github.ref }}
  cancel-in-progress: true

jobs:
  review:
    runs-on: ubuntu-latest
    timeout-minutes: 20
    permissions:
      contents: read
      pull-requests: write
@@id_token@@
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 1

      - uses: @@uses@@
        with:
          @@auth_input@@: ${{ secrets.@@secret@@ }}
@@extra_with@@
          prompt: |
            REPO: ${{ github.repository }}
            PR NUMBER: ${{ github.event.pull_request.number }}

            Review this pull request for documentation drift only. Another workflow
            reviews the code; do not duplicate it. The PR branch is checked out.

            Read AGENTS.md first. It is the project's router: its "Source of truth,
            in order" section names which document wins when two disagree, and its
            "Invariants" section lists what nothing in the test suite catches.

            Report, in this order:
            - A claim in an authoritative document that this diff has just made
              false. Use the "Source of truth, in order" section to decide which
              side is wrong.
            - Behaviour this diff changes with no matching doc update: a new or
              renamed flag, a changed default, a renamed config key, a new entry
              point.
            - Drift touching an invariant named in AGENTS.md.
            - Any newly added `file.md:123` style citation. This repo cites
              documents by anchor and code by symbol, because line numbers rot
              silently when text is inserted above them; the contract check (L1.5)
              enforces this. Explain the rule rather than only naming the failure.

            Do not:
            - Rewrite documentation. Flag stale claims; the wording is a human's call.
            - Comment on anything under docs/ai/. Those are dated, non-authoritative
              snapshots and are not updated as the code changes.
            - Flag style that `make check` already enforces.
            - Propose anything the "What requires a human" section reserves.

            Be concise and specific. If the documentation is consistent with the
            diff, say so in one short comment rather than manufacturing findings.

            Use `gh pr comment` for top-level feedback.
            Use `mcp__github_inline_comment__create_inline_comment` (with
            `confirmed: true`) for issues tied to specific lines.
            Only post GitHub comments; do not return review text as a message.
```

- [ ] **Step 4: Write the provider table and renderer**

Create `src/agentify/review.py`:

```python
"""agentify review: write a PR review workflow for the provider you name.

`adopt` writes nothing that depends on any one agent. This command does,
deliberately and only when asked: the model step is a value the adopter
names, substituted into a provider-neutral template.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentify.templates import render

REVIEW = ".github/workflows/review.yml"
DOCS_REVIEW = ".github/workflows/docs-review.yml"

CLAUDE_USES = "anthropics/claude-code-action@v1"
CLAUDE_AUTH = {
    # --auth value: (with: key, repository secret)
    "oauth": ("claude_code_oauth_token", "CLAUDE_CODE_AUTH_TOKEN"),
    "api-key": ("anthropic_api_key", "ANTHROPIC_API_KEY"),
}
# Indented to the depth of the `with:` block in the templates (10 spaces).
CLAUDE_EXTRA_WITH = """\
          # Without this the action mints its own token through the Claude
          # GitHub App. The job's own token has the pull-requests: write it
          # needs; comments arrive from github-actions[bot].
          github_token: ${{ secrets.GITHUB_TOKEN }}
          claude_args: |
            --allowedTools "mcp__github_inline_comment__create_inline_comment,Bash(gh pr comment:*),Bash(gh pr diff:*),Bash(gh pr view:*)"
"""
ID_TOKEN_LINE = "      id-token: write"


@dataclass(frozen=True)
class Provider:
    name: str
    uses: str
    auth_input: str
    secret: str
    id_token: bool
    extra_with: str


def claude(auth: str) -> Provider:
    if auth not in CLAUDE_AUTH:
        raise ValueError(
            f"unknown auth {auth!r}: choose {' or '.join(sorted(CLAUDE_AUTH))}"
        )
    auth_input, secret = CLAUDE_AUTH[auth]
    # id-token: write lets claude-code-action mint its OIDC credential. An
    # arbitrary action does not get it unasked.
    return Provider("claude", CLAUDE_USES, auth_input, secret, True, CLAUDE_EXTRA_WITH)


def custom(uses: str, auth_input: str, secret: str) -> Provider:
    return Provider("custom", uses, auth_input, secret, False, "")


def render_workflow(template: str, provider: Provider) -> str:
    """`template` is "review.yml" or "docs-review.yml"."""
    return render(
        template,
        uses=provider.uses,
        auth_input=provider.auth_input,
        secret=provider.secret,
        id_token=ID_TOKEN_LINE if provider.id_token else "",
        extra_with=provider.extra_with.rstrip("\n"),
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `PATH=$PWD/.venv/bin:$PATH pytest tests/test_review.py tests/test_templates.py -q`
Expected: all pass. If `test_rendered_workflow_parses_and_passes_l2_3` fails with `not valid YAML`, the blank line left by an empty placeholder is not the cause (YAML allows it); check the indentation of `CLAUDE_EXTRA_WITH` (10 spaces) and `ID_TOKEN_LINE` (6 spaces).

- [ ] **Step 6: Lint and format**

Run: `PATH=$PWD/.venv/bin:$PATH ruff check src/agentify/review.py tests/test_review.py && PATH=$PWD/.venv/bin:$PATH ruff format src/agentify/review.py tests/test_review.py tests/test_templates.py`
Expected: no lint errors; format may rewrite the three files.

- [ ] **Step 7: Commit**

```bash
git add src/agentify/templates/review.yml src/agentify/templates/docs-review.yml src/agentify/review.py tests/test_review.py tests/test_templates.py
git commit -m "feat(review): provider table and the two review-workflow templates

Two verbatim templates with five @@placeholders@@; a frozen Provider row
per model step. The tests render every provider and run the real L2.3
check on the result, so the template and the check cannot drift apart.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018o9jrBq3fPjVtQ2egrQdtJ"
```

---

### Task 2: `run_review` writes the files and prints the secret step

**Files:**
- Modify: `src/agentify/review.py`
- Modify: `tests/test_review.py`

**Interfaces:**
- Consumes: `agentify.repo.write_if_missing(repo, rel, content, dry_run) -> str`; Task 1's `render_workflow`, `REVIEW`, `DOCS_REVIEW`.
- Produces: `review.run_review(repo: Repo, provider: Provider, docs_review: bool, dry_run: bool) -> list[str]`. The last element is always `f"next     gh secret set {provider.secret} --repo <owner/name>"`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_review.py`:

```python
def test_run_review_writes_review_only_by_default(tmp_path: Path):
    actions = review.run_review(
        Repo.open(tmp_path), review.claude("oauth"), docs_review=False, dry_run=False
    )
    assert actions[0] == "wrote    .github/workflows/review.yml"
    assert (tmp_path / review.REVIEW).is_file()
    assert not (tmp_path / review.DOCS_REVIEW).exists()
    assert actions[-1] == "next     gh secret set CLAUDE_CODE_AUTH_TOKEN --repo <owner/name>"


def test_run_review_with_docs_review_writes_both(tmp_path: Path):
    actions = review.run_review(
        Repo.open(tmp_path), PROVIDERS["custom"], docs_review=True, dry_run=False
    )
    assert actions[:2] == [
        "wrote    .github/workflows/review.yml",
        "wrote    .github/workflows/docs-review.yml",
    ]
    assert actions[-1] == "next     gh secret set ACME_TOKEN --repo <owner/name>"
    written = (tmp_path / review.DOCS_REVIEW).read_text()
    assert written == review.render_workflow("docs-review.yml", PROVIDERS["custom"])


def test_run_review_never_overwrites(tmp_path: Path):
    mine = "name: mine\non: pull_request\njobs: {}\n"
    target = tmp_path / review.REVIEW
    target.parent.mkdir(parents=True)
    target.write_text(mine)
    actions = review.run_review(
        Repo.open(tmp_path), review.claude("oauth"), docs_review=False, dry_run=False
    )
    assert actions[0] == "exists   .github/workflows/review.yml"
    assert target.read_text() == mine


def test_run_review_dry_run_writes_nothing(tmp_path: Path):
    actions = review.run_review(
        Repo.open(tmp_path), review.claude("oauth"), docs_review=True, dry_run=True
    )
    assert actions[:2] == [
        "would write .github/workflows/review.yml",
        "would write .github/workflows/docs-review.yml",
    ]
    assert not (tmp_path / ".github").exists()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PATH=$PWD/.venv/bin:$PATH pytest tests/test_review.py -q -k run_review`
Expected: 4 failures with `AttributeError: module 'agentify.review' has no attribute 'run_review'`.

- [ ] **Step 3: Implement `run_review`**

In `src/agentify/review.py`, change the import line `from agentify.templates import render` to:

```python
from agentify.repo import Repo, write_if_missing
from agentify.templates import render
```

and append:

```python
def run_review(
    repo: Repo, provider: Provider, docs_review: bool, dry_run: bool
) -> list[str]:
    """Write the workflow(s); never overwrite. The final line is the one step
    the wizard cannot take: the secret is repository state, like labels."""
    actions = [
        write_if_missing(repo, REVIEW, render_workflow("review.yml", provider), dry_run)
    ]
    if docs_review:
        actions.append(
            write_if_missing(
                repo,
                DOCS_REVIEW,
                render_workflow("docs-review.yml", provider),
                dry_run,
            )
        )
    actions.append(f"next     gh secret set {provider.secret} --repo <owner/name>")
    return actions
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PATH=$PWD/.venv/bin:$PATH pytest tests/test_review.py -q`
Expected: all pass.

- [ ] **Step 5: Lint, format, commit**

```bash
PATH=$PWD/.venv/bin:$PATH ruff check src/agentify/review.py tests/test_review.py
PATH=$PWD/.venv/bin:$PATH ruff format src/agentify/review.py tests/test_review.py
git add src/agentify/review.py tests/test_review.py
git commit -m "feat(review): run_review writes the workflows and names the secret step

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018o9jrBq3fPjVtQ2egrQdtJ"
```

---

### Task 3: Flag-or-question resolution and the CLI subcommand

**Files:**
- Modify: `src/agentify/review.py`
- Modify: `src/agentify/cli.py`
- Modify: `tests/test_review.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: Task 1's `claude`, `custom`; Task 2's `run_review`.
- Produces:
  - `review.MissingOption(ValueError)` with attribute `option: str` (the flag name without dashes, e.g. `"provider"`, `"uses"`).
  - `review.resolve_provider(provider: str | None, auth: str, uses: str | None, auth_input: str | None, secret: str | None, ask: Callable[[str], str] | None) -> Provider`.
  - `cli.interactive_ask() -> Callable[[str], str] | None`: returns `input` when `sys.stdin.isatty()`, else `None`. Tests monkeypatch this.
  - `agentify review <repo> --provider {claude,custom} [--auth {oauth,api-key}] [--uses REF] [--auth-input NAME] [--secret NAME] [--docs-review] [--dry-run]`.

- [ ] **Step 1: Write the failing tests for resolution**

Append to `tests/test_review.py`:

```python
def _asker(answers: dict[str, str]):
    """Answers a question by the flag name it mentions; records what was asked."""
    asked: list[str] = []

    def ask(question: str) -> str:
        asked.append(question)
        for key, value in answers.items():
            if key in question:
                return value
        raise AssertionError(f"unexpected question {question!r}")

    return ask, asked


def test_resolve_claude_from_flags_asks_nothing():
    ask, asked = _asker({})
    p = review.resolve_provider("claude", "api-key", None, None, None, ask)
    assert p == review.claude("api-key")
    assert asked == []


def test_resolve_custom_from_flags_asks_nothing():
    ask, asked = _asker({})
    p = review.resolve_provider(
        "custom", "oauth", "acme/reviewer@v2", "acme_token", "ACME_TOKEN", ask
    )
    assert p == PROVIDERS["custom"]
    assert asked == []


def test_resolve_without_provider_and_without_a_terminal_raises():
    with pytest.raises(review.MissingOption) as exc:
        review.resolve_provider(None, "oauth", None, None, None, None)
    assert exc.value.option == "provider"


def test_resolve_custom_missing_one_flag_without_a_terminal_names_it():
    with pytest.raises(review.MissingOption) as exc:
        review.resolve_provider("custom", "oauth", "acme/r@v1", None, "S", None)
    assert exc.value.option == "auth-input"


def test_resolve_asks_only_for_what_is_missing():
    ask, asked = _asker({"--provider": "custom", "--auth-input": "acme_token"})
    p = review.resolve_provider(None, "oauth", "acme/reviewer@v2", None, "ACME_TOKEN", ask)
    assert p == PROVIDERS["custom"]
    assert len(asked) == 2
    assert "--provider" in asked[0] and "claude" in asked[0] and "custom" in asked[0]
    assert "--auth-input" in asked[1]


def test_resolve_rejects_an_unknown_provider_answer():
    ask, _ = _asker({"--provider": "gpt"})
    with pytest.raises(ValueError, match="gpt"):
        review.resolve_provider(None, "oauth", None, None, None, ask)


def test_resolve_treats_a_blank_answer_as_missing():
    ask, _ = _asker({"--provider": "   "})
    with pytest.raises(review.MissingOption) as exc:
        review.resolve_provider(None, "oauth", None, None, None, ask)
    assert exc.value.option == "provider"
```

- [ ] **Step 2: Run to verify they fail**

Run: `PATH=$PWD/.venv/bin:$PATH pytest tests/test_review.py -q -k resolve`
Expected: 7 failures, `AttributeError` on `resolve_provider` / `MissingOption`.

- [ ] **Step 3: Implement resolution**

In `src/agentify/review.py`, add `from collections.abc import Callable` to the imports (after `from __future__ import annotations`, before `from dataclasses import dataclass`), and append:

```python
PROVIDERS = ("claude", "custom")


class MissingOption(ValueError):
    """A required option was neither given as a flag nor answerable (no TTY)."""

    def __init__(self, option: str):
        super().__init__(f"--{option} is required")
        self.option = option


def _need(
    value: str | None, option: str, question: str, ask: Callable[[str], str] | None
) -> str:
    """The flag's value, or the answer to `question` on a terminal.

    Asks only when the flag is absent; never asks for something already
    given. A blank answer is missing, not an empty value."""
    if value is not None and value.strip():
        return value.strip()
    if ask is None:
        raise MissingOption(option)
    answer = ask(question).strip()
    if not answer:
        raise MissingOption(option)
    return answer


def resolve_provider(
    provider: str | None,
    auth: str,
    uses: str | None,
    auth_input: str | None,
    secret: str | None,
    ask: Callable[[str], str] | None,
) -> Provider:
    name = _need(
        provider, "provider", "--provider (claude or custom): ", ask
    )
    if name == "claude":
        return claude(auth)
    if name != "custom":
        raise ValueError(f"unknown provider {name!r}: choose claude or custom")
    return custom(
        _need(uses, "uses", "--uses, the action to run (owner/action@ref): ", ask),
        _need(
            auth_input,
            "auth-input",
            "--auth-input, the with: key that receives the secret: ",
            ask,
        ),
        _need(secret, "secret", "--secret, the repository secret's name: ", ask),
    )
```

- [ ] **Step 4: Run to verify they pass**

Run: `PATH=$PWD/.venv/bin:$PATH pytest tests/test_review.py -q`
Expected: all pass.

- [ ] **Step 5: Write the failing CLI tests**

Append to `tests/test_cli.py`:

```python
def test_review_writes_the_workflow_and_prints_the_secret_step(
    python_repo: Path, capsys
):
    assert main(["review", str(python_repo), "--provider", "claude"]) == 0
    out = capsys.readouterr().out
    assert "wrote    .github/workflows/review.yml" in out
    assert "docs-review.yml" not in out
    assert "gh secret set CLAUDE_CODE_AUTH_TOKEN" in out
    assert (python_repo / ".github/workflows/review.yml").is_file()


def test_review_docs_review_and_dry_run(python_repo: Path, capsys):
    before = tree_hash(python_repo)
    assert (
        main(
            [
                "review",
                str(python_repo),
                "--provider",
                "custom",
                "--uses",
                "acme/reviewer@v2",
                "--auth-input",
                "acme_token",
                "--secret",
                "ACME_TOKEN",
                "--docs-review",
                "--dry-run",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "would write .github/workflows/review.yml" in out
    assert "would write .github/workflows/docs-review.yml" in out
    assert "gh secret set ACME_TOKEN" in out
    assert tree_hash(python_repo) == before


def test_review_without_provider_and_without_a_terminal_exits_2(
    python_repo: Path, monkeypatch, capsys
):
    import agentify.cli as cli

    monkeypatch.setattr(cli, "interactive_ask", lambda: None)
    with pytest.raises(SystemExit) as exc:
        main(["review", str(python_repo)])
    assert exc.value.code == 2
    assert "--provider is required" in capsys.readouterr().err


def test_review_asks_on_a_terminal(python_repo: Path, monkeypatch, capsys):
    import agentify.cli as cli

    monkeypatch.setattr(cli, "interactive_ask", lambda: lambda q: "claude")
    assert main(["review", str(python_repo)]) == 0
    assert "wrote    .github/workflows/review.yml" in capsys.readouterr().out


def test_review_then_check_passes_l2_3(python_repo: Path, capsys):
    main(["adopt", str(python_repo), "--level", "2"])
    main(["review", str(python_repo), "--provider", "claude", "--docs-review"])
    fill_all(python_repo)
    capsys.readouterr()
    assert main(["check", str(python_repo)]) == 0
    out = capsys.readouterr().out
    assert "L2.3  pass" in out
    assert "review.yml" in out and "docs-review.yml" in out
```

Add `import pytest` to the imports at the top of `tests/test_cli.py` (after `import json`).

- [ ] **Step 6: Run to verify they fail**

Run: `PATH=$PWD/.venv/bin:$PATH pytest tests/test_cli.py -q -k review`
Expected: 5 failures; argparse rejects `review` as an invalid choice (`SystemExit: 2`), so `test_review_without_provider_and_without_a_terminal_exits_2` may pass by accident on the exit code but fail on the `--provider is required` message. Confirm all five are red before continuing.

- [ ] **Step 7: Wire the subcommand**

In `src/agentify/cli.py`:

Change the module docstring to `"""agentify check | adopt | fill | review."""`.

Add to the imports:

```python
from collections.abc import Callable

from agentify.review import MissingOption, resolve_provider, run_review
```

In `build_parser`, after the `fill` subparser and before `return parser`:

```python
    review = sub.add_parser(
        "review",
        help="write a PR review workflow for the provider you name; never overwrites",
    )
    review.add_argument("repo", nargs="?", default=".")
    review.add_argument(
        "--provider",
        choices=["claude", "custom"],
        default=None,
        help="the model step; asked for on a terminal when omitted",
    )
    review.add_argument(
        "--auth",
        choices=["oauth", "api-key"],
        default="oauth",
        help="claude only: bill a Claude subscription (CLAUDE_CODE_AUTH_TOKEN) or an API key (ANTHROPIC_API_KEY)",
    )
    review.add_argument(
        "--uses",
        default=None,
        help="custom only: the action to run, owner/action@ref; it must accept a `prompt` input",
    )
    review.add_argument(
        "--auth-input",
        default=None,
        help="custom only: the with: key that receives the secret",
    )
    review.add_argument(
        "--secret", default=None, help="custom only: the repository secret's name"
    )
    review.add_argument(
        "--docs-review",
        action="store_true",
        help="also write docs-review.yml, a second workflow for documentation drift",
    )
    review.add_argument("--dry-run", action="store_true")
```

Add these functions after `cmd_fill`:

```python
def interactive_ask() -> Callable[[str], str] | None:
    """`input` on a terminal, else None: an agent driving the CLI must get an
    error for a missing flag, never a prompt that waits forever."""
    return input if sys.stdin.isatty() else None


def cmd_review(
    parser: argparse.ArgumentParser, repo: Repo, args: argparse.Namespace
) -> int:
    try:
        provider = resolve_provider(
            args.provider,
            args.auth,
            args.uses,
            args.auth_input,
            args.secret,
            interactive_ask(),
        )
    except MissingOption as exc:
        parser.error(f"{exc} (pass the flag, or answer the prompt on a terminal)")
    except ValueError as exc:
        parser.error(str(exc))
    for action in run_review(repo, provider, args.docs_review, args.dry_run):
        print(action)
    return 0
```

In `main`, change `args = build_parser().parse_args(argv)` to:

```python
    parser = build_parser()
    args = parser.parse_args(argv)
```

and before the final `return cmd_fill(repo)` add:

```python
    if args.command == "review":
        return cmd_review(parser, repo, args)
```

- [ ] **Step 8: Run to verify they pass**

Run: `PATH=$PWD/.venv/bin:$PATH pytest tests/test_cli.py tests/test_review.py -q`
Expected: all pass. `parser.error` raises `SystemExit(2)` and writes to stderr, which `test_review_without_provider_and_without_a_terminal_exits_2` reads via `capsys`.

- [ ] **Step 9: Lint, format, commit**

```bash
PATH=$PWD/.venv/bin:$PATH ruff check src tests
PATH=$PWD/.venv/bin:$PATH ruff format src/agentify/cli.py src/agentify/review.py tests/test_cli.py tests/test_review.py
git add src/agentify/cli.py src/agentify/review.py tests/test_cli.py tests/test_review.py
git commit -m "feat(review): the agentify review subcommand asks only on a terminal

Every question has a flag. Without a TTY a missing flag is a parser
error, so an agent driving the CLI never hangs on a prompt.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018o9jrBq3fPjVtQ2egrQdtJ"
```

---

### Task 4: The converted repo's own gate passes L2.3

**Files:**
- Modify: `tests/test_integration.py`

**Interfaces:**
- Consumes: `review.run_review`, `review.claude`.

- [ ] **Step 1: Extend the integration test**

In `tests/test_integration.py`, add to the imports:

```python
from agentify.review import claude, run_review
```

In `test_generated_gate_runs_green`, directly after `run_adopt(Repo.open(python_repo), level=2, dry_run=False)` add:

```python
    # The generated review workflows must pass the converted repo's own
    # contract self-check (L2.3), in a fresh venv on the pinned agentify.
    run_review(Repo.open(python_repo), claude("oauth"), docs_review=True, dry_run=False)
```

Then after the final `assert proc.returncode == 0, proc.stdout + proc.stderr` in that test, add:

```python
    contract = subprocess.run(
        ["agentify", "check", ".", "--level", "2"],
        cwd=python_repo,
        env=_env_for(venv),
        capture_output=True,
        text=True,
    )
    assert contract.returncode == 0, contract.stdout + contract.stderr
    assert "L2.3  pass" in contract.stdout, contract.stdout
```

Update the module docstring's second paragraph to end: `...inside a fresh venv that has only what the generated CI would install, and that the review workflows `agentify review` writes pass L2.3 there.`

- [ ] **Step 2: Run the integration test**

Run: `PATH=$PWD/.venv/bin:$PATH pytest tests/test_integration.py -q -k runs_green`
Expected: pass (needs `uv` on PATH; takes about 30 s). The converted repo's `tests/test_contract.py` at level 2 now exercises L2.3 as PASS rather than NA.

- [ ] **Step 3: Mutation check of the tie**

Temporarily edit `src/agentify/templates/review.yml` to change `contents: read` to `contents: write`. Run:

`PATH=$PWD/.venv/bin:$PATH pytest tests/test_review.py -q -k "passes_l2_3 or shape"`

Expected: the `passes_l2_3` cases for `review.yml` fail with `grants contents: write`; `docs-review.yml` cases still pass. Restore the file (`git checkout src/agentify/templates/review.yml`) and confirm the tests are green again. Record the result in the commit message.

- [ ] **Step 4: Commit**

```bash
PATH=$PWD/.venv/bin:$PATH ruff format tests/test_integration.py
git add tests/test_integration.py
git commit -m "test(review): the converted repo's own gate reports L2.3 pass

Mutation-checked: contents: write in the template turns the L2.3 cases
red and nothing else.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018o9jrBq3fPjVtQ2egrQdtJ"
```

---

### Task 5: Contract, README, runbook and router prose

**Files:**
- Modify: `CONTRACT.md` (the L2.3 row and the two lines after the level 2 adopt table)
- Modify: `README.md` (the commands section and the level 2 paragraph)
- Modify: `docs/adopting.md` (the `### Review bots` section)
- Modify: `AGENTS.md` (the "not a framework" paragraph and the *Where to look* table)

**Interfaces:**
- Consumes: nothing from code; L1.5 (`tests/test_docs_references.py`) resolves every backticked path and `::symbol` below, so `src/agentify/review.py::run_review` must exist (Task 2).

- [ ] **Step 1: CONTRACT.md**

In the L2.3 row, replace the sentence `Nothing is generated.` with:

```
`adopt` writes nothing for this item; `agentify review --provider <name>` writes `src/agentify/templates/review.yml` rendered for that provider (and `src/agentify/templates/docs-review.yml` with `--docs-review`) into `.github/workflows/`, then names the repository secret to create.
```

Replace the two lines after the level 2 adopt table:

```
Nothing else. The setup target is in the level 1 Makefile, and review bots
are copied by hand from the reference named in `docs/adopting.md#review-bots`.
```

with:

```
Nothing else. The setup target is in the level 1 Makefile. Review workflows
are written by `agentify review`, not by adopt, because the model step is a
choice; `docs/adopting.md#review-bots` walks through it.
```

- [ ] **Step 2: README.md**

Change the heading `## The three commands` to `## The four commands` and the block beneath it to:

```
    agentify check  <repo> [--level N]          # one row per contract item; exit 1 on any failure
    agentify adopt  <repo> [--level N]          # write the missing files; never overwrites
    agentify fill   <repo>                      # list the <<FILL>> markers left to write
    agentify review <repo> --provider claude    # write a PR review workflow; never overwrites
```

In the level 2 section, replace the sentence beginning `Level 2 also checks that` with:

```
Level 2 also checks that `make setup` exists and that any PR review bot reads
`AGENTS.md` and cannot push. Adopt writes no review bot; `agentify review
--provider claude` (or `--provider custom` with `--uses`, `--auth-input` and
`--secret`) writes one, and `--docs-review` adds a second workflow for
documentation drift. The workflow needs a repository secret, which the
command names when it finishes.
```

Keep the sentence about the three labels that follows.

- [ ] **Step 3: docs/adopting.md**

Replace the whole `### Review bots` section body (up to `### A hand-written Makefile`) with:

```
### Review bots

L2.3 is optional. Adopt writes no review workflow, because the model step
is a choice; `agentify review` writes one for the provider you name:

    agentify review . --provider claude                 # bills a Claude subscription
    agentify review . --provider claude --auth api-key  # bills an API key instead
    agentify review . --provider custom --uses owner/action@ref \
        --auth-input <with-key> --secret <SECRET_NAME>
    agentify review . --provider claude --docs-review   # adds docs-review.yml

Omit a flag on a terminal and the command asks for it; without a terminal
a missing flag is an error, so an agent never hangs on a prompt. A custom
action must accept a `prompt` input: that is where the generated
instructions go, and it is how L2.3 recognises a review workflow.

The command ends by printing the secret to create, for example:

    gh secret set CLAUDE_CODE_AUTH_TOKEN --repo <owner/name>

For Claude the oauth token comes from `claude setup-token`. Without the
secret the workflow fails on its first run and posts nothing.

The generated prompt tells the model to read `AGENTS.md` and defers to its
sections by name, so it never needs editing when the invariants change.
The check fails on any `contents: write`, on a workflow that declares no
`permissions` at all (the default token may write), and on a
`pull_request_target` trigger, because a confidently wrong rewrite must
cost a comment and never a commit.
```

- [ ] **Step 4: AGENTS.md**

Replace:

```
It is not a framework and not an agent. It writes plain files: a router, a
Makefile, a CI workflow, two tests. Nothing it generates depends on any one
agent's hooks, skills, or settings.
```

with:

```
It is not a framework and not an agent. It writes plain files: a router, a
Makefile, a CI workflow, two tests. `adopt` writes nothing that depends on
any one agent's hooks, skills, or settings; `agentify review` writes a PR
review workflow for the provider you name, and only when asked.
```

In the *Where to look* table, change `| Run the three commands | `README.md` |` to `| Run the four commands | `README.md` |` and add, after the `What adopt writes` row:

```
| What `agentify review` writes | `src/agentify/review.py::run_review`, templates `src/agentify/templates/review.yml` and `src/agentify/templates/docs-review.yml` |
```

- [ ] **Step 5: Run the gate**

Run: `PATH=$PWD/.venv/bin:$PATH make check 2>&1 | tail -5`
Expected: ruff clean; every test passes, including `tests/test_docs_references.py` (every new backticked path resolves) and `tests/test_contract.py` (this repo still passes its own level 2 check with L2.3 n/a). Record the passed count for the PR body; it must exceed the 196 baseline by the number of tests added in Tasks 1 to 4.

- [ ] **Step 6: Commit**

```bash
git add CONTRACT.md README.md docs/adopting.md AGENTS.md
git commit -m "docs: CONTRACT, README, runbook and router describe agentify review

L2.3 keeps its id, level and check; only 'Nothing is generated' changes.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_018o9jrBq3fPjVtQ2egrQdtJ"
```

---

### Task 6: Final verification and PR

**Files:** none new.

- [ ] **Step 1: Dry-run the command against this repo**

Run: `PATH=$PWD/.venv/bin:$PATH agentify review . --provider claude --docs-review --dry-run`
Expected output, exactly three lines:

```
would write .github/workflows/review.yml
would write .github/workflows/docs-review.yml
next     gh secret set CLAUDE_CODE_AUTH_TOKEN --repo <owner/name>
```

Do not run it without `--dry-run` here: this repo stays at L2.3 n/a (spec section 6).

- [ ] **Step 2: Run the whole gate once more and record the count**

Run: `PATH=$PWD/.venv/bin:$PATH make check 2>&1 | tail -3`
Expected: `N passed`. Write N down as MEASURED.

- [ ] **Step 3: Push and open the PR**

Probe transport first: `timeout 10 ssh -o BatchMode=yes -o ConnectTimeout=8 -T git@github.com`. Then:

```bash
git push -u origin review-wizard
gh pr create --title "feat: agentify review writes the L2.3 workflow for a named provider" --body "$(cat <<'EOF'
Adds a fourth command. `adopt` still writes nothing that depends on one agent; `agentify review --provider claude|custom` writes `review.yml` (and `docs-review.yml` with `--docs-review`) from a provider-neutral template and a provider table, then names the secret to create. Questions are asked only on a TTY; without one a missing flag is a parser error.

Spec: docs/ai/specs/2026-09-16-review-bot-wizard-design.md
Plan: docs/ai/plans/2026-09-16-review-wizard.md

L2.3 keeps its id, level and check. The tests render every provider and run the real L2.3 check on the result; the integration test runs the converted repo's own contract check in a fresh venv and asserts L2.3 pass.

Tests: <N> passed (MEASURED, `make check` at HEAD), up from 196 on main.

Not in this PR: proving the generated workflow on a live PR. wgan-synthetic has the secret; a follow-up there replacing its two hand-copied workflows is the real proof.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_018o9jrBq3fPjVtQ2egrQdtJ
EOF
)"
```

Replace `<N>` with the measured count before running. Then `gh pr checks <n> --watch` and paste the output; an empty check list is not green.
