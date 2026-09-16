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
    # The header comment names pull_request_target as the trigger never to
    # use, so check the parsed trigger rather than the text.
    assert list(parsed[True]) == ["pull_request"]
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
