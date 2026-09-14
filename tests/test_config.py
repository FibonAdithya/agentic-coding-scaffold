from pathlib import Path

from agentify.config import CONFIG_FILE, Config, ensure_level, load_config


def test_missing_config_is_level_zero(tmp_path: Path):
    assert load_config(tmp_path) == Config()


def test_load_reads_level_and_ignore_prefixes(tmp_path: Path):
    (tmp_path / CONFIG_FILE).write_text(
        '[contract]\nlevel = 2\n\n[docs]\nignore_references = ["runs/", "data/"]\n'
    )
    cfg = load_config(tmp_path)
    assert cfg.level == 2
    assert cfg.ignore_references == ("runs/", "data/")


def test_ensure_level_writes_when_absent(tmp_path: Path):
    assert ensure_level(tmp_path, 1, dry_run=False) == f"wrote    {CONFIG_FILE}"
    assert load_config(tmp_path).level == 1
    assert "ignore_references = []" in (tmp_path / CONFIG_FILE).read_text()


def test_ensure_level_raises_but_never_lowers(tmp_path: Path):
    ensure_level(tmp_path, 1, dry_run=False)
    assert (
        ensure_level(tmp_path, 3, dry_run=False)
        == f"raised   {CONFIG_FILE} level 1 -> 3"
    )
    assert load_config(tmp_path).level == 3
    assert (
        ensure_level(tmp_path, 2, dry_run=False) == f"exists   {CONFIG_FILE} (level 3)"
    )
    assert load_config(tmp_path).level == 3


def test_ensure_level_preserves_the_rest_of_the_file(tmp_path: Path):
    (tmp_path / CONFIG_FILE).write_text(
        '[contract]\nlevel = 1\n\n[docs]\nignore_references = ["runs/"]\n'
    )
    ensure_level(tmp_path, 2, dry_run=False)
    assert load_config(tmp_path) == Config(level=2, ignore_references=("runs/",))


def test_ensure_level_dry_run_writes_nothing(tmp_path: Path):
    assert ensure_level(tmp_path, 1, dry_run=True) == f"would write {CONFIG_FILE}"
    assert not (tmp_path / CONFIG_FILE).exists()
    (tmp_path / CONFIG_FILE).write_text("[contract]\nlevel = 1\n")
    assert (
        ensure_level(tmp_path, 2, dry_run=True)
        == f"would raise {CONFIG_FILE} level 1 -> 2"
    )
    assert load_config(tmp_path).level == 1
