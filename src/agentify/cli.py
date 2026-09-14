"""agentify check | adopt | fill."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from agentify.contract import FAIL, max_level, run_adopt, run_checks
from agentify.fill import find_markers
from agentify.repo import Repo


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
        help=f"1..{max_level()} (default: highest known)",
    )
    check.add_argument("--json", action="store_true", help="machine-readable output")

    adopt = sub.add_parser("adopt", help="write the missing files; never overwrites")
    adopt.add_argument("repo", nargs="?", default=".")
    adopt.add_argument("--level", type=int, default=1)
    adopt.add_argument("--dry-run", action="store_true")

    fill = sub.add_parser("fill", help="list the <<FILL>> markers left to write")
    fill.add_argument("repo", nargs="?", default=".")
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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        repo = Repo.open(args.repo)
    except FileNotFoundError as exc:
        print(f"agentify: {exc}", file=sys.stderr)
        return 2
    if args.command == "check":
        level = args.level if args.level is not None else max_level()
        return cmd_check(repo, level, args.json)
    if args.command == "adopt":
        return cmd_adopt(repo, args.level, args.dry_run)
    return cmd_fill(repo)
