import hashlib
import json
from pathlib import Path

from agentify.cli import main
from helpers import fill_all


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        h.update(str(path.relative_to(root)).encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def test_check_on_a_bare_repo_lists_every_item_and_exits_1(python_repo: Path, capsys):
    assert main(["check", str(python_repo)]) == 1
    out = capsys.readouterr().out
    for item in ("L1.1", "L1.2", "L1.3", "L1.4", "L1.5", "L1.6", "L1.7"):
        assert item in out
    # L1.5 passes vacuously: with no AGENTS.md or README.md there is nothing to scan.
    assert "L1.5  pass" in out
    # Every item except L1.5 fails on a bare repo. A task that adds an item
    # updates this line: it is the record of what a bare repo is missing.
    assert "L2.1  fail" in out
    assert "L2.2  fail" in out
    assert out.strip().endswith("level 2: FAIL (8 failing)")


def test_check_json_output(python_repo: Path, capsys):
    main(["check", str(python_repo), "--json"])
    rows = json.loads(capsys.readouterr().out)
    assert rows[0] == {"item": "L1.1", "status": "fail", "reason": "AGENTS.md missing"}


def test_adopt_then_fill_then_check_passes(python_repo: Path, capsys):
    assert main(["adopt", str(python_repo)]) == 0
    out = capsys.readouterr().out
    assert "wrote    AGENTS.md" in out and "wrote    tests/test_contract.py" in out
    assert "wrote    requirements-dev.txt" in out
    assert main(["check", str(python_repo)]) == 1
    out = capsys.readouterr().out
    assert "L1.1  fail" in out and "L1.2  pass" in out and "L1.3  pass" in out
    assert main(["fill", str(python_repo)]) == 1
    listing = capsys.readouterr().out
    assert listing.count("AGENTS.md:") >= 4 and "README.md:" in listing
    fill_all(python_repo)
    assert main(["fill", str(python_repo)]) == 0
    assert main(["check", str(python_repo)]) == 0
    assert capsys.readouterr().out.strip().endswith("level 1: PASS")


def test_adopt_is_idempotent_and_never_overwrites(python_repo: Path, capsys):
    (python_repo / "Makefile").write_text("check:\n\techo mine\n")
    main(["adopt", str(python_repo)])
    capsys.readouterr()  # drain the first run's output; the assertion below is about the second
    before = tree_hash(python_repo)
    assert (python_repo / "Makefile").read_text() == "check:\n\techo mine\n"
    main(["adopt", str(python_repo)])
    out = capsys.readouterr().out
    assert "wrote" not in out and "appended" not in out
    assert tree_hash(python_repo) == before


def test_adopt_dry_run_writes_nothing(python_repo: Path, capsys):
    before = tree_hash(python_repo)
    assert main(["adopt", str(python_repo), "--dry-run"]) == 0
    assert "would write AGENTS.md" in capsys.readouterr().out
    assert tree_hash(python_repo) == before


def test_fill_exits_1_on_an_unterminated_marker(tmp_path: Path, capsys):
    (tmp_path / "AGENTS.md").write_text("# x\n\n<<FILL: no closing\n")
    assert main(["fill", str(tmp_path)]) == 1
    assert "unterminated marker: add the closing >>" in capsys.readouterr().out


def test_missing_repo_path_is_an_error(tmp_path: Path):
    assert main(["check", str(tmp_path / "nope")]) == 2


def _two_level_registry(monkeypatch):
    import agentify.contract as c
    from agentify.contract import PASS, Item, Result

    items = [
        Item("T.1", 1, "one", lambda r: Result("T.1", PASS, "ok"), lambda r, d: []),
        Item("T.2", 2, "two", lambda r: Result("T.2", PASS, "ok"), lambda r, d: []),
    ]
    monkeypatch.setattr(c, "registry", lambda: items)


def test_check_defaults_to_the_declared_level(tmp_path: Path, monkeypatch, capsys):
    _two_level_registry(monkeypatch)
    (tmp_path / ".agentify.toml").write_text("[contract]\nlevel = 1\n")
    assert main(["check", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "T.1" in out and "T.2" not in out and "level 1:" in out


def test_check_defaults_to_the_highest_level_without_a_config(
    tmp_path: Path, monkeypatch, capsys
):
    _two_level_registry(monkeypatch)
    assert main(["check", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "T.2" in out and "level 2:" in out


def test_check_ignores_a_declared_level_above_the_maximum(
    tmp_path: Path, monkeypatch, capsys
):
    _two_level_registry(monkeypatch)
    (tmp_path / ".agentify.toml").write_text("[contract]\nlevel = 9\n")
    assert main(["check", str(tmp_path)]) == 0
    assert "level 2:" in capsys.readouterr().out
