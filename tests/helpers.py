from pathlib import Path

from agentify.fill import FILL, FILL_FILES


def fill_all(root: Path) -> None:
    """Replace every fill marker in the generated files with a stand-in sentence."""
    for rel in FILL_FILES:
        target = root / rel
        if target.is_file():
            target.write_text(FILL.sub("filled.", target.read_text()))
