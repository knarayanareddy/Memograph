"""Allow ``python -m memograph``."""

from .cli.memograph_cli import main

raise SystemExit(main())
