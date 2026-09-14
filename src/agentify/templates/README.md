# @@project_name@@

<<FILL: One paragraph: what this project does and who uses it. Then a Quick
start section with the commands a new person runs on day one, in the order
they run them.>>

If you are a coding agent, read `AGENTS.md` first. It says which document is
authoritative, what must not be broken, and what needs a human.

## Checks

    pip install -r requirements-dev.txt

That installs the linter, the test runner, and agentify, which the contract
self-check imports.

    make check

That is the gate CI runs. It must be green before a change is done.
