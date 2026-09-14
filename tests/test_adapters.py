from pathlib import Path

from agentify.adapters import detect_adapter
from agentify.adapters.python import PythonAdapter


def test_detects_on_pyproject_or_requirements(tmp_path: Path):
    assert detect_adapter(tmp_path) is None
    (tmp_path / "requirements.txt").write_text("")
    assert detect_adapter(tmp_path).name == "python"
    (tmp_path / "requirements.txt").unlink()
    (tmp_path / "pyproject.toml").write_text("")
    assert detect_adapter(tmp_path).name == "python"


def test_gate_body_defines_check_and_uses_tabs():
    body = PythonAdapter().gate_body()
    assert "check: lint format-check test" in body
    assert "\n\t$(RUFF) check .\n" in body
    assert "\n\t$(PYTHON) -m pytest\n" in body
    assert "|| true" not in body


def test_ci_setup_steps_install_the_pin_and_are_indented_six_spaces():
    steps = PythonAdapter().ci_setup_steps("agentify @ git+https://x@v9")
    assert '"agentify @ git+https://x@v9"' in steps
    assert all(line.startswith("      ") for line in steps.splitlines() if line.strip())
    assert "@@" not in steps


def test_ignore_patterns():
    assert PythonAdapter().ignore_patterns() == [
        "__pycache__/",
        ".venv/",
        ".ruff_cache/",
        ".pytest_cache/",
    ]


def test_resolve_symbol_finds_functions_classes_members_and_assignments(tmp_path: Path):
    f = tmp_path / "m.py"
    f.write_text(
        "X = 1\n"
        "Y: int = 2\n"
        "def fn():\n    pass\n"
        "class C:\n"
        "    attr = 3\n"
        "    def method(self):\n        pass\n"
    )
    a = PythonAdapter()
    for symbol in ("X", "Y", "fn", "C", "C.attr", "C.method"):
        assert a.resolve_symbol(f, symbol), symbol
    for symbol in ("nope", "C.nope", "fn.nope"):
        assert not a.resolve_symbol(f, symbol), symbol


def test_resolve_symbol_is_false_for_non_python_or_unparseable(tmp_path: Path):
    a = PythonAdapter()
    md = tmp_path / "x.md"
    md.write_text("# hi")
    assert not a.resolve_symbol(md, "hi")
    bad = tmp_path / "bad.py"
    bad.write_text("def (:\n")
    assert not a.resolve_symbol(bad, "x")
