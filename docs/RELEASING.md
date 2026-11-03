# Releasing

Releases are tag-triggered in
[`.github/workflows/release.yml`](https://github.com/knarayanareddy/Memograph/blob/main/.github/workflows/release.yml).
No workflow publishes from pull requests or branch pushes. All actions are
SHA-pinned and checkout credentials are not persisted.

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

Run the full validation suite, including security scans:

```bash
make release-check
```

The equivalent individual commands are:

```bash
uv sync --frozen --extra dev --extra api --extra docs
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync mypy
uv run --no-sync bandit -c pyproject.toml -r src/memograph -ll
uv run --no-sync ruff check src/memograph --select S --ignore S101
uv export --all-extras --frozen --no-emit-project --format requirements-txt > /tmp/requirements.txt
uvx --from 'pip-audit==2.10.1' pip-audit -r /tmp/requirements.txt --vulnerability-service pypi --progress-spinner off --format json --ignore-vuln GHSA-f4j7-r4q5-qw2c --ignore-vuln GHSA-36p7-vc44-83pf --ignore-vuln GHSA-xph7-9rjv-w5fr --ignore-vuln GHSA-2wm9-hf6c-p5cr
uv run --no-sync pytest -m "not integration"
uv sync --all-extras --frozen
uv run --no-sync pytest -m integration
npm audit --prefix sdk/typescript --omit=dev
uv run --no-sync mkdocs build --strict
uv build
npm ci --prefix sdk/typescript
npm test --prefix sdk/typescript -- --run
npm run typecheck --prefix sdk/typescript
npm run build --prefix sdk/typescript
```

The `pip-audit` exceptions are documented in
[SECURITY.md](https://github.com/knarayanareddy/Memograph/blob/main/SECURITY.md);
remove them as soon as patched ChromaDB releases exist.

## Tag and publish

```bash
git tag v0.2.0
git push origin v0.2.0
```

The workflow:

1. Builds the Python sdist and wheel with `uv build`.
2. Publishes to PyPI with OIDC trusted publishing; no PyPI password is stored.
3. Creates a GitHub release with generated notes and attached Python artifacts.
4. Runs `npm ci`, tests, typecheck, and build for the TypeScript package on
   Node.js 26.
5. Publishes `memograph-sdk` with `npm publish --provenance --access public`.

## Required configuration

- Configure PyPI trusted publishing for `knarayanareddy/Memograph` and the
  `pypi` GitHub environment.
- Add an npm automation token as the `NPM_TOKEN` repository secret.
- Confirm the npm package name is available before the first release.
- Do not commit tokens, `.env` files, databases, memory stores, or `node_modules`.

See [SECURITY.md](https://github.com/knarayanareddy/Memograph/blob/main/SECURITY.md)
for secret-handling guidance.
