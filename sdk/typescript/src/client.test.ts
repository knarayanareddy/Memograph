import assert from "node:assert/strict";
import test from "node:test";

import { MemographClient } from "./client.js";
import { MemographError } from "./validation.js";

const API_KEY = "test-key-0123456789abcdef";

test("client sends the API key and parses JSON", async () => {
  let capturedUrl = "";
  let capturedInit: RequestInit | undefined;
  const fetchImpl = (async (input: RequestInfo | URL, init?: RequestInit) => {
    capturedUrl = String(input);
    capturedInit = init;
    return new Response(
      JSON.stringify({ status: "ok", version: "0.2.0", auth_model: "single-user-shared-key" }),
      {
        status: 200,
        headers: { "content-type": "application/json" },
      },
    );
  }) as typeof fetch;

  const client = new MemographClient({
    baseUrl: "https://example.test/api/",
    apiKey: API_KEY,
    fetchImpl,
  });
  const health = await client.health();
  assert.equal(health.status, "ok");
  assert.equal(health.auth_model, "single-user-shared-key");
  assert.match(capturedUrl, /\/api\/health$/);
  assert.equal(new Headers(capturedInit?.headers).get("X-API-Key"), API_KEY);
});

test("client posts JSON bodies", async () => {
  let capturedInit: RequestInit | undefined;
  const fetchImpl = (async (_input: RequestInfo | URL, init?: RequestInit) => {
    capturedInit = init;
    return new Response(
      JSON.stringify({
        success: true,
        skipped: false,
        skip_reason: null,
        error: null,
        fact_id: "fact_123",
      }),
      { status: 200, headers: { "content-type": "application/json" } },
    );
  }) as typeof fetch;

  const client = new MemographClient({
    baseUrl: "https://example.test",
    apiKey: API_KEY,
    fetchImpl,
  });
  const result = await client.remember({
    topic_id: "project_stack",
    content: "Uses FastAPI",
  });
  assert.equal(result.fact_id, "fact_123");
  assert.equal(capturedInit?.method, "POST");
  assert.equal(new Headers(capturedInit?.headers).get("Content-Type"), "application/json");
  assert.match(String(capturedInit?.body), /Uses FastAPI/);
});

test("client raises a typed error on non-2xx responses", async () => {
  const fetchImpl = (async () =>
    new Response("unauthorized", { status: 401 })) as typeof fetch;
  const client = new MemographClient({
    baseUrl: "https://example.test",
    apiKey: API_KEY,
    fetchImpl,
  });
  await assert.rejects(() => client.status(), MemographError);
});

test("client rejects short API keys", () => {
  assert.throws(
    () =>
      new MemographClient({
        baseUrl: "https://example.test",
        apiKey: "short",
      }),
    MemographError,
  );
});

test("client requires HTTPS for non-loopback hosts", () => {
  assert.throws(
    () =>
      new MemographClient({
        baseUrl: "http://example.test",
        apiKey: API_KEY,
      }),
    /https/,
  );
});

test("client allows loopback HTTP for local development", () => {
  const client = new MemographClient({
    baseUrl: "http://127.0.0.1:8000",
    apiKey: API_KEY,
  });
  assert.ok(client);
});

test("client rejects oversized request bodies", async () => {
  const client = new MemographClient({
    baseUrl: "https://example.test",
    apiKey: API_KEY,
    maxRequestBytes: 10,
    fetchImpl: (async () => new Response("{}")) as typeof fetch,
  });
  await assert.rejects(
    () =>
      client.remember({
        topic_id: "project_stack",
        content: "x".repeat(100),
      }),
    /too large/,
  );
});
