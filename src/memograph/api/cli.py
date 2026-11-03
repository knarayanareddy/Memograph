"""Console entrypoint for the Memograph REST service."""

from __future__ import annotations

import argparse

try:
    import uvicorn
except ImportError as exc:  # pragma: no cover - depends on optional extra
    raise RuntimeError("Install the 'memograph[api]' extra to use the REST API.") from exc

from .. import __version__
from .settings import APISettings


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="memograph-api",
        description=(
            "Run the authenticated, single-user Memograph REST/WebSocket API. "
            "MEMOGRAPH_API_KEY is required; bind to a reverse proxy for remote access."
        ),
    )
    defaults = APISettings()
    parser.add_argument("--host", default=defaults.host, help="Bind host (default: 127.0.0.1).")
    parser.add_argument("--port", type=int, default=defaults.port, help="Bind port.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()

    # Import lazily so --version works without the API extra's FastAPI import.
    from .app import create_app

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, log_level=defaults.log_level)
