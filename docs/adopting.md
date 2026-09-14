# Converting a repository

    agentify adopt <repo>
    agentify fill <repo>
    # write each marked section, then
    agentify check <repo>

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
