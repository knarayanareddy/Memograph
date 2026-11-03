# memograph-sdk

TypeScript SDK for [Memograph](https://github.com/knarayanareddy/Memograph).
It provides:

- `MemographClient` — typed REST/WebSocket client for the authenticated Python service.
- `LocalMemograph` — a standalone SQLite-backed local store with the same core operations.
- Shared validation, stable IDs, and TypeScript types.

## Requirements

Node.js **22.5+** is required. The local store uses the experimental
`node:sqlite` module, so tests and local-store programs must run with
`--experimental-sqlite`.

## Install

```bash
npm install memograph-sdk
```

## REST client

```ts
import { MemographClient } from "memograph-sdk";

const client = new MemographClient({
  baseUrl: "https://memograph.example.com",
  apiKey: process.env.MEMOGRAPH_API_KEY!,
});

await client.remember({
  topicId: "project_stack",
  content: "Uses FastAPI and SQLite",
  source: "readme",
});
const topics = await client.recall("What framework?");
const context = await client.context({ query: "What framework?" });
console.log(context.text);

for await (const event of client.events()) {
  console.log(event.type, event.payload);
}
```

## Local store

```ts
import { LocalMemograph } from "memograph-sdk";

const mg = new LocalMemograph({ basePath: ".memograph" });
await mg.open();
await mg.remember("project_stack", "Uses FastAPI", "app");
console.log(await mg.status());
await mg.close();
```

Run local-store programs with:

```bash
node --experimental-sqlite your-script.js
```

## Development

```bash
npm ci
npm test
npm run typecheck
```

`npm test` compiles to `dist/` and runs `node:test` suites against both the
client and the local SQLite store.
