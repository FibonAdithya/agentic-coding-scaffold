from pathlib import Path

import pytest

PYPROJECT = """\
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "demo"
version = "0.0.1"
requires-python = ">=3.11"

[tool.setuptools.packages.find]
where = ["src"]
"""


@pytest.fixture
def python_repo(tmp_path: Path) -> Path:
    """A minimal, valid Python project with none of the files adopt writes."""
    (tmp_path / "pyproject.toml").write_text(PYPROJECT)
    (tmp_path / "src/demo").mkdir(parents=True)
    (tmp_path / "src/demo/__init__.py").write_text(
        "def answer() -> int:\n    return 42\n"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_demo.py").write_text(
        "from demo import answer\n\n\ndef test_answer():\n    assert answer() == 42\n"
    )
    return tmp_path
