# Examples

- [quickstart.py](quickstart.py) — an offline, self-cleaning Python API walkthrough.

Run it from the repository root after installing the development package:

```bash
pip install -e ".[dev]"
python examples/quickstart.py
# or: make example
```

`quickstart.py` uses the `none` LLM provider and a temporary directory. It does
not require API keys, a network service, or a persistent `.memograph` store.

For CLI equivalents, see the [root README](../README.md).
