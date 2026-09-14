"""Verbatim template files with `@@name@@` placeholders.

No template language. Anything conditional lives in the adapter that
supplies the value, so a template reads exactly like the file it produces.
`@@` was chosen because workflow files contain `${{ }}`.
"""

from __future__ import annotations

import re
from importlib import resources
from pathlib import Path

PLACEHOLDER = re.compile(r"@@([a-z_]+)@@")


def _template_dir() -> Path:
    return Path(str(resources.files("agentify") / "templates"))


def load(name: str) -> str:
    return (_template_dir() / name).read_text(encoding="utf-8")


def render(name: str, **values: str) -> str:
    text = load(name)

    def substitute(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in values:
            raise KeyError(f"template {name}: no value for @@{key}@@")
        return values[key]

    return PLACEHOLDER.sub(substitute, text)
