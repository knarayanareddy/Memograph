# TypeScript SDK

The [`memograph-sdk` package](https://github.com/knarayanareddy/Memograph/tree/main/sdk/typescript)
lives in `sdk/typescript`. It requires Node.js 22.5+ because `LocalMemograph`
uses experimental `node:sqlite`.

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
implementation for testing, and raises `MemographError` on non-2xx responses.
The WebSocket client sends the API key in handshake headers, not the URL.

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
does not call an LLM provider.

## Development

```bash
cd sdk/typescript
npm ci
npm test
npm run typecheck
```

`npm test` compiles TypeScript and runs `node:test` suites. CI runs `npm ci`
and `npm test` on Node.js 22. See [Releasing](RELEASING.md) for npm publishing.
