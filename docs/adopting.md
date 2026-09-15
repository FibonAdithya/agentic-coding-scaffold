# Converting a repository

    agentify adopt <repo>
    agentify fill <repo>
    # write each marked section, then
    agentify check <repo>

For Python repos, `adopt` also writes `requirements-dev.txt`; install it
before running the gate:

    pip install -r requirements-dev.txt

That installs the linter, the test runner, and agentify, which the contract
self-check imports.

`adopt` writes only what is missing and prints one line per file: `wrote`,
`exists`, `appended` (the `.gitignore` block and the ruff block in
`pyproject.toml`), `raised` (the level in `.agentify.toml`), or `skipped`.
A file it reports as `exists` is yours; if it lacks something the contract
needs, `check` says what is missing, and the "What adopt writes" table in
`CONTRACT.md` names the template to copy from.

Commit the generated files before filling the markers, so the diff that adds
the project-specific content is readable on its own.

## When adopt skips a file

An existing `Makefile` without a `check` target, or an existing CI workflow
that does not run it, fails `check` with a reason naming the gap. Merging
generated content into a hand-written file is a judgement call and the tool
does not make it. Copy from the template the contract table names, keep what
the file already does, and re-run `check`.

## Filling the markers

Each marker carries its own prompt. These sections say what a good answer
looks like.

### What this project is

Two to four sentences an agent reads before anything else. Say what the
project produces, who or what consumes it, and what success means. If there
is a common misreading, say what the project is not. The reference projects
this contract came from each needed one sentence of that kind: "the target is
not a matching distribution" and "there is no database and no network
service".

### Finding invariants

An invariant is a rule that is silently wrong when violated and that no test
catches. Find them in this order:

1. Read the test suite's file names. Everything covered there is not an
   invariant; it is a test.
2. Read the configs, the data contracts, and anything with a version or
   variant number. Ask, for each: what happens if an agent changes this while
   believing it is making progress? If the answer is "a number silently means
   something else", that is an invariant.
3. Read the last twenty commit messages for reverts and "fix" commits. Each
   one is a candidate.

Write each as: the rule in bold, why it exists, and where the truth lives,
cited by anchor or symbol. Five is a typical count; more than eight means
some are tests waiting to be written.

### What requires a human

A bulleted list of decisions an agent must raise and stop on. Typical
entries: changing what a version or variant number means; tightening a
threshold or gate band; changing a pinned dependency; anything that redefines
what an existing result meant. Keep the bug-reporting paragraph the template
wrote: the label it names is what routes an issue to a person.

### Where to look

One row per recurring task, pointing at the entry point, the data contract,
the configs, or the tests for a subsystem. Cite documents by anchor and code
by symbol; the docs-reference test rejects line numbers because they rot
silently when text is inserted above them.

## Build products the docs may name

If an authoritative document names a path that is correctly absent from a
clean checkout (run directories, downloaded data), list its prefix in
`.agentify.toml`:

```toml
[docs]
ignore_references = ["runs/", "data/"]
```

## Level 2

    agentify adopt <repo> --level 2

writes two workflows and raises the level in `.agentify.toml`. Three things
then need a person, because they are repository state and not files.

### Labels

The router tells agents to file with `--label agent-reported`;
`.github/workflows/notify.yml` routes that label and `auto-bug` to the
owner; `.github/workflows/branch-hygiene.yml` keeps a branch whose PR
carries `keep-branch`. `gh issue create --label X` fails when `X` does not
exist, so create all three once:

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
