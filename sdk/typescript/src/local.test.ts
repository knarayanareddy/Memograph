import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, rm, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { LocalMemograph } from "./local.js";
import {
  MemographError,
  assertApiKey,
  assertLiteralPattern,
  assertRegexPattern,
  assertTopicId,
  safePath,
  stableId,
  validateBaseUrl,
} from "./validation.js";

test("local store persists facts, views, context, and dream state", async () => {
  const dir = await mkdtemp(join(tmpdir(), "memograph-ts-"));
  const mg = new LocalMemograph({ basePath: dir });
  await mg.open();
  try {
    const result = await mg.remember("project_stack", "Uses FastAPI and SQLite", "test");
    assert.equal(result.success, true);
    assert.ok(result.fact_id?.startsWith("fact_"));

    const status = await mg.status();
    assert.equal(status.provider, "none");
    assert.equal(status.topics.total, 1);
    assert.equal(status.topics.total_facts, 1);

    const topics = await mg.recall("FastAPI");
    assert.equal(topics.length, 1);
    assert.equal(topics[0]?.topic_id, "project_stack");

    const context = await mg.buildContext("FastAPI");
    assert.match(context.text, /FastAPI/);
    assert.ok(context.topics_loaded.includes("project_stack"));

    const index = await mg.index();
    assert.match(index, /project_stack/);
    assert.ok(existsSync(join(dir, "MEMORY.md")));
    assert.ok(existsSync(join(dir, "topics", "project_stack.json")));
    assert.ok(existsSync(join(dir, "topics", "project_stack.md")));

    const dream = await mg.dreamNow(true);
    assert.equal(dream.status, "completed");
    assert.notEqual((await mg.status()).last_consolidated, null);

    const updated = await mg.update("project_stack", result.fact_id!, {
      newContent: "Uses FastAPI and PostgreSQL",
    });
    assert.equal(updated, true);
    assert.match((await mg.recall("PostgreSQL"))[0]?.facts[0]?.content ?? "", /PostgreSQL/);

    assert.equal(await mg.forget("project_stack"), true);
    assert.equal((await mg.status()).topics.total, 0);
  } finally {
    await mg.close();
    await rm(dir, { recursive: true, force: true });
  }
});

test("local store archives transcripts and validates regex", async () => {
  const dir = await mkdtemp(join(tmpdir(), "memograph-ts-"));
  const mg = new LocalMemograph({ basePath: dir });
  await mg.open();
  try {
    await mg.startSession("session_1");
    await mg.archiveTurn("user", "Uses FastAPI");
    await mg.archiveTurn("assistant", "SQLite is canonical");
    assert.equal((await mg.recentSignals()).length, 2);
    assert.equal((await mg.grepTranscripts("FastAPI")).length, 1);
    await assert.rejects(() => mg.grepTranscripts("[", 20, true), MemographError);
    await assert.rejects(() => mg.grepTranscripts("(a+)+$", 20, true), /catastrophic/);
    await assert.rejects(() => mg.grepTranscripts("a".repeat(201), 20, true), /too long/);
    await assert.rejects(() => mg.grepTranscripts("FastAPI", 101, false), /max_results/);
    await mg.endSession();
  } finally {
    await mg.close();
    await rm(dir, { recursive: true, force: true });
  }
});

test("literal grep escapes metacharacters", async () => {
  const dir = await mkdtemp(join(tmpdir(), "memograph-ts-"));
  const mg = new LocalMemograph({ basePath: dir });
  await mg.open();
  try {
    await mg.startSession("session_1");
    await mg.archiveTurn("user", "a.b");
    assert.equal((await mg.grepTranscripts("a.b")).length, 1);
    await mg.endSession();
  } finally {
    await mg.close();
    await rm(dir, { recursive: true, force: true });
  }
});

test("safePath rejects symlink escapes", async () => {
  const dir = await mkdtemp(join(tmpdir(), "memograph-ts-"));
  const outside = await mkdtemp(join(tmpdir(), "memograph-outside-"));
  try {
    await mkdir(join(dir, "topics"));
    await symlink(outside, join(dir, "topics", "escape"));
    assert.throws(
      () => safePath(join(dir, "topics"), "escape", "file.json"),
      MemographError,
    );
  } finally {
    await rm(dir, { recursive: true, force: true });
    await rm(outside, { recursive: true, force: true });
  }
});

test("validation helpers are deterministic and strict", () => {
  assert.throws(() => assertTopicId("../escape"), MemographError);
  assert.equal(assertTopicId("project_stack"), "project_stack");
  assert.equal(stableId("same-input"), stableId("same-input"));
  assert.notEqual(stableId("a"), stableId("b"));
  assert.throws(() => validateBaseUrl("http://example.test"), /https/);
  assert.throws(() => validateBaseUrl("https://user:pass@example.test"), /credentials/);
  assert.equal(validateBaseUrl("https://example.test"), "https://example.test/");
  assert.throws(() => assertApiKey("short"), MemographError);
  assert.throws(() => assertRegexPattern("(a+)+$"), MemographError);
  assert.throws(() => assertRegexPattern("a".repeat(201)), MemographError);
  assert.equal(assertLiteralPattern("a.b"), "a\\.b");
});
