from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CANONICAL_DOCS = [
    "ARCHITECTURE.md",
    "ROADMAP.md",
    "DECISIONS.md",
    "SPEC_STATUS.md",
    "REFERENCES.md",
    "REST_API.md",
    "INTEGRATIONS.md",
    "TYPESCRIPT.md",
    "RELEASING.md",
    "api.md",
    "examples.md",
    "index.md",
    "README.md",
]


def test_canonical_docs_replace_historical_artifacts():
    assert not (ROOT / "memo.md").exists()
    assert not (ROOT / "🧠 MemoGraph — Complete Build Architecture.pdf").exists()
    archived = ROOT / "docs" / "archive" / "memo.md"
    assert archived.exists()
    assert "Archived historical design draft" in archived.read_text(encoding="utf-8")[:200]

    for name in CANONICAL_DOCS:
        assert (ROOT / "docs" / name).exists()

    for path in [
        "uv.lock",
        "mkdocs.yml",
        "sdk/typescript/package.json",
        "sdk/typescript/package-lock.json",
        ".github/workflows/ci.yml",
        ".github/workflows/docs.yml",
        ".github/workflows/release.yml",
    ]:
        assert (ROOT / path).exists()


def test_no_unverifiable_provenance_claims_in_canonical_docs():
    paths = [ROOT / "README.md", *(ROOT / "docs" / name for name in CANONICAL_DOCS)]
    for path in paths:
        text = path.read_text(encoding="utf-8").lower()
        assert "leaked source" not in text
        assert "implement this exactly" not in text


def test_readme_and_hygiene():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Status" in readme
    assert 'pip install -e ".[dev]"' in readme
    assert "uv sync --all-extras --frozen" in readme
    assert "docs/ROADMAP.md" in readme
    assert "REST API" in readme
    assert "TypeScript SDK" in readme
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in [
        ".env",
        ".memograph/",
        "*.db",
        "*.pkl",
        "__pycache__/",
        "node_modules/",
        "site/",
        "*.tsbuildinfo",
    ]:
        assert pattern in ignore
    assert (ROOT / "LICENSE").exists()
    assert (ROOT / "SECURITY.md").exists()
    assert (ROOT / ".github" / "workflows" / "ci.yml").exists()


def test_roadmap_and_status_no_longer_defer_phases():
    roadmap = (ROOT / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
    status = (ROOT / "docs" / "SPEC_STATUS.md").read_text(encoding="utf-8")
    assert "remain intentionally deferred" not in roadmap.lower()
    assert "| 9 |" in roadmap
    assert "Implemented" in roadmap
    assert "no longer deferred" in status.lower()
