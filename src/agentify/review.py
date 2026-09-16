"""agentify review: write a PR review workflow for the provider you name.

`adopt` writes nothing that depends on any one agent. This command does,
deliberately and only when asked: the model step is a value the adopter
names, substituted into a provider-neutral template.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentify.repo import Repo, write_if_missing
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
