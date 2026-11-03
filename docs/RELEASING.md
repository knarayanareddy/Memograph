# Releasing

Releases are tag-triggered in
[`.github/workflows/release.yml`](https://github.com/knarayanareddy/Memograph/blob/main/.github/workflows/release.yml).
No workflow publishes from pull requests or branch pushes.

## Version sync

Before tagging, update all of these to the same version:

- `pyproject.toml`
- `src/memograph/__init__.py`
- `sdk/typescript/package.json`
- `sdk/typescript/package-lock.json`
- [`CHANGELOG.md`](https://github.com/knarayanareddy/Memograph/blob/main/CHANGELOG.md)

Then regenerate `uv.lock` if dependencies changed:

```bash
uv lock
```

Run the full validation suite:

```bash
uv sync --all-extras --frozen
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync mypy
uv run --no-sync pytest -m "not integration"
uv run --no-sync pytest -m integration
uv run --no-sync mkdocs build --strict
uv build
npm ci --prefix sdk/typescript
npm test --prefix sdk/typescript
```

## Tag and publish

```bash
git tag v0.2.0
git push origin v0.2.0
```

The workflow:

1. Builds the Python sdist and wheel with `uv build`.
2. Publishes to PyPI with OIDC trusted publishing; no PyPI password is stored.
3. Creates a GitHub release with generated notes and attached Python artifacts.
4. Runs `npm ci` and `npm test` for the TypeScript package.
5. Publishes `memograph-sdk` with `npm publish --provenance --access public`.

## Required configuration

- Configure PyPI trusted publishing for `knarayanareddy/Memograph` and the
  `pypi` GitHub environment.
- Add an npm automation token as the `NPM_TOKEN` repository secret.
- Confirm the npm package name is available before the first release.
- Do not commit tokens, `.env` files, databases, memory stores, or `node_modules`.

See [SECURITY.md](https://github.com/knarayanareddy/Memograph/blob/main/SECURITY.md)
for secret-handling guidance.
