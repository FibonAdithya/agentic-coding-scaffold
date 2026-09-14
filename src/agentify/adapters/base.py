"""The language adapter boundary.

Everything language-specific that adopt or check needs is one of these
methods. Adding a language is one class implementing them, registered in
`agentify.adapters.ADAPTERS`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class Adapter(Protocol):
    name: str

    def detect(self, root: Path) -> bool:
        """True if this adapter applies to the repo at `root`."""
        ...

    def gate_body(self) -> str:
        """Makefile text (tab-indented recipes) defining `check` and its parts."""
        ...

    def ci_setup_steps(self, agentify_pin: str) -> str:
        """YAML for the steps that install the toolchain, indented six spaces."""
        ...

    def ignore_patterns(self) -> list[str]:
        """Cache and environment directories `.gitignore` must cover."""
        ...

    def resolve_symbol(self, file: Path, symbol: str) -> bool:
        """True if `symbol` (dotted, one level deep) is defined in `file`."""
        ...
