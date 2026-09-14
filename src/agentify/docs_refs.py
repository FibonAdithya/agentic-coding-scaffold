"""Mechanical resolution of backticked references in the authoritative docs.

Documents are cited by anchor and code by symbol; both survive edits above
them. Line numbers do not, so a `path:123` citation is reported as a defect
outright. Nothing here judges whether prose is true.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from agentify.config import load_config
from agentify.markdown import lines_outside_fences
from agentify.repo import Repo

EXTENSIONS = r"md|py|ya?ml|json|toml|txt|sh|cfg|ini|csv|npy"
REFERENCE = re.compile(
    r"`(?P<path>"
    r"Makefile"
    r"|[A-Za-z0-9_.][A-Za-z0-9_./-]*/"
    rf"|[A-Za-z0-9_.][A-Za-z0-9_./-]*\.(?:{EXTENSIONS})"
    r")"
    r"(?:#(?P<anchor>[A-Za-z0-9_-]+)"
    r"|::(?P<symbol>[A-Za-z_][A-Za-z0-9_.]*)"
    r"|:(?P<line>\d+(?:-\d+)?))?`"
)
ROOT_DOCS = ("AGENTS.md", "CLAUDE.md", "README.md")
NOTES_DIR = "docs/ai/"
LINE_REASON = "line-number citation; cite by #anchor or ::symbol"


@dataclass(frozen=True)
class Unresolved:
    doc: str
    line: int
    ref: str
    reason: str


def section(text: str, heading: str) -> str:
    """The lines under `## {heading}` up to the next `## `, or empty."""
    lines = text.splitlines()
    try:
        start = lines.index(f"## {heading}") + 1
    except ValueError:
        return ""
    body: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body)


def slug(heading: str) -> str:
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def anchors(markdown: str) -> set[str]:
    return {
        slug(line.lstrip("#"))
        for _, line in lines_outside_fences(markdown)
        if line.startswith("#")
    }


def authoritative_docs(repo: Repo) -> list[Path]:
    """Root docs plus every .md the router's source-of-truth section names outside docs/ai/."""
    docs = [repo.path(name) for name in ROOT_DOCS if repo.exists(name)]
    agents_path = repo.path("AGENTS.md")
    agents_text = (
        agents_path.read_text(encoding="utf-8", errors="replace")
        if agents_path.exists()
        else ""
    )
    listed = section(agents_text, "Source of truth, in order")
    for match in REFERENCE.finditer(listed):
        path = match["path"]
        if not path.endswith(".md") or path.startswith(NOTES_DIR):
            continue
        target = repo.path(path)
        if target.is_file() and target not in docs:
            docs.append(target)
    return docs


def _resolve(repo: Repo, match: re.Match[str]) -> str | None:
    """The reason a reference fails to resolve, or None if it resolves."""
    if match["line"]:
        return LINE_REASON
    path = match["path"]
    if not repo.contains(path):
        return "reference escapes the repository"
    target = repo.path(path)
    if not target.exists():
        return "path does not exist"
    if match["anchor"] and (
        target.suffix != ".md"
        or match["anchor"]
        not in anchors(target.read_text(encoding="utf-8", errors="replace"))
    ):
        return "anchor not found"
    if (
        match["symbol"]
        and repo.adapter is not None
        and not repo.adapter.resolve_symbol(target, match["symbol"])
    ):
        return "symbol not found"
    return None


def scan_docs(repo: Repo) -> list[Unresolved]:
    ignore = load_config(repo.root).ignore_references
    found: list[Unresolved] = []
    for doc in authoritative_docs(repo):
        rel = str(doc.relative_to(repo.root))
        for number, line in lines_outside_fences(
            doc.read_text(encoding="utf-8", errors="replace")
        ):
            for match in REFERENCE.finditer(line):
                if any(match["path"].startswith(prefix) for prefix in ignore):
                    continue
                reason = _resolve(repo, match)
                if reason is not None:
                    found.append(
                        Unresolved(rel, number, match.group(0).strip("`"), reason)
                    )
    return found
