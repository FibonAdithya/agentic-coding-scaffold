"""The repository under check or conversion, and the two ways files get written."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agentify.adapters import Adapter, detect_adapter


@dataclass(frozen=True)
class Repo:
    root: Path
    adapter: Adapter | None

    @classmethod
    def open(cls, path: str | Path) -> Repo:
        root = Path(path).resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"not a directory: {root}")
        return cls(root=root, adapter=detect_adapter(root))

    @property
    def name(self) -> str:
        return self.root.name

    def path(self, rel: str) -> Path:
        return self.root / rel

    def exists(self, rel: str) -> bool:
        return (self.root / rel).exists()

    def contains(self, rel: str) -> bool:
        """True if `rel`, resolved against root, is root or under it.

        A doc reference like `../outside.md` can resolve to something that
        exists on disk without being part of this repository at all.
        """
        target = (self.root / rel).resolve()
        return target == self.root or self.root in target.parents

    def read(self, rel: str) -> str | None:
        target = self.root / rel
        if not target.is_file():
            return None
        return target.read_text(encoding="utf-8")


def write_if_missing(repo: Repo, rel: str, content: str, dry_run: bool) -> str:
    """Create `rel` with `content` unless it exists. Never overwrites."""
    target = repo.root / rel
    if target.exists() or target.is_symlink():
        # A dangling symlink is not "exists" under Path.exists() (which
        # follows the link), but writing through it would create a file at
        # whatever it points to -- outside our control and possibly outside
        # the repo. Treat it as an existing, owned file: never overwritten.
        return f"exists   {rel}"
    if dry_run:
        return f"would write {rel}"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"wrote    {rel}"


def append_text(repo: Repo, rel: str, text: str, dry_run: bool) -> str:
    """Append `text` (newline-terminated) to `rel`, separated by a blank line."""
    if dry_run:
        return f"would append {rel}"
    target = repo.root / rel
    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    if existing and not existing.endswith("\n"):
        existing += "\n"
    if existing:
        existing += "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(existing + text, encoding="utf-8")
    return f"appended {rel}"
