from pathlib import Path

from agentify.contract import FAIL, PASS, Item, Result, run_adopt, run_checks
from agentify.repo import Repo


def test_run_checks_filters_by_level_and_survives_a_crashing_check(
    monkeypatch, tmp_path: Path
):
    import agentify.contract as c

    def boom(repo: Repo) -> Result:
        raise RuntimeError("kaboom")

    items = [
        Item("T.1", 1, "ok", lambda r: Result("T.1", PASS, "fine"), lambda r, d: []),
        Item("T.2", 1, "crash", boom, lambda r, d: []),
        Item("T.3", 2, "later", lambda r: Result("T.3", PASS, "fine"), lambda r, d: []),
    ]
    monkeypatch.setattr(c, "registry", lambda: items)
    results = run_checks(Repo.open(tmp_path), level=1)
    assert [r.item for r in results] == ["T.1", "T.2"]
    assert results[1].status == FAIL
    assert "RuntimeError: kaboom" in results[1].reason


def test_run_adopt_runs_generators_up_to_level_then_writes_config(
    monkeypatch, tmp_path: Path
):
    import agentify.contract as c

    items = [
        Item(
            "T.1", 1, "a", lambda r: Result("T.1", PASS, ""), lambda r, d: ["wrote a"]
        ),
        Item(
            "T.3", 2, "b", lambda r: Result("T.3", PASS, ""), lambda r, d: ["wrote b"]
        ),
    ]
    monkeypatch.setattr(c, "registry", lambda: items)
    actions = run_adopt(Repo.open(tmp_path), level=1, dry_run=False)
    assert actions == ["wrote a", "wrote    .agentify.toml"]
    assert (tmp_path / ".agentify.toml").exists()
