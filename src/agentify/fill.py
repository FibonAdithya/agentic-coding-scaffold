"""`<<FILL: ...>>` markers: the parts of a generated file only a person or an
agent who has read the project can write."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

FILL = re.compile(r"<<FILL:(.*?)>>", re.DOTALL)

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
        for match in FILL.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            found.append(Marker(rel, line, " ".join(match.group(1).split())))
    return found
