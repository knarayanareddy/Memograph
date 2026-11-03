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
    assert project["requires-python"] == ">=3.11"
    assert project["scripts"]["memograph"] == "memograph.cli.memograph_cli:main"
    assert "pytest" in " ".join(project["optional-dependencies"]["dev"])
    assert data["tool"]["pytest"]["ini_options"]["asyncio_mode"] == "auto"
    assert data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["src/memograph"]
    for url in project["urls"].values():
        assert "yourname" not in url
        assert "memograph.dev" not in url


def test_entry_point_imports():
    module = importlib.import_module("memograph.cli.memograph_cli")
    assert callable(module.main)


def test_no_phantom_extras_in_provider_errors():
    for path in (ROOT / "src" / "memograph").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        assert "pip install memograph[" not in source
