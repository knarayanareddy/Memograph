# References

This project is an independent implementation. It does not use or reproduce any
leaked third-party source. The following primary documentation describes the
public APIs and libraries used here.

- Python `fcntl`: <https://docs.python.org/3/library/fcntl.html>
- Python `pathlib.Path.is_relative_to`: <https://docs.python.org/3/library/pathlib.html#pathlib.PurePath.is_relative_to>
- Python `os.replace`: <https://docs.python.org/3/library/os.html#os.replace>
- SQLite Write-Ahead Logging: <https://www.sqlite.org/wal.html>
- SQLite foreign keys: <https://www.sqlite.org/foreignkeys.html>
- Pydantic: <https://docs.pydantic.dev/latest/>
- pydantic-settings: <https://docs.pydantic.dev/latest/concepts/pydantic_settings/>
- httpx: <https://www.python-httpx.org/>
- Ollama API: <https://github.com/ollama/ollama/blob/main/docs/api.md>
- Anthropic Messages API: <https://docs.anthropic.com/en/api/messages>
- OpenAI Chat Completions API: <https://platform.openai.com/docs/api-reference/chat>
- Gemini `generateContent`: <https://ai.google.dev/api/generate-content>
- pytest-asyncio: <https://pytest-asyncio.readthedocs.io/>
- Ruff: <https://docs.astral.sh/ruff/>
- mypy: <https://mypy.readthedocs.io/>
- Hatchling: <https://hatch.pypa.io/latest/config/build/>

Model context sizes change frequently. Memograph therefore uses a conservative
default and an explicit caller override rather than embedding a model catalog as
fact.
