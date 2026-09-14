from __future__ import annotations

from pathlib import Path

from agentify.adapters.base import Adapter

ADAPTERS: list[Adapter] = []


def detect_adapter(root: Path) -> Adapter | None:
    """The first registered adapter whose detect() fires, else None."""
    for adapter in ADAPTERS:
        if adapter.detect(root):
            return adapter
    return None
