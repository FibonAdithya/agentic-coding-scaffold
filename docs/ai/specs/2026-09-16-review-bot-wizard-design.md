# agentify review: a provider-neutral review-bot wizard — Design

Date: 2026-09-16

Level 2 item L2.3 checks a PR review workflow but writes none. The runbook
tells an adopter to hand-copy `claude-review.yml` and `docs-review.yml` from
wgan-synthetic, whose prompts paste that project's invariants into the
workflow file where they go stale. This spec adds a fourth command,
`agentify review`, that writes the workflow from a neutral template and a
provider table, so the agnostic default of `adopt` is untouched and the model
step is a value the adopter names rather than text they copy.

## Decisions already made

Settled in the design conversation on 2026-09-16 and not reopened here.

| Question | Decision |
|---|---|
| Where the provider lives | A separate command, `agentify review`. `adopt` still writes nothing that depends on one agent. The L2.3 generator stays a no-op. |
| Providers | `claude` fully wired from the working wgan-synthetic workflows, plus `custom`, which takes the action ref, auth input name and secret name as flags and writes them verbatim. |
| How many workflows | `review.yml` always; `docs-review.yml` only with `--docs-review`. |
| Interactivity | Every question has a flag. The wizard asks on stdin only when it is a TTY and a required flag is missing. Non-interactive with a missing flag is an argparse error, never a hang. |
| Prompt content | Generic. The prompt tells the model to read `AGENTS.md` and defers to its sections by name. No fill markers. |

## 1. The command

    agentify review <repo> --provider {claude,custom}
                    [--auth {oauth,api-key}]              # claude only; default oauth
                    [--uses REF --auth-input NAME --secret NAME]   # custom only, all three required
                    [--docs-review] [--dry-run]

Behaviour, in order:

1. Resolve the provider. `--provider` missing on a TTY asks
   `Provider (claude, custom):`; missing without a TTY is a parser error.
   The same rule applies to the three `custom` flags. `--auth` defaults to
   `oauth` and is never asked for.
2. Render `review.yml`, and `docs-review.yml` when asked, and write each with
   `agentify.repo.write_if_missing`. Existing files are reported `exists`
   and left byte-identical (AGENTS.md invariant 1). `--dry-run` prints
   `would write` and touches nothing.
3. Print the one step the wizard cannot do, as a command:

       gh secret set CLAUDE_CODE_AUTH_TOKEN --repo <owner/name>

   using the secret name the provider resolved to. `<owner/name>` is the
   literal placeholder; the wizard does not read git remotes.
4. Exit 0. The command does not run the L2.3 check itself; `agentify check`
   does, and the test suite ties the template to the check (section 5).

Output lines follow `adopt`'s format (`wrote    <path>`, `exists   <path>`,
`would write <path>`) so an agent parsing one can parse the other.

### Provider resolution

`src/agentify/review.py` holds:

```python
@dataclass(frozen=True)
class Provider:
    name: str          # "claude" or "custom"
    uses: str          # owner/action@ref
    auth_input: str    # the `with:` key that receives the secret
    secret: str        # the repository secret's name
    id_token: bool     # whether the job needs id-token: write
    extra_with: str    # further `with:` lines, already indented, or ""
```

| Provider | uses | auth_input | secret | id_token | extra_with |
|---|---|---|---|---|---|
| claude, `--auth oauth` | `anthropics/claude-code-action@v1` | `claude_code_oauth_token` | `CLAUDE_CODE_AUTH_TOKEN` | yes | `github_token: ${{ secrets.GITHUB_TOKEN }}` and the `claude_args` allowlist below |
| claude, `--auth api-key` | same | `anthropic_api_key` | `ANTHROPIC_API_KEY` | yes | same |
| custom | `--uses` | `--auth-input` | `--secret` | no | none |

The `claude_args` allowlist is the one wgan-synthetic runs:
`mcp__github_inline_comment__create_inline_comment`, `Bash(gh pr comment:*)`,
`Bash(gh pr diff:*)`, `Bash(gh pr view:*)`. It is the only place the generated
file names a tool.

`id_token` is per provider because `id-token: write` lets a job mint an OIDC
token. claude-code-action needs it; an arbitrary action should not receive
it unasked. The L2.3 check already allows it.

A `custom` action must accept a `prompt` input: that is how L2.3 recognises
a review workflow, and the generated prompt is passed under that key. The
wizard's `--help` text for `--uses` says so.

`Provider` values are plain strings substituted into the template. Nothing
is escaped or validated beyond argparse's presence check; a wrong ref fails
on GitHub, the same as a hand-written one would.

## 2. The templates

Two verbatim files under `src/agentify/templates/`, rendered with the
existing `@@name@@` engine (AGENTS.md invariant 4). Placeholders in both:
`@@uses@@`, `@@auth_input@@`, `@@secret@@`, `@@id_token@@`, `@@extra_with@@`.
`@@id_token@@` is either the indented line `id-token: write` or empty;
`@@extra_with@@` is either indented lines or empty. Both are produced by the
provider, so the template reads like the file it produces.

`review.yml`:

```yaml
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
    # This job comments and never pushes. A confidently wrong review must
    # cost a comment, never a commit. L2.3 fails on `contents: write`.
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
            <prompt, section 3>
```

`docs-review.yml` is identical except `name: docs-review`, the concurrency
group `docs-review-${{ github.ref }}`, and its prompt.

Never `pull_request_target`: a fork PR would then run with a write token and
secrets. The trigger is fixed in the template, not a placeholder.

### Why job-level permissions

The reference files put `permissions` on the job. L2.3 accepts either
placement. Job level is kept so that adding a second job later starts with
no permissions rather than inheriting the review job's.

## 3. The prompts

Both prompts defer to `AGENTS.md` by section name instead of restating its
contents. The router already carries the project's invariants, authority
order and reserved decisions; a prompt that copies them has two sources of
truth. `agentify check` L1.1 guarantees those sections exist under exactly
those headings, which is what makes referring to them safe.

`review.yml` prompt:

```
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

`docs-review.yml` prompt:

```
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

The two tool sentences at the end name Claude's inline-comment MCP tool.
They stay in the prompt for `custom` too: a model without that tool ignores
the instruction and still has `gh pr comment`. Splitting the prompt per
provider was rejected as a second template pair for one paragraph.

Both prompts contain the literal string `AGENTS.md`, which L2.3 requires.

## 4. Contract and documentation changes

L2.3 keeps its id, level, check and semantics. The following prose changes:

- `CONTRACT.md`, L2.3 row: "Nothing is generated." becomes "`adopt` writes
  nothing; `agentify review` writes `review.yml`, and `docs-review.yml` on
  request, from `src/agentify/templates/`." The "What adopt writes for
  level 2" paragraph drops "copied by hand from the reference" and points
  at the command.
- `README.md`: "The three commands" becomes "The four commands" with the
  `review` line and one sentence on providers. The level 2 paragraph gains
  one sentence.
- `docs/adopting.md#review-bots`: describes the command, the secret step,
  the `prompt` input requirement for `custom`, and no longer points at
  wgan-synthetic as the thing to copy.
- `AGENTS.md` here and `src/agentify/templates/AGENTS.md`: the sentence
  "Nothing it generates depends on any one agent's hooks, skills, or
  settings" becomes "`adopt` writes nothing that depends on any one agent;
  `agentify review` writes a workflow for the provider you name." The
  *Where to look* table here gains a row for the wizard.
- `src/agentify/cli.py` docstring: `check | adopt | fill | review`.

Every backticked path in these documents is resolved by L1.5 against this
repo, and this repo has no `.github/workflows/review.yml`. Prose therefore
names the generated files by their template path,
`src/agentify/templates/review.yml`, or without backticks.

The design spec of 2026-09-14 recorded "There is no generator; the runbook
points at wgan-synthetic's two workflows as the copyable reference." That
spec is not edited; this one supersedes that sentence.

The L2.3 check itself is not changed. If implementing shows the generated
file fails the check, the template is wrong, not the check.

## 5. Testing

`tests/test_review.py`:

| Test | Mutation it catches |
|---|---|
| For each of claude/oauth, claude/api-key, custom: write into a temp repo, parse with PyYAML, run `l2_3_review.check`, assert PASS naming the file. | Any template edit that breaks L2.3: dropping `AGENTS.md` from a prompt, granting `contents: write`, dropping `timeout-minutes`, switching to `pull_request_target`, removing `permissions`. |
| claude/oauth: rendered text contains `claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_AUTH_TOKEN }}` and `id-token: write`. api-key: contains `anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}`. | Provider table rows swapped or a placeholder left unsubstituted. |
| custom: rendered text contains the three flag values verbatim and does not contain `id-token`. | `id_token` ignored, or claude's extras leaking into custom. |
| `--docs-review` writes both files; without it only `review.yml` exists. | Flag ignored. |
| A pre-existing `review.yml` with distinct content is byte-identical after the run and the action line says `exists`. | A regression to invariant 1. |
| `--dry-run` writes nothing and reports `would write`. | dry_run threaded wrongly. |
| Provider missing, no TTY: `main([...])` raises `SystemExit(2)`. | Wizard hanging or defaulting silently. |
| Provider missing, TTY: the injected question function is called once with the prompt text and its answer is used. `custom` with one flag missing asks for exactly that flag. | Asking for flags already given, or not asking on a TTY. |
| The final printed line names the resolved secret in a `gh secret set` command. | Secret name and printed instruction diverging. |

The TTY path is tested by giving `run_review` an `ask: Callable[[str], str]`
parameter and an `interactive: bool`; `cli.main` passes `input` and
`sys.stdin.isatty()`. No test touches a real terminal.

`tests/test_templates.py` gains: both templates render with the claude
provider's values without `KeyError`, and rendered YAML parses to a mapping.

`tests/test_cli.py` gains: `agentify review <tmp> --provider claude` through
`main()` exits 0 and the file exists.

`tests/test_integration.py`: the existing level 2 conversion runs
`agentify review --provider claude --docs-review` before the converted repo's
`make check`, so the converted repo's own `tests/test_contract.py` reports
L2.3 as PASS. This is the proof that generated YAML passes the check in a
fresh venv on the pinned agentify.

Mutation check after implementing: break each named property in the
template, confirm exactly the named test fails, restore.

## 6. Verified by hand, once

Not in this change. The generated workflow is proven on GitHub only by a PR
in a repo that has the secret. wgan-synthetic has `CLAUDE_CODE_AUTH_TOKEN`;
the follow-up, if the owner wants it, is a PR there replacing
`claude-review.yml` and `docs-review.yml` with the two generated files and
reading the resulting comments. This repo has no review workflow and no
secret, and stays at L2.3 n/a.

## 7. Out of scope

- Any provider beyond `claude` and `custom`. Adding one is a row in the
  table and a row in the test parametrisation.
- Reading the git remote to fill `<owner/name>` in the printed secret step.
- Creating the secret. It is repository state, like labels.
- Editing an existing review workflow. `review` never overwrites.
- Running the L2.3 check from inside `review`. `check` exists.
- A level 3 fixer or any job that pushes.

## 8. Known failure modes

- **A `custom` action that takes its instructions under a key other than
  `prompt`.** The workflow runs but the model receives no prompt, and L2.3
  does not classify the file as a review workflow, so it reports n/a rather
  than fail. The runbook states the requirement; nothing enforces it.
- **The `claude_args` allowlist drifts from claude-code-action's tool
  names.** The action ignores an unknown tool name and the model loses
  inline comments, falling back to `gh pr comment`. The integration test
  cannot see this; only a live PR can.
- **`@@extra_with@@` indentation.** The provider produces lines indented to
  the `with:` block's depth. A provider entry with wrong indentation
  produces YAML that fails to parse; the render test in
  `tests/test_templates.py` catches it for the shipped providers, and the
  L2.3 check reports `not valid YAML` for a bad `custom` value at check time.
