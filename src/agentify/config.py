""".agentify.toml: the one file adopt owns and may edit in place."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from agentify.templates import render

CONFIG_FILE = ".agentify.toml"
LEVEL_LINE = re.compile(r"(?m)^level\s*=\s*\d+")


@dataclass(frozen=True)
class Config:
    level: int = 0
    ignore_references: tuple[str, ...] = ()


def load_config(root: Path) -> Config:
    target = root / CONFIG_FILE
    if not target.is_file():
        return Config()
    data = tomllib.loads(target.read_text(encoding="utf-8"))
    contract = data.get("contract", {})
    docs = data.get("docs", {})
    return Config(
        level=int(contract.get("level", 0)),
        ignore_references=tuple(docs.get("ignore_references", [])),
    )


def ensure_level(root: Path, level: int, dry_run: bool) -> str:
    """Write the config with `level` if absent; raise a lower level; never lower one."""
    target = root / CONFIG_FILE
    if not target.is_file():
        if dry_run:
            return f"would write {CONFIG_FILE}"
        target.write_text(render("agentify.toml", level=str(level)), encoding="utf-8")
        return f"wrote    {CONFIG_FILE}"
    current = load_config(root).level
    if current >= level:
        return f"exists   {CONFIG_FILE} (level {current})"
    if dry_run:
        return f"would raise {CONFIG_FILE} level {current} -> {level}"
    text = target.read_text(encoding="utf-8")
    target.write_text(
        LEVEL_LINE.sub(f"level = {level}", text, count=1), encoding="utf-8"
    )
    return f"raised   {CONFIG_FILE} level {current} -> {level}"
