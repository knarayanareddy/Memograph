# TypeScript SDK

The [`memograph-sdk` package](https://github.com/knarayanareddy/Memograph/tree/main/sdk/typescript)
lives in `sdk/typescript`. It supports Node.js 22, 24, and 26 because
`LocalMemograph` uses `node:sqlite`; CI and releases use Node 26 and TypeScript
7. Loopback HTTP is allowed for local development, but remote clients must use
HTTPS/WSS.

## Install

```bash
npm install memograph-sdk
```

## REST and WebSocket client

```ts
import { MemographClient } from "memograph-sdk";

const client = new MemographClient({
  baseUrl: "https://memograph.example.com",
  apiKey: process.env.MEMOGRAPH_API_KEY!,
});

const health = await client.health();
await client.remember({
  topic_id: "project_stack",
  content: "Uses FastAPI",
  source: "sdk",
});
const context = await client.context({ query: "FastAPI" });
console.log(context.text);

const events = client.events();
for await (const event of events) {
  console.log(event.type);
  if (event.type === "memory.remembered") events.close();
}
```

`MemographClient` covers every REST endpoint, accepts an injected `fetch`
implementation for testing, raises `MemographError` on non-2xx responses, and
requires a sufficiently long API key. The WebSocket client sends the key in
handshake headers, not the URL. Request bodies are bounded to 1 MiB by default;
`health()` reports the server's `single-user-shared-key` auth model.

## Local SQLite store

```ts
import { LocalMemograph } from "memograph-sdk";

const mg = new LocalMemograph({ basePath: ".memograph" });
await mg.open();
const result = await mg.remember("project_stack", "Uses FastAPI", "app");
console.log(result.fact_id, await mg.status());
await mg.close();
```

Run local-store programs with:

```bash
node --experimental-sqlite your-script.js
```

`LocalMemograph` implements topics, facts, generated JSON/Markdown views, index
limits, keyword recall, context budgeting, transcript archiving, grep, offline
consolidation, SHA-256 stable IDs, and startup reconciliation. It is offline and
does not call an LLM provider. Topic IDs, content, tags, and grep patterns are
bounded to the same limits as the Python implementation; `safePath` uses
`realpath` to reject symlink escapes. Transcript grep escapes literal patterns,
rejects suspicious regex constructs, and clips snippets to 200 characters.

## Development

```bash
cd sdk/typescript
npm ci
npm test -- --run
npm run typecheck
```

`npm test` compiles TypeScript and runs `node:test` suites. CI runs `npm ci`,
`npm test`, `npm run typecheck`, and `npm run build` on Node.js 22, 24, and 26.
See [Releasing](RELEASING.md) for npm publishing.
