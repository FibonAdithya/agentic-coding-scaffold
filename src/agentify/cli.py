"""agentify check | adopt | fill | review."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import asdict

from agentify.config import load_config
from agentify.contract import FAIL, max_level, run_adopt, run_checks
from agentify.fill import find_markers
from agentify.repo import Repo
from agentify.review import MissingOption, resolve_provider, run_review


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentify",
        description="A contract for agent-operable repositories: check it, adopt it, fill it in.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser(
        "check", help="report each contract item as pass, fail, or n/a"
    )
    check.add_argument("repo", nargs="?", default=".")
    check.add_argument(
        "--level",
        type=int,
        default=None,
        choices=range(1, max_level() + 1),
        help=f"1..{max_level()} (default: the level .agentify.toml declares, else the highest known)",
    )
    check.add_argument("--json", action="store_true", help="machine-readable output")

    adopt = sub.add_parser("adopt", help="write the missing files; never overwrites")
    adopt.add_argument("repo", nargs="?", default=".")
    adopt.add_argument(
        "--level", type=int, default=1, choices=range(1, max_level() + 1)
    )
    adopt.add_argument("--dry-run", action="store_true")

    fill = sub.add_parser("fill", help="list the <<FILL>> markers left to write")
    fill.add_argument("repo", nargs="?", default=".")

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
    return parser


def cmd_check(repo: Repo, level: int, as_json: bool) -> int:
    results = run_checks(repo, level)
    failing = [r for r in results if r.status == FAIL]
    if as_json:
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        for r in results:
            print(f"{r.item:<5} {r.status:<4} {r.reason}")
        verdict = "PASS" if not failing else f"FAIL ({len(failing)} failing)"
        print(f"level {level}: {verdict}")
    return 1 if failing else 0


def cmd_adopt(repo: Repo, level: int, dry_run: bool) -> int:
    for action in run_adopt(repo, level, dry_run):
        print(action)
    return 0


def cmd_fill(repo: Repo) -> int:
    markers = find_markers(repo.root)
    for m in markers:
        print(f"{m.file}:{m.line}: {m.prompt}")
    print(f"{len(markers)} marker(s) remaining" if markers else "no markers remaining")
    return 1 if markers else 0


def interactive_ask() -> Callable[[str], str] | None:
    """`input` on a terminal, else None: an agent driving the CLI must get an
    error for a missing flag, never a prompt that waits forever."""
    stdin = sys.stdin
    return input if stdin is not None and stdin.isatty() else None


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


def _default_level(repo: Repo) -> int:
    """The level .agentify.toml declares, when it is one this agentify knows;
    otherwise the highest known. A level 1 repo must not exit 1 on level 2
    items it never adopted."""
    declared = load_config(repo.root).level
    top = max_level()
    return declared if 1 <= declared <= top else top


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        repo = Repo.open(args.repo)
    except FileNotFoundError as exc:
        print(f"agentify: {exc}", file=sys.stderr)
        return 2
    if args.command == "check":
        level = args.level if args.level is not None else _default_level(repo)
        return cmd_check(repo, level, args.json)
    if args.command == "adopt":
        return cmd_adopt(repo, args.level, args.dry_run)
    if args.command == "review":
        return cmd_review(parser, repo, args)
    return cmd_fill(repo)
