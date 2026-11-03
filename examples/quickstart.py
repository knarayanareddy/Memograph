"""Minimal offline Memograph walkthrough.

Run from a checkout after ``pip install -e ".[dev]"``::

    python examples/quickstart.py

The script creates a temporary store, so it does not modify the repository or
require a network service.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from memograph import LLMProvider, MemoGraph


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="memograph-example-") as tmp:
        base_path = Path(tmp) / "store"
        async with MemoGraph(base_path=base_path, provider=LLMProvider.NONE) as mg:
            result = await mg.remember(
                "project_stack",
                "Uses FastAPI and SQLite",
                source="examples/quickstart.py",
            )
            fact_id = result.fact.fact_id if result.fact else None
            print(f"remembered: {result.success} {fact_id}")

            topics = await mg.recall("What framework do we use?", top_k=3)
            print(f"recalled topics: {[topic.topic_id for topic in topics]}")

            context = await mg.build_context("What framework do we use?")
            print("context:")
            print(context.text)

            status = await mg.status()
            print(f"topic count: {status['topics']['total']}")

            dream = await mg.dream_now(force=True)
            print(f"dream: {dream.status} {dream.operations_applied} operations")

    print("temporary store cleaned up")


if __name__ == "__main__":
    asyncio.run(main())
