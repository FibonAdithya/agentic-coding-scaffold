"""Small Markdown helpers shared by the checks and the docs scanner."""

from __future__ import annotations


def lines_outside_fences(text: str) -> list[tuple[int, str]]:
    """(1-based line number, line) for every line not inside a ``` fence."""
    out: list[tuple[int, str]] = []
    in_fence = False
    for number, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            out.append((number, line))
    return out
