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
# A backticked `*.md` glob in the authority list, e.g. `docs/datasets/*.md`.
# Kept apart from REFERENCE, whose path class excludes `*`, so prose that
# mentions a glob is never treated as a single path.
GLOB_REFERENCE = re.compile(
    r"`(?P<pattern>[A-Za-z0-9_.][A-Za-z0-9_./*-]*\*[A-Za-z0-9_./*-]*\.md)`"
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
    wanted = f"## {heading}"
    start = next(
        (i + 1 for i, line in enumerate(lines) if line.strip() == wanted), None
    )
    if start is None:
        return ""
    body: list[str] = []
    for line in lines[start:]:
        if line.strip().startswith("## "):
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


def expand_glob(repo: Repo, pattern: str) -> list[Path]:
    """Files under the root matching a `*.md` glob, sorted; nothing outside docs/ai/ excluded here."""
    return sorted(
        p for p in repo.root.glob(pattern) if p.is_file() and repo.contains_path(p)
    )


def authoritative_docs(repo: Repo) -> list[Path]:
    """Root docs plus every .md the router's source-of-truth section names outside docs/ai/.

    A backticked `*.md` glob in that section expands to every file it matches.
    """
    docs = [repo.path(name) for name in ROOT_DOCS if repo.exists(name)]
    agents_path = repo.path("AGENTS.md")
    agents_text = (
        agents_path.read_text(encoding="utf-8", errors="replace")
        if agents_path.exists()
        else ""
    )
    listed = section(agents_text, "Source of truth, in order")
    candidates: list[Path] = []
    for match in REFERENCE.finditer(listed):
        path = match["path"]
        if path.endswith(".md") and repo.contains(path):
            candidates.append(repo.path(path))
    for match in GLOB_REFERENCE.finditer(listed):
        candidates.extend(expand_glob(repo, match["pattern"]))
    for target in candidates:
        rel = (
            target.relative_to(repo.root).as_posix()
            if repo.contains_path(target)
            else ""
        )
        if rel.startswith(NOTES_DIR):
            continue
        if target.is_file() and target not in docs:
            docs.append(target)
    return docs


def _target(repo: Repo, doc: Path, path: str) -> Path | None:
    """The file `path` names, tried relative to `doc`'s directory and then to the root.

    Candidates that escape the repository are skipped, so a doc-relative `..`
    can never reach outside; None means nothing inside the repository exists.
    """
    for candidate in (doc.parent / path, repo.root / path):
        if repo.contains_path(candidate) and candidate.exists():
            return candidate
    return None


def _resolve(repo: Repo, doc: Path, match: re.Match[str]) -> str | None:
    """The reason a reference fails to resolve, or None if it resolves."""
    if match["line"]:
        return LINE_REASON
    path = match["path"]
    target = _target(repo, doc, path)
    if target is None:
        if not repo.contains(path):
            return "reference escapes the repository"
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
                reason = _resolve(repo, doc, match)
                if reason is not None:
                    found.append(
                        Unresolved(rel, number, match.group(0).strip("`"), reason)
                    )
    return found
