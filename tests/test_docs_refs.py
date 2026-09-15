from pathlib import Path

from agentify.docs_refs import (
    REFERENCE,
    Unresolved,
    anchors,
    authoritative_docs,
    scan_docs,
    section,
    slug,
)
from agentify.repo import Repo

AGENTS = """\
# Agent guide

## Source of truth, in order

1. The code in `src/`.
2. `GUIDE.md` and `docs/ai/README.md`.

## Where to look

See `GUIDE.md#setup`.
"""


def test_reference_regex_shapes():
    def m(s):
        match = REFERENCE.search(s)
        return match and (
            match["path"],
            match["anchor"],
            match["symbol"],
            match["line"],
        )

    assert m("`README.md`") == ("README.md", None, None, None)
    assert m("`docs/ai/`") == ("docs/ai/", None, None, None)
    assert m("`Makefile`") == ("Makefile", None, None, None)
    assert m("`.github/workflows/ci.yml`") == (
        ".github/workflows/ci.yml",
        None,
        None,
        None,
    )
    assert m("`GUIDE.md#some-anchor`") == ("GUIDE.md", "some-anchor", None, None)
    assert m("`src/m.py::C.method`") == ("src/m.py", None, "C.method", None)
    assert m("`src/m.py:12-14`") == ("src/m.py", None, None, "12-14")
    assert m("`make check`") is None
    assert m("`/abs/path.md`") is None


def test_slug_matches_github_anchors():
    assert slug('What "done" means') == "what-done-means"
    assert slug("Source of truth, in order") == "source-of-truth-in-order"
    assert slug("ANN difficulty — the gate") == "ann-difficulty--the-gate"
    assert slug("generator_type") == "generator_type"


def test_anchors_skip_fenced_code():
    md = "# Top\n```\n# not a heading\n```\n## Real one\n"
    assert anchors(md) == {"top", "real-one"}


def test_section_returns_body_until_next_h2():
    assert (
        section(AGENTS, "Source of truth, in order").strip().startswith("1. The code")
    )
    assert "Where to look" not in section(AGENTS, "Source of truth, in order")
    assert section(AGENTS, "Nope") == ""


def test_section_matches_a_heading_with_trailing_whitespace():
    text = "# x\n\n## Source of truth, in order \n\n1. `README.md`.\n"
    assert section(text, "Source of truth, in order").strip() == "1. `README.md`."


def test_authoritative_docs_are_root_docs_plus_listed_md_outside_docs_ai(
    tmp_path: Path,
):
    (tmp_path / "AGENTS.md").write_text(AGENTS)
    (tmp_path / "README.md").write_text("")
    (tmp_path / "GUIDE.md").write_text("")
    (tmp_path / "docs/ai").mkdir(parents=True)
    (tmp_path / "docs/ai/README.md").write_text("")
    names = [p.name for p in authoritative_docs(Repo.open(tmp_path))]
    assert names == ["AGENTS.md", "README.md", "GUIDE.md"]


def test_scan_reports_each_failure_kind(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text(AGENTS)
    (tmp_path / "GUIDE.md").write_text(
        "# Guide\n\n## Setup\n\n`missing.md`, `GUIDE.md#nope`, `src/m.py::gone`, `src/m.py:3`\n"
        "```\n`ignored/in/fence.md`\n```\n"
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src/m.py").write_text("def here():\n    pass\n")
    (tmp_path / "pyproject.toml").write_text("")
    (tmp_path / "docs/ai").mkdir(parents=True)
    (tmp_path / "docs/ai/README.md").write_text("")
    found = scan_docs(Repo.open(tmp_path))
    assert found == [
        Unresolved("GUIDE.md", 5, "missing.md", "path does not exist"),
        Unresolved("GUIDE.md", 5, "GUIDE.md#nope", "anchor not found"),
        Unresolved("GUIDE.md", 5, "src/m.py::gone", "symbol not found"),
        Unresolved(
            "GUIDE.md",
            5,
            "src/m.py:3",
            "line-number citation; cite by #anchor or ::symbol",
        ),
    ]


def test_reference_escaping_the_repo_root_is_unresolved_even_if_it_exists(
    tmp_path: Path,
):
    root = tmp_path / "repo"
    root.mkdir()
    (tmp_path / "outside.md").write_text("# Outside\n")
    (root / "AGENTS.md").write_text("# x\n\nSee `../outside.md`.\n")
    found = scan_docs(Repo.open(root))
    assert found == [
        Unresolved("AGENTS.md", 3, "../outside.md", "reference escapes the repository")
    ]


def test_symbols_are_only_checked_with_an_adapter(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("`x.py::whatever`\n")
    (tmp_path / "x.py").write_text("")
    assert scan_docs(Repo.open(tmp_path)) == []


def test_ignore_references_prefixes_are_exempt(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text("`runs/v0/summary.json`\n")
    assert len(scan_docs(Repo.open(tmp_path))) == 1
    (tmp_path / ".agentify.toml").write_text('[docs]\nignore_references = ["runs/"]\n')
    assert scan_docs(Repo.open(tmp_path)) == []


def test_non_utf8_docs_do_not_crash_the_scan(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_bytes(b"# x\n\nSee `GUIDE.md#setup` and \xff\xfe.\n")
    (tmp_path / "GUIDE.md").write_bytes(b"# Guide\n\n## Setup\n\xff\n")
    assert scan_docs(Repo.open(tmp_path)) == []


def test_references_resolve_relative_to_the_citing_document_first(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text(
        "## Source of truth, in order\n\n1. `docs/guide/GUIDE.md`.\n"
    )
    (tmp_path / "docs/guide/specs").mkdir(parents=True)
    (tmp_path / "docs/guide/notes.md").write_text("# Top\n")
    (tmp_path / "docs/guide/GUIDE.md").write_text(
        "# Guide\n\nSee `specs/`, `notes.md#top`, and the root `README.md`.\n"
    )
    (tmp_path / "README.md").write_text("# r\n")
    assert scan_docs(Repo.open(tmp_path)) == []


def test_doc_relative_anchor_is_checked_against_the_doc_relative_target(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text(
        "## Source of truth, in order\n\n1. `docs/GUIDE.md`.\n"
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/notes.md").write_text("# Other\n")
    (tmp_path / "notes.md").write_text("# Top\n")
    (tmp_path / "docs/GUIDE.md").write_text("`notes.md#top`\n")
    # docs/notes.md exists and wins over the root notes.md, and it lacks the anchor.
    assert scan_docs(Repo.open(tmp_path)) == [
        Unresolved("docs/GUIDE.md", 1, "notes.md#top", "anchor not found")
    ]


def test_doc_relative_escape_does_not_resolve(tmp_path: Path):
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (tmp_path / "outside.md").write_text("# out\n")
    (root / "AGENTS.md").write_text(
        "## Source of truth, in order\n\n1. `docs/GUIDE.md`.\n"
    )
    (root / "docs/GUIDE.md").write_text("`../../outside.md`\n")
    found = scan_docs(Repo.open(root))
    assert [u.ref for u in found] == ["../../outside.md"]
    assert found[0].reason in (
        "reference escapes the repository",
        "path does not exist",
    )


def test_authoritative_docs_expands_md_globs_in_the_authority_list(tmp_path: Path):
    (tmp_path / "AGENTS.md").write_text(
        "## Source of truth, in order\n\n1. `docs/datasets/*.md`.\n2. `docs/ai/*.md`.\n"
    )
    (tmp_path / "docs/datasets").mkdir(parents=True)
    (tmp_path / "docs/datasets/sift.md").write_text("")
    (tmp_path / "docs/datasets/deep.md").write_text("")
    (tmp_path / "docs/ai").mkdir()
    (tmp_path / "docs/ai/README.md").write_text("")
    names = [
        str(p.relative_to(tmp_path)) for p in authoritative_docs(Repo.open(tmp_path))
    ]
    assert names == ["AGENTS.md", "docs/datasets/deep.md", "docs/datasets/sift.md"]
