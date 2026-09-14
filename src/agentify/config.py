""".agentify.toml: the one file adopt owns and may edit in place."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from agentify.templates import render

CONFIG_FILE = ".agentify.toml"


@dataclass(frozen=True)
class Config:
    level: int = 0
    ignore_references: tuple[str, ...] = ()


def _set_contract_level(text: str, level: int) -> str:
    """Set the level in [contract] table, handling all cases."""
    lines = text.split("\n")
    contract_idx = None

    # Find [contract] table header
    for i, line in enumerate(lines):
        if line.strip() == "[contract]":
            contract_idx = i
            break

    if contract_idx is None:
        # No [contract] table: append it with level
        if text and not text.endswith("\n"):
            text += "\n"
        return text + "\n[contract]\nlevel = " + str(level) + "\n"

    # [contract] table exists: find its level line or insert position
    level_idx = None

    # Scan lines after [contract] to find level line or next table
    for i in range(contract_idx + 1, len(lines)):
        line = lines[i]
        if line.startswith("["):
            break
        if level_idx is None:
            # Check if this line is a level assignment
            import re

            match = re.match(r"^(\s*)level\s*=\s*\d+(.*)$", line)
            if match:
                level_idx = i
                # Preserve any trailing comment
                trailing = match.group(2)
                lines[i] = f"level = {level}{trailing}"
                break

    if level_idx is None:
        # No level line found in [contract] table: insert after header
        lines.insert(contract_idx + 1, f"level = {level}")

    return "\n".join(lines)


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
    target.write_text(_set_contract_level(text, level), encoding="utf-8")
    return f"raised   {CONFIG_FILE} level {current} -> {level}"
