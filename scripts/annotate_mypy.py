#!/usr/bin/env python3
"""Turn mypy output into GitHub Actions error annotations."""

from __future__ import annotations

import sys
from pathlib import Path

MAX_ANNOTATIONS = 10
ERROR_MARKER = ": error:"


def escape(value: str) -> str:
    """Escape workflow-command data as required by GitHub Actions."""
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main() -> int:
    if len(sys.argv) > 1:
        raw = Path(sys.argv[1]).read_text(encoding="utf-8")
    else:
        raw = sys.stdin.read()

    lines = [line.rstrip("\r\n") for line in raw.splitlines() if line.strip()]
    errors = [line for line in lines if ERROR_MARKER in line]
    for line in errors[:MAX_ANNOTATIONS]:
        print(f"::error title=mypy::{escape(line)}")

    remaining = len(errors) - MAX_ANNOTATIONS
    if remaining > 0:
        message = (
            f"{remaining} additional mypy errors are in the job summary and uploaded artifact."
        )
        print(f"::notice title=mypy::{escape(message)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
