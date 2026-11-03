import * as fs from "node:fs";
import * as path from "node:path";
import { DatabaseSync } from "node:sqlite";

import type {
  ConfidenceLevel,
  ContextResult,
  DreamResult,
  LocalMemographOptions,
  MemoryFact,
  RememberOptions,
  Status,
  TopicFile,
  UpdateOptions,
  WriteResult,
} from "./types.js";
import {
  MAX_FACT_CHARS,
  MAX_GREP_PATTERN_CHARS,
  MAX_INDEX_BYTES,
  MAX_INDEX_LINES,
  MAX_POINTER_CHARS,
  MAX_SNIPPET_CHARS,
  MemographError,
  assertAgentId,
  assertConfidence,
  assertContent,
  assertId,
  assertMaxResults,
  assertQuery,
  assertRegexPattern,
  assertSource,
  assertString,
  assertTags,
  assertTopK,
  assertTopicId,
  assertVerificationHint,
  clipText,
  estimateTokens,
  nowIso,
  safePath,
  stableId,
} from "./validation.js";

type SqlRow = Record<string, unknown>;
type SqlParam = string | number | bigint | null;

interface Pointer {
  topic_id: string;
  pointer_line: string;
  fact_count: number;
  avg_confidence: number;
  last_modified: string;
}

const DEFAULT_CONTEXT_TOKENS = 8_192;
const OUTPUT_RESERVATION = 2_048;
const CONFIDENCE_SCORE: Record<ConfidenceLevel, number> = {
  verified: 1.0,
  observed: 0.6,
  inferred: 0.4,
  stale: 0.1,
};

const SCHEMA = `
CREATE TABLE IF NOT EXISTS topics (
    agent_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    topic_name TEXT NOT NULL,
    tags_json TEXT NOT NULL,
    file_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_modified TEXT NOT NULL,
    PRIMARY KEY (agent_id, topic_id)
);
CREATE TABLE IF NOT EXISTS facts (
    agent_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    fact_id TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT NOT NULL,
    confidence TEXT NOT NULL,
    verification_hint TEXT,
    created_at TEXT NOT NULL,
    last_verified TEXT,
    contradicts_json TEXT NOT NULL,
    meta_json TEXT NOT NULL,
    PRIMARY KEY (agent_id, topic_id, fact_id),
    FOREIGN KEY (agent_id, topic_id) REFERENCES topics(agent_id, topic_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS index_pointers (
    agent_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,
    pointer_line TEXT NOT NULL,
    fact_count INTEGER NOT NULL,
    avg_confidence REAL NOT NULL,
    last_modified TEXT NOT NULL,
    PRIMARY KEY (agent_id, topic_id)
);
CREATE TABLE IF NOT EXISTS sessions (
    agent_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    turn_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (agent_id, session_id)
);
CREATE TABLE IF NOT EXISTS transcripts (
    agent_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    tool_calls_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (agent_id, session_id, turn_index)
);
CREATE TABLE IF NOT EXISTS dream_state (
    agent_id TEXT PRIMARY KEY,
    last_run_id TEXT NOT NULL,
    last_consolidated_at TEXT NOT NULL,
    sessions_since_last INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS dream_runs (
    agent_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    trigger TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    operations_applied INTEGER NOT NULL,
    error TEXT,
    PRIMARY KEY (agent_id, run_id)
);
`;

function parseJson<T>(value: unknown, fallback: T): T {
  if (value === null || value === undefined || value === "") return fallback;
  try {
    return JSON.parse(String(value)) as T;
  } catch {
    return fallback;
  }
}

function titleize(topicId: string): string {
  return topicId
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export class LocalMemograph {
  private db: DatabaseSync | null = null;
  private readonly basePath: string;
  private readonly topicsPath: string;
  private readonly transcriptsPath: string;
  private readonly dbPath: string;
  private readonly indexPath: string;
  private readonly agentId: string;
  private currentSessionId: string | null = null;
  private turnIndex = 0;

  constructor(options: LocalMemographOptions = {}) {
    this.basePath = path.resolve(options.basePath ?? ".memograph");
    this.topicsPath = path.join(this.basePath, "topics");
    this.transcriptsPath = path.join(this.basePath, "transcripts");
    this.dbPath = path.join(this.basePath, "memograph.db");
    this.indexPath = path.join(this.basePath, "MEMORY.md");
    this.agentId = assertAgentId(options.agentId ?? "default");
  }

  async open(): Promise<void> {
    fs.mkdirSync(this.topicsPath, { recursive: true });
    fs.mkdirSync(this.transcriptsPath, { recursive: true });
    const db = new DatabaseSync(this.dbPath);
    db.exec("PRAGMA journal_mode=WAL;");
    db.exec("PRAGMA foreign_keys=ON;");
    db.exec(SCHEMA);
    this.db = db;
    this.reconcile();
  }

  async close(): Promise<void> {
    if (this.currentSessionId) await this.endSession();
    this.db?.close();
    this.db = null;
  }

  private assertOpen(): DatabaseSync {
    if (!this.db) throw new MemographError("LocalMemograph is not open");
    return this.db;
  }

  private safePath(base: string, ...parts: string[]): string {
    return safePath(base, ...parts);
  }

  private atomicWrite(target: string, content: string): void {
    fs.mkdirSync(path.dirname(target), { recursive: true });
    const temp = `${target}.${process.pid}.${Date.now()}.tmp`;
    const fd = fs.openSync(temp, "w");
    try {
      fs.writeFileSync(fd, content, "utf8");
      fs.fsyncSync(fd);
    } finally {
      fs.closeSync(fd);
    }
    try {
      fs.renameSync(temp, target);
    } catch (error) {
      fs.rmSync(temp, { force: true });
      throw error;
    }
  }

  private transaction<T>(fn: () => T): T {
    const db = this.assertOpen();
    db.exec("BEGIN IMMEDIATE");
    try {
      const result = fn();
      db.exec("COMMIT");
      return result;
    } catch (error) {
      db.exec("ROLLBACK");
      throw error;
    }
  }

  private rows(sql: string, ...params: SqlParam[]): SqlRow[] {
    return this.assertOpen().prepare(sql).all(...params) as unknown as SqlRow[];
  }

  private row(sql: string, ...params: SqlParam[]): SqlRow | undefined {
    return this.assertOpen().prepare(sql).get(...params) as unknown as SqlRow | undefined;
  }

  private run(sql: string, ...params: SqlParam[]): number {
    const result = this.assertOpen().prepare(sql).run(...params) as unknown as {
      changes: number;
    };
    return Number(result.changes ?? 0);
  }

  private allTopics(db: DatabaseSync): TopicFile[] {
    const topics = db
      .prepare("SELECT * FROM topics WHERE agent_id = ? ORDER BY rowid")
      .all(this.agentId) as SqlRow[];
    return topics.map((row) => {
      const topicId = String(row.topic_id);
      const factRows = db
        .prepare(
          "SELECT * FROM facts WHERE agent_id = ? AND topic_id = ? ORDER BY rowid",
        )
        .all(this.agentId, topicId) as SqlRow[];
      const facts: MemoryFact[] = factRows.map((fact) => ({
        fact_id: String(fact.fact_id),
        topic_id: topicId,
        content: String(fact.content),
        source: String(fact.source),
        confidence: String(fact.confidence) as ConfidenceLevel,
        verification_hint: fact.verification_hint ? String(fact.verification_hint) : null,
        created_at: String(fact.created_at),
        last_verified: fact.last_verified ? String(fact.last_verified) : null,
        contradicts_ids: parseJson<string[]>(fact.contradicts_json, []),
        meta: parseJson<Record<string, unknown>>(fact.meta_json, {}),
      }));
      return {
        topic_id: topicId,
        topic_name: String(row.topic_name),
        agent_id: String(row.agent_id),
        facts,
        tags: parseJson<string[]>(row.tags_json, []),
        file_path: String(row.file_path),
        created_at: String(row.created_at),
        last_modified: String(row.last_modified),
      };
    });
  }

  private dreamState(db: DatabaseSync): SqlRow | undefined {
    return db
      .prepare("SELECT * FROM dream_state WHERE agent_id = ?")
      .get(this.agentId) as SqlRow | undefined;
  }

  private buildPointers(db: DatabaseSync): Pointer[] {
    const pointers: Pointer[] = [];
    for (const topic of this.allTopics(db)) {
      if (topic.facts.length === 0) continue;
      const scores = topic.facts.map(
        (fact) => CONFIDENCE_SCORE[fact.confidence] ?? 0.5,
      );
      const average = scores.reduce((sum, score) => sum + score, 0) / scores.length;
      const line = clipText(
        `[${topic.topic_id}] ${topic.facts.length} facts about ${topic.topic_name} -> topics/${topic.topic_id}.json (${topic.last_modified.slice(0, 10)}, conf=${average.toFixed(1)})`,
        MAX_POINTER_CHARS,
      );
      pointers.push({
        topic_id: topic.topic_id,
        pointer_line: line,
        fact_count: topic.facts.length,
        avg_confidence: average,
        last_modified: topic.last_modified,
      });
    }
    return pointers;
  }

  private renderIndex(db: DatabaseSync, pointers: Pointer[]): string {
    const state = this.dreamState(db);
    const last = state?.last_consolidated_at
      ? String(state.last_consolidated_at)
      : "Never";
    return [
      `# Memograph Index - Agent: ${this.agentId}`,
      `Last consolidated: ${last}`,
      `Pointers: ${pointers.length}`,
      "---",
      ...pointers.map((pointer) => pointer.pointer_line),
    ].join("\n");
  }

  private validateIndex(db: DatabaseSync, pointers: Pointer[]): void {
    const markdown = this.renderIndex(db, pointers);
    const lines = markdown.split("\n").length;
    const bytes = Buffer.byteLength(markdown, "utf8");
    if (lines > MAX_INDEX_LINES || bytes > MAX_INDEX_BYTES) {
      throw new MemographError(
        `Index limits exceeded: ${lines} lines, ${bytes} bytes`,
      );
    }
  }

  private rebuildPointers(db: DatabaseSync, pointers: Pointer[]): void {
    db.prepare("DELETE FROM index_pointers WHERE agent_id = ?").run(this.agentId);
    const insert = db.prepare(
      `INSERT INTO index_pointers(
        agent_id, topic_id, pointer_line, fact_count, avg_confidence, last_modified
      ) VALUES (?, ?, ?, ?, ?, ?)`,
    );
    for (const pointer of pointers) {
      insert.run(
        this.agentId,
        pointer.topic_id,
        pointer.pointer_line,
        pointer.fact_count,
        pointer.avg_confidence,
        pointer.last_modified,
      );
    }
  }

  private topicMarkdown(topic: TopicFile): string {
    const verified = topic.facts.filter((fact) => fact.confidence === "verified").length;
    const stale = topic.facts.filter((fact) => fact.confidence === "stale").length;
    const lines = [
      `# Topic: ${topic.topic_name}`,
      `ID: \`${topic.topic_id}\` | Agent: ${topic.agent_id}`,
      `Tags: ${topic.tags.length ? topic.tags.join(", ") : "none"}`,
      `Facts: ${topic.facts.length} (verified=${verified}, stale=${stale})`,
      `Last modified: ${topic.last_modified}`,
      "---",
      "## Facts",
    ];
    for (const fact of topic.facts) {
      lines.push(
        `- [${fact.confidence}] \`${fact.fact_id}\` ${clipText(fact.content, 500)}`,
        `  source: ${fact.source} | verified: ${fact.last_verified ?? "never"}`,
      );
    }
    return lines.join("\n");
  }

  private removeOrphanTopicFiles(pointers: Pointer[]): void {
    const expected = new Set<string>();
    for (const pointer of pointers) {
      expected.add(`${pointer.topic_id}.json`);
      expected.add(`${pointer.topic_id}.md`);
    }
    for (const name of fs.readdirSync(this.topicsPath)) {
      if ((name.endsWith(".json") || name.endsWith(".md")) && !expected.has(name)) {
        fs.rmSync(this.safePath(this.topicsPath, name), { force: true });
      }
    }
  }

  private writeViews(db: DatabaseSync, pointers: Pointer[]): void {
    this.atomicWrite(this.indexPath, this.renderIndex(db, pointers));
    for (const topic of this.allTopics(db)) {
      if (topic.facts.length === 0) continue;
      const jsonPath = this.safePath(this.topicsPath, `${topic.topic_id}.json`);
      const mdPath = this.safePath(this.topicsPath, `${topic.topic_id}.md`);
      this.atomicWrite(jsonPath, JSON.stringify(topic, null, 2));
      this.atomicWrite(mdPath, this.topicMarkdown(topic));
    }
    this.removeOrphanTopicFiles(pointers);
  }

  reconcile(): void {
    const db = this.assertOpen();
    const pointers = this.buildPointers(db);
    this.validateIndex(db, pointers);
    this.transaction(() => this.rebuildPointers(db, pointers));
    this.writeViews(db, pointers);
  }

  private writeViewsWithRecovery(db: DatabaseSync, pointers: Pointer[]): void {
    try {
      this.writeViews(db, pointers);
    } catch (error) {
      this.reconcile();
      throw error;
    }
  }

  async remember(
    topicId: string,
    content: string,
    source = "user",
    options: RememberOptions = {},
  ): Promise<WriteResult> {
    assertTopicId(topicId);
    const text = clipText(assertContent(content), MAX_FACT_CHARS);
    const safeSource = assertSource(source);
    const confidence = assertConfidence(options.confidence);
    const verificationHint = assertVerificationHint(options.verificationHint);
    if (confidence === "verified" && !verificationHint) {
      throw new MemographError("verified facts require a verification hint");
    }
    const db = this.assertOpen();
    const now = nowIso();
    const factId = stableId(`${topicId}|${text}|${safeSource}|${now}`, "fact", 8);
    const topicName = options.topicName ?? titleize(topicId);
    const tags = JSON.stringify(assertTags(options.tags));
    const meta = JSON.stringify(options.meta ?? {});
    const lastVerified = confidence === "verified" ? now : null;
    let pointers: Pointer[] = [];
    this.transaction(() => {
      db.prepare(
        `INSERT INTO topics(
          agent_id, topic_id, topic_name, tags_json, file_path, created_at, last_modified
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(agent_id, topic_id) DO UPDATE SET
          last_modified = excluded.last_modified`,
      ).run(
        this.agentId,
        topicId,
        topicName,
        tags,
        `topics/${topicId}.json`,
        now,
        now,
      );
      db.prepare(
        `INSERT INTO facts(
          agent_id, topic_id, fact_id, content, source, confidence,
          verification_hint, created_at, last_verified, contradicts_json, meta_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      ).run(
        this.agentId,
        topicId,
        factId,
        text,
        safeSource,
        confidence,
        options.verificationHint ?? null,
        now,
        lastVerified,
        "[]",
        meta,
      );
      pointers = this.buildPointers(db);
      this.validateIndex(db, pointers);
      this.rebuildPointers(db, pointers);
    });
    this.writeViewsWithRecovery(db, pointers);
    return {
      success: true,
      skipped: false,
      skip_reason: null,
      error: null,
      fact_id: factId,
    };
  }

  async recall(query: string, topK = 3): Promise<TopicFile[]> {
    const safeQuery = assertQuery(query);
    const safeTopK = assertTopK(topK);
    const db = this.assertOpen();
    const terms = safeQuery.toLowerCase().split(/\s+/).filter(Boolean);
    if (terms.length === 0) return [];
    const scored = this.allTopics(db).map((topic) => {
      const haystack = [
        topic.topic_id,
        topic.topic_name,
        ...topic.tags,
        ...topic.facts.flatMap((fact) => [fact.content, fact.source]),
      ]
        .join(" ")
        .toLowerCase();
      const score = terms.reduce(
        (sum, term) => sum + (haystack.includes(term) ? 1 : 0),
        0,
      );
      return { topic, score };
    });
    return scored
      .filter((item) => item.score > 0)
      .sort((left, right) => right.score - left.score || left.topic.topic_id.localeCompare(right.topic.topic_id))
      .slice(0, safeTopK)
      .map((item) => item.topic);
  }

  async forget(topicId: string, factId?: string): Promise<boolean> {
    assertTopicId(topicId);
    const safeFactId = factId === undefined ? undefined : assertId(factId, "fact_id");
    const db = this.assertOpen();
    let changed = false;
    let pointers: Pointer[] = [];
    this.transaction(() => {
      if (safeFactId) {
        changed =
          this.run(
            "DELETE FROM facts WHERE agent_id = ? AND topic_id = ? AND fact_id = ?",
            this.agentId,
            topicId,
            safeFactId,
          ) > 0;
      } else {
        changed =
          this.run(
            "DELETE FROM topics WHERE agent_id = ? AND topic_id = ?",
            this.agentId,
            topicId,
          ) > 0;
      }
      pointers = this.buildPointers(db);
      this.validateIndex(db, pointers);
      this.rebuildPointers(db, pointers);
    });
    this.writeViewsWithRecovery(db, pointers);
    return changed;
  }

  async update(
    topicId: string,
    factId: string,
    options: UpdateOptions = {},
  ): Promise<boolean> {
    assertTopicId(topicId);
    const safeFactId = assertId(factId, "fact_id");
    const db = this.assertOpen();
    const existing = this.row(
      "SELECT * FROM facts WHERE agent_id = ? AND topic_id = ? AND fact_id = ?",
      this.agentId,
      topicId,
      safeFactId,
    );
    if (!existing) return false;
    const confidence = assertConfidence(
      options.newConfidence ?? (String(existing.confidence) as ConfidenceLevel),
    );
    const verificationSource = assertVerificationHint(options.verificationSource);
    if (confidence === "verified" && !verificationSource) {
      throw new MemographError("verified confidence requires verificationSource");
    }
    const content =
      options.newContent !== undefined
        ? clipText(assertContent(options.newContent), MAX_FACT_CHARS)
        : String(existing.content);
    const verificationHint =
      verificationSource ?? (existing.verification_hint ? String(existing.verification_hint) : null);
    const lastVerified =
      confidence === "verified"
        ? nowIso()
        : existing.last_verified
          ? String(existing.last_verified)
          : null;
    const now = nowIso();
    let pointers: Pointer[] = [];
    this.transaction(() => {
      db.prepare(
        `UPDATE facts SET content = ?, confidence = ?, verification_hint = ?, last_verified = ?
         WHERE agent_id = ? AND topic_id = ? AND fact_id = ?`,
      ).run(
        content,
        confidence,
        verificationHint,
        lastVerified,
        this.agentId,
        topicId,
        factId,
      );
      db.prepare(
        "UPDATE topics SET last_modified = ? WHERE agent_id = ? AND topic_id = ?",
      ).run(now, this.agentId, topicId);
      pointers = this.buildPointers(db);
      this.validateIndex(db, pointers);
      this.rebuildPointers(db, pointers);
    });
    this.writeViewsWithRecovery(db, pointers);
    return true;
  }

  async status(): Promise<Status> {
    const db = this.assertOpen();
    const topics = this.allTopics(db);
    const pointers = this.buildPointers(db);
    const markdown = this.renderIndex(db, pointers);
    const state = this.dreamState(db);
    return {
      provider: "none",
      model: "none",
      local: true,
      agent_id: this.agentId,
      auto_consolidate: false,
      skeptical_mode: true,
      base_path: this.basePath,
      db_path: this.dbPath,
      topics: {
        total: topics.length,
        total_facts: topics.reduce((sum, topic) => sum + topic.facts.length, 0),
      },
      index: {
        pointers: pointers.length,
        lines: markdown.split("\n").length,
        bytes: Buffer.byteLength(markdown, "utf8"),
        max_lines: MAX_INDEX_LINES,
        max_bytes: MAX_INDEX_BYTES,
      },
      last_consolidated: state?.last_consolidated_at
        ? String(state.last_consolidated_at)
        : null,
      sessions_since_last: Number(state?.sessions_since_last ?? 0),
      usage: { total_calls: 0, prompt_tokens: 0, completion_tokens: 0 },
    };
  }

  async index(): Promise<string> {
    const db = this.assertOpen();
    return this.renderIndex(db, this.buildPointers(db));
  }

  async getContextInjection(): Promise<string> {
    return this.index();
  }

  async buildContext(
    query: string,
    maxTopics = 3,
    tokenBudget?: number,
  ): Promise<ContextResult> {
    const safeQuery = assertQuery(query);
    const safeMaxTopics = assertTopK(maxTopics);
    const available =
      tokenBudget ?? Math.max(1, DEFAULT_CONTEXT_TOKENS - OUTPUT_RESERVATION);
    const indexText = await this.index();
    const indexTokens = estimateTokens(indexText);
    const prefix =
      "Memories are hints, not ground truth. Verify against the codebase before acting on them.\n\n" +
      `# Memograph Context\nQuery: ${safeQuery}\n\n`;
    let text = prefix + indexText;
    let totalTokens = estimateTokens(text);
    if (totalTokens > available) {
      throw new MemographError("Index does not fit within the token budget");
    }
    const topics = await this.recall(safeQuery, safeMaxTopics);
    const loaded: string[] = [];
    let topicTokens = 0;
    for (const topic of topics) {
      const markdown = this.topicMarkdown(topic);
      const tokens = estimateTokens(markdown);
      if (totalTokens + tokens > available) continue;
      text += `\n\n## Topic: ${topic.topic_name}\n\n${markdown}`;
      totalTokens += tokens;
      topicTokens += tokens;
      loaded.push(topic.topic_id);
    }
    const ratio = totalTokens / available;
    return {
      text,
      total_tokens: totalTokens,
      index_tokens: indexTokens,
      topic_tokens: topicTokens,
      topics_loaded: loaded,
      pressure_level: ratio > 0.8 ? "high" : ratio > 0.5 ? "medium" : "low",
      available_input: available,
    };
  }

  async dreamNow(force = false): Promise<DreamResult> {
    const db = this.assertOpen();
    const now = nowIso();
    const runId = stableId(`dream:${now}:${Math.random()}`, "dream", 12);
    const state = this.dreamState(db);
    const skipped =
      !force &&
      state?.last_consolidated_at !== undefined &&
      Date.now() - Date.parse(String(state.last_consolidated_at)) < 24 * 60 * 60 * 1000;
    const status = skipped ? "skipped" : "completed";
    this.transaction(() => {
      db.prepare(
        `INSERT INTO dream_runs(
          agent_id, run_id, trigger, status, started_at, ended_at,
          duration_ms, operations_applied, error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      ).run(
        this.agentId,
        runId,
        "manual",
        status,
        now,
        now,
        0,
        0,
        null,
      );
      if (!skipped) {
        db.prepare(
          `INSERT INTO dream_state(
            agent_id, last_run_id, last_consolidated_at, sessions_since_last
          ) VALUES (?, ?, ?, 0)
          ON CONFLICT(agent_id) DO UPDATE SET
            last_run_id = excluded.last_run_id,
            last_consolidated_at = excluded.last_consolidated_at,
            sessions_since_last = 0`,
        ).run(this.agentId, runId, now);
      }
    });
    return {
      run_id: runId,
      skipped,
      skip_reason: skipped ? "Below minimum consolidation interval" : null,
      status,
      operations_applied: 0,
      facts_created: 0,
      facts_merged: 0,
      contradictions_resolved: 0,
      confidence_promoted: 0,
      error: null,
      duration_ms: 0,
      gate_report: null,
    };
  }

  async prune(): Promise<number> {
    const db = this.assertOpen();
    const empty = this.rows(
      "SELECT topic_id FROM index_pointers WHERE agent_id = ? AND fact_count = 0",
      this.agentId,
    );
    let pointers: Pointer[] = [];
    this.transaction(() => {
      db.prepare(
        "DELETE FROM index_pointers WHERE agent_id = ? AND fact_count = 0",
      ).run(this.agentId);
      pointers = this.buildPointers(db);
      this.validateIndex(db, pointers);
      this.rebuildPointers(db, pointers);
    });
    this.writeViewsWithRecovery(db, pointers);
    return empty.length;
  }

  async startSession(sessionId?: string): Promise<string> {
    const db = this.assertOpen();
    const id =
      sessionId ?? stableId(`session:${nowIso()}:${Math.random()}`, "session", 12);
    db.prepare(
      `INSERT INTO sessions(agent_id, session_id, started_at, ended_at, turn_count)
       VALUES (?, ?, ?, NULL, 0)
       ON CONFLICT(agent_id, session_id) DO UPDATE SET started_at = excluded.started_at`,
    ).run(this.agentId, id, nowIso());
    this.currentSessionId = id;
    this.turnIndex = 0;
    return id;
  }

  async endSession(): Promise<void> {
    if (!this.currentSessionId) return;
    this.run(
      "UPDATE sessions SET ended_at = ?, turn_count = ? WHERE agent_id = ? AND session_id = ?",
      nowIso(),
      this.turnIndex,
      this.agentId,
      this.currentSessionId,
    );
    this.currentSessionId = null;
    this.turnIndex = 0;
  }

  async archiveTurn(
    role: string,
    content: string,
    toolCalls: unknown[] = [],
  ): Promise<void> {
    const safeRole = assertSource(role);
    const safeContent = assertContent(content);
    if (!this.currentSessionId) await this.startSession();
    const sessionId = this.currentSessionId as string;
    this.run(
      `INSERT INTO transcripts(
        agent_id, session_id, turn_index, role, content, tool_calls_json, created_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?)`,
      this.agentId,
      sessionId,
      this.turnIndex,
      safeRole,
      safeContent,
      JSON.stringify(toolCalls),
      nowIso(),
    );
    this.turnIndex += 1;
    this.run(
      "UPDATE sessions SET turn_count = ? WHERE agent_id = ? AND session_id = ?",
      this.turnIndex,
      this.agentId,
      sessionId,
    );
  }

  async recentSignals(limit = 20): Promise<string[]> {
    const rows = this.rows(
      `SELECT content FROM transcripts WHERE agent_id = ?
       ORDER BY rowid DESC LIMIT ?`,
      this.agentId,
      Math.max(1, limit),
    );
    return rows.reverse().map((row) => clipText(String(row.content), MAX_SNIPPET_CHARS));
  }

  async grepTranscripts(
    pattern: string,
    maxResults = 20,
    regex = false,
  ): Promise<Array<Record<string, unknown>>> {
    const safeMaxResults = assertMaxResults(maxResults);
    let matcher: (value: string) => boolean;
    if (regex) {
      const compiled = new RegExp(assertRegexPattern(pattern), "i");
      matcher = (value) => compiled.test(value);
    } else {
      const needle = assertString(pattern, "pattern", MAX_GREP_PATTERN_CHARS).toLowerCase();
      matcher = (value) => value.toLowerCase().includes(needle);
    }
    const rows = this.rows(
      `SELECT session_id, role, content, created_at FROM transcripts
       WHERE agent_id = ? ORDER BY rowid`,
      this.agentId,
    );
    const results: Array<Record<string, unknown>> = [];
    for (const row of rows) {
      const content = String(row.content);
      if (!matcher(content)) continue;
      results.push({
        session_id: String(row.session_id),
        role: String(row.role),
        content: clipText(content, MAX_SNIPPET_CHARS),
        created_at: String(row.created_at),
      });
      if (results.length >= safeMaxResults) break;
    }
    return results;
  }
}
