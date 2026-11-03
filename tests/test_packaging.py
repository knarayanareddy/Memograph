from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_is_complete():
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]
    dependencies = set(project["dependencies"])
    assert {"aiosqlite", "httpx", "pydantic", "pydantic-settings"}.issubset(
        {item.split(">=")[0].split("[")[0] for item in dependencies}
    )
    assert project["requires-python"] == ">=3.11,<3.14"
    assert project["version"] == "0.2.0"
    assert project["scripts"]["memograph"] == "memograph.cli.memograph_cli:main"
    assert project["scripts"]["memograph-api"] == "memograph.api.cli:main"
    assert project["urls"]["Documentation"] == "https://knarayanareddy.github.io/Memograph/"

    extras = project["optional-dependencies"]
    for name in ["dev", "api", "integrations", "docs", "all"]:
        assert name in extras
    assert "pytest" in " ".join(extras["dev"])
    assert "fastapi" in " ".join(extras["api"])
    assert "langchain-core" in " ".join(extras["integrations"])
    assert "mkdocs" in " ".join(extras["docs"])
    assert data["tool"]["uv"]["constraint-dependencies"] == ["pyarrow<26"]
    assert data["tool"]["pytest"]["ini_options"]["asyncio_mode"] == "auto"
    assert data["tool"]["pytest"]["ini_options"]["markers"] == [
        "integration: tests requiring optional framework SDKs"
    ]
    assert data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["src/memograph"]
    sdist_include = data["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
    for path in [
        "src/memograph",
        "tests",
        "docs",
        "examples",
        "sdk/typescript",
        "uv.lock",
        "mkdocs.yml",
    ]:
        assert path in sdist_include
    for url in project["urls"].values():
        assert "yourname" not in url
        assert "memograph.dev" not in url


def test_entry_point_imports():
    module = importlib.import_module("memograph.cli.memograph_cli")
    assert callable(module.main)
    api_module = importlib.import_module("memograph.api.cli")
    assert callable(api_module.main)


def test_no_phantom_extras_in_provider_errors():
    for path in (ROOT / "src" / "memograph").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "pip install memograph[" not in source


def test_lockfiles_and_release_automation():
    assert (ROOT / "uv.lock").exists()
    assert (ROOT / "sdk/typescript/package-lock.json").exists()
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    docs = (ROOT / ".github" / "workflows" / "docs.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert "astral-sh/setup-uv@v10.3.3" in ci
    assert "uv sync --all-extras --frozen" in ci
    assert "mypy --python-version 3.11 --no-incremental" in ci
    assert "typecheck-compat" in ci
    assert "continue-on-error: true" in ci
    assert "scripts/annotate_mypy.py" in ci
    assert "$GITHUB_STEP_SUMMARY" in ci
    assert "npm ci --prefix sdk/typescript" in ci
    assert "mkdocs build --strict" in ci
    assert "actions/deploy-pages@v4" in docs
    assert "pypa/gh-action-pypi-publish@release/v1" in release
    assert "npm publish --prefix sdk/typescript --provenance" in release
