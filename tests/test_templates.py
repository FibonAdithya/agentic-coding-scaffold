import pytest

from agentify.templates import load, render


def test_claude_md_template_points_at_agents_md():
    assert load("CLAUDE.md").replace("`", "").strip() == "See AGENTS.md."


def test_render_substitutes_every_placeholder(tmp_path, monkeypatch):
    import agentify.templates as t

    (tmp_path / "x.txt").write_text("hello @@who@@, @@who@@ again; @@what@@\n")
    monkeypatch.setattr(t, "_template_dir", lambda: tmp_path)
    assert render("x.txt", who="a", what="b") == "hello a, a again; b\n"


def test_render_raises_on_a_placeholder_with_no_value(tmp_path, monkeypatch):
    import agentify.templates as t

    (tmp_path / "x.txt").write_text("@@missing@@")
    monkeypatch.setattr(t, "_template_dir", lambda: tmp_path)
    with pytest.raises(KeyError, match="missing"):
        render("x.txt")


def test_render_leaves_github_expressions_alone(tmp_path, monkeypatch):
    import agentify.templates as t

    (tmp_path / "x.yml").write_text("group: ci-${{ github.ref }}\n")
    monkeypatch.setattr(t, "_template_dir", lambda: tmp_path)
    assert render("x.yml") == "group: ci-${{ github.ref }}\n"


def test_python_templates_are_lint_and_format_clean(tmp_path):
    """A generated test file goes straight into another repo's `make check`."""
    import shutil
    import subprocess

    from agentify.templates import _template_dir

    for tmpl in sorted(_template_dir().glob("*.py.tmpl")):
        target = tmp_path / tmpl.name.removesuffix(".tmpl")
        shutil.copy(tmpl, target)
        for args in (
            ["check", "--select", "E,F,I,W,UP", "--ignore", "E501"],
            ["format", "--check"],
        ):
            proc = subprocess.run(
                ["ruff", *args, "--isolated", str(target)],
                capture_output=True,
                text=True,
            )
            assert proc.returncode == 0, (
                f"{tmpl.name}: ruff {args[0]}\n{proc.stdout}{proc.stderr}"
            )
