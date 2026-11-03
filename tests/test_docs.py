from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_canonical_docs_replace_historical_artifacts():
    assert not (ROOT / "memo.md").exists()
    assert not (ROOT / "🧠 MemoGraph — Complete Build Architecture.pdf").exists()
    archived = ROOT / "docs" / "archive" / "memo.md"
    assert archived.exists()
    assert "Archived historical design draft" in archived.read_text(encoding="utf-8")[:200]

    for name in [
        "ARCHITECTURE.md",
        "ROADMAP.md",
        "DECISIONS.md",
        "SPEC_STATUS.md",
        "REFERENCES.md",
    ]:
        assert (ROOT / "docs" / name).exists()


def test_no_leaked_source_claims_in_canonical_docs():
    for name in ["README.md", "docs/ARCHITECTURE.md", "docs/DECISIONS.md", "docs/REFERENCES.md"]:
        text = (ROOT / name).read_text(encoding="utf-8").lower()
        assert "leaked source" not in text
        assert "implement this exactly" not in text


def test_readme_and_hygiene():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Status" in readme
    assert 'pip install -e ".[dev]"' in readme
    assert "docs/ROADMAP.md" in readme
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in [".env", ".memograph/", "*.db", "*.pkl", "__pycache__/"]:
        assert pattern in ignore
    assert (ROOT / "LICENSE").exists()
    assert (ROOT / "SECURITY.md").exists()
    assert (ROOT / ".github" / "workflows" / "ci.yml").exists()
