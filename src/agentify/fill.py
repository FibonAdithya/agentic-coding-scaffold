"""`<<FILL: ...>>` markers: the parts of a generated file only a person or an
agent who has read the project can write."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

FILL = re.compile(r"<<FILL:(.*?)>>", re.DOTALL)
UNTERMINATED = "unterminated marker: add the closing >>"

# Only files adopt writes can carry markers, so only those are scanned. This
# keeps the agentify repo's own template sources out of its own worklist.
FILL_FILES = ("AGENTS.md", "README.md", "Makefile", ".github/workflows/ci.yml")


@dataclass(frozen=True)
class Marker:
    file: str
    line: int
    prompt: str


def find_markers(root: Path) -> list[Marker]:
    found: list[Marker] = []
    for rel in FILL_FILES:
        target = root / rel
        if not target.is_file():
            continue
        text = target.read_text(encoding="utf-8")
        positioned: list[tuple[int, Marker]] = []
        complete_starts: set[int] = set()
        for match in FILL.finditer(text):
            complete_starts.add(match.start())
            line = text.count("\n", 0, match.start()) + 1
            positioned.append(
                (match.start(), Marker(rel, line, " ".join(match.group(1).split())))
            )
        # `<<FILL:` (with the colon) is what marks an attempted marker; bare
        # mentions of "<<FILL>>" in prose describing the syntax (as this
        # very file's README does) are not markers and must not be flagged.
        for stray in re.finditer(r"<<FILL:", text):
            if stray.start() in complete_starts:
                continue  # the start of a complete marker, already recorded above
            line = text.count("\n", 0, stray.start()) + 1
            positioned.append((stray.start(), Marker(rel, line, UNTERMINATED)))
        found.extend(marker for _, marker in sorted(positioned, key=lambda p: p[0]))
    return found
