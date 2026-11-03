"""Memograph command-line interface."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from typing import Any

from .. import MemoGraph


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="memograph",
        description="Inspect and maintain a Memograph memory store.",
    )
    parser.add_argument("--base-path", default=".memograph")
    parser.add_argument(
        "--provider", default=None, help="ollama|openai|groq|custom|anthropic|gemini|none"
    )
    parser.add_argument("--model", default=None)
    parser.add_argument("--api-key", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--json", action="store_true", help="Emit compact JSON")

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("status", help="Show memory-store status")

    remember = subparsers.add_parser("remember", help="Store one fact")
    remember.add_argument("topic_id")
    remember.add_argument("content")
    remember.add_argument("--source", default="cli")
    remember.add_argument("--confidence", default="observed")

    recall = subparsers.add_parser("recall", help="Recall relevant topics")
    recall.add_argument("query")
    recall.add_argument("--top-k", type=int, default=3)
    recall.add_argument("--verify", action="store_true")

    forget = subparsers.add_parser("forget", help="Forget a topic or one fact")
    forget.add_argument("topic_id")
    forget.add_argument("--fact-id", default=None)

    update = subparsers.add_parser("update", help="Update one fact")
    update.add_argument("topic_id")
    update.add_argument("fact_id")
    update.add_argument("--content", default=None)
    update.add_argument("--confidence", default=None)
    update.add_argument("--verification-source", default=None)

    context = subparsers.add_parser("context", help="Build bandwidth-aware context")
    context.add_argument("query")
    context.add_argument("--max-topics", type=int, default=3)
    context.add_argument("--token-budget", type=int, default=None)

    dream = subparsers.add_parser("dream", help="Run one consolidation cycle")
    dream.add_argument("--force", action="store_true")

    subparsers.add_parser("prune", help="Remove dangling index pointers")
    subparsers.add_parser("index", help="Print the always-loaded index")

    transcript = subparsers.add_parser("grep", help="Grep archived transcripts")
    transcript.add_argument("pattern")
    transcript.add_argument("--max-results", type=int, default=20)
    transcript.add_argument("--regex", action="store_true")

    return parser


def _topic_payload(topic: Any) -> dict[str, Any]:
    return {
        "topic_id": topic.topic_id,
        "topic_name": topic.topic_name,
        "tags": topic.tags,
        "facts": [fact.model_dump(mode="json") for fact in topic.facts],
    }


async def _run(args: argparse.Namespace) -> Any:
    async with MemoGraph(
        base_path=args.base_path,
        provider=args.provider,
        model=args.model,
        api_key=args.api_key,
        base_url=args.base_url,
    ) as mg:
        if args.command == "status":
            return await mg.status()
        if args.command == "remember":
            write_result = await mg.remember(
                args.topic_id,
                args.content,
                args.source,
                confidence=args.confidence,
            )
            return {
                "success": write_result.success,
                "skipped": write_result.skipped,
                "skip_reason": write_result.skip_reason,
                "error": write_result.error,
                "fact_id": write_result.fact.fact_id if write_result.fact else None,
            }
        if args.command == "recall":
            topics = await mg.recall(args.query, args.top_k, args.verify)
            return [_topic_payload(topic) for topic in topics]
        if args.command == "forget":
            return {"forgotten": await mg.forget(args.topic_id, args.fact_id)}
        if args.command == "update":
            return {
                "updated": await mg.update(
                    args.topic_id,
                    args.fact_id,
                    args.content,
                    args.confidence,
                    args.verification_source,
                )
            }
        if args.command == "context":
            built = await mg.build_context(args.query, args.max_topics, args.token_budget)
            return {"text": built.text, **built.to_dict()}
        if args.command == "dream":
            result = await mg.dream_now(force=args.force)
            return result.to_dict()
        if args.command == "prune":
            return {"pointers_removed": await mg.prune()}
        if args.command == "index":
            return {"index": await mg.get_context_injection()}
        if args.command == "grep":
            return await mg.grep_transcripts(args.pattern, args.max_results, args.regex)
        raise ValueError(f"Unknown command: {args.command}")  # pragma: no cover


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        payload = asyncio.run(_run(args))
    except Exception as exc:  # pragma: no cover - exercised manually
        print(f"memograph: {exc}", file=sys.stderr)
        return 1
    indent = None if args.json else 2
    print(json.dumps(payload, indent=indent, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
