"""Static checks for packaging, workflows, and security automation."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def get_pyproject() -> dict:
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_python_package_metadata() -> None:
    project = get_pyproject()["project"]
    assert project["name"] == "memograph"
    assert project["version"] == "0.2.0"
    assert project["requires-python"] == ">=3.11,<3.14"
    assert "regex>=2026.1.15,<2026.2" in project["dependencies"]
    assert "bandit>=1.9,<2" in project["optional-dependencies"]["dev"]
    assert "bandit>=1.9,<2" in project["optional-dependencies"]["all"]
    assert get_pyproject()["tool"]["uv"].get("constraint-dependencies", []) == []


def test_sdist_includes_security_config() -> None:
    includes = get_pyproject()["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
    for path in (
        "src/memograph",
        "tests",
        "docs",
        "examples",
        "sdk/typescript",
        ".github/workflows",
        ".github/dependabot.yml",
        "SECURITY.md",
        "uv.lock",
        "pyproject.toml",
    ):
        assert path in includes


def test_ci_uses_narrow_locked_installs_and_security_scans() -> None:
    text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    assert "uv sync --frozen --extra dev --extra api --extra docs" in text
    assert "uv sync --all-extras --frozen" in text
    assert "pytest -m integration" in text
    assert "bandit -c pyproject.toml -r src/memograph -ll" in text
    assert "ruff check src/memograph --select S --ignore S101" in text
    assert "npm audit --prefix sdk/typescript --omit=dev" in text
    assert "pip-audit" in text
    assert "GHSA-f4j7-r4q5-qw2c" in text
    assert 'node-version: ["22", "24", "26"]' in text
    assert 'python-version: ["3.11", "3.12", "3.13"]' in text
    assert "persist-credentials: false" in text


def test_workflows_are_sha_pinned() -> None:
    ci = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
    docs = (WORKFLOWS / "docs.yml").read_text(encoding="utf-8")
    release = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")
    for text in (ci, docs, release):
        assert "@v" not in text
        assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in text
    for sha in (
        "6d4fd22b20465ccc0f7354476588e8df7c9ca0e0",
        "949feb2413d6458794dcd2491c4babbbce0c15c1",
        "68559e99cc807c1eb7e9238fd43a15bba460eec2",
    ):
        assert sha in ci
    assert "45bfe0192ca1faeb007ade9deae92b16b8254a0d" in docs
    assert "fc324d3547104276b827a68afc52ff2a11cc49c9" in docs
    assert "368f82528645a54fb793d4d04e342629a3f51346" in docs
    assert "7245906fb61fa33a13554f9d5fb856fe61758086" in release
    assert "efb35369e0ad2afab669f228072c1b0d510eae64" in release
    assert "pypa/gh-action-pypi-publish@release/v1" not in release


def test_dependabot_and_precommit_are_configured() -> None:
    dependabot = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    for ecosystem in ("pip", "npm", "github-actions"):
        assert f'package-ecosystem: "{ecosystem}"' in dependabot

    precommit = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    for sha in (
        "25bcf95026b96e2dd3c0aec3090c3d6ef6ca2e6c",
        "92ae8b82fb422a639f0ed8d99e96cea769594e08",
        "3e8a8703264a2f4a69428a0aa4dcb512790b2c8c",
    ):
        assert sha in precommit
    assert "ruff-security" in precommit
    assert "bandit-source" in precommit
    assert "detect-private-key" in precommit


def test_makefile_has_security_target() -> None:
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "security:" in text
    assert "release-check: lint typecheck security" in text
    assert "--host 127.0.0.1" in text
