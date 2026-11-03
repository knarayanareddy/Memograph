"""Command-line runner for the optional REST/WebSocket service."""

from __future__ import annotations

import argparse
import os
from collections.abc import Sequence

from .settings import APISettings


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memograph-api")
    parser.add_argument("--host", help="Bind host (default: MEMOGRAPH_API_HOST or 0.0.0.0)")
    parser.add_argument("--port", type=int, help="Bind port (default: 8000)")
    parser.add_argument("--base-path", help="Memory store directory")
    parser.add_argument("--agent-id", help="Agent identifier")
    parser.add_argument("--provider", help="LLM provider name; 'none' is offline")
    parser.add_argument(
        "--cors-origin",
        action="append",
        default=[],
        help="Allowed browser origin; repeat for multiple origins",
    )
    parser.add_argument("--rate-limit", type=int, help="Requests per minute per API key")
    parser.add_argument("--log-level", help="Uvicorn log level")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run ``uvicorn`` for :func:`memograph.api.create_app`."""
    args = _parser().parse_args(argv)
    mapping = {
        "MEMOGRAPH_API_HOST": args.host,
        "MEMOGRAPH_API_PORT": str(args.port) if args.port is not None else None,
        "MEMOGRAPH_BASE_PATH": args.base_path,
        "MEMOGRAPH_AGENT_ID": args.agent_id,
        "MEMOGRAPH_LLM_PROVIDER": args.provider,
        "MEMOGRAPH_API_RATE_LIMIT_PER_MINUTE": (
            str(args.rate_limit) if args.rate_limit is not None else None
        ),
        "MEMOGRAPH_API_LOG_LEVEL": args.log_level,
    }
    for key, value in mapping.items():
        if value is not None:
            os.environ[key] = value
    if args.cors_origin:
        os.environ["MEMOGRAPH_API_CORS_ORIGINS"] = ",".join(args.cors_origin)

    try:
        import uvicorn

        from .app import create_app
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise SystemExit("Install the 'memograph[api]' extra to run the REST API.") from exc

    settings = APISettings()
    if not settings.api_key.get_secret_value():
        raise SystemExit("MEMOGRAPH_API_KEY is required before starting the REST API.")
    app = create_app(settings=settings)
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
    )
    return 0
