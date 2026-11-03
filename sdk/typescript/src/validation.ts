import { createHash } from "node:crypto";
import * as fs from "node:fs";
import * as path from "node:path";

import type { ConfidenceLevel } from "./types.js";

export class MemographError extends Error {
  readonly status?: number;
  readonly body?: unknown;

  constructor(message: string, status?: number, body?: unknown) {
    super(message);
    this.name = "MemographError";
    this.status = status;
    this.body = body;
  }
}

const TOPIC_ID_RE = /^[a-z][a-z0-9_]{0,49}$/;
const AGENT_ID_RE = /^[a-z][a-z0-9_-]{0,49}$/;
const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);
const SUSPICIOUS_REGEX = [
  /\([^)]*[+*][^)]*\)[+*{]/, // nested quantifiers such as (a+)+
  /\(\?[=!]/, // lookarounds
  /\\[1-9]/, // backreferences
  /\{[0-9]+,\}[+*{]/, // open-ended repetition followed by a quantifier
];

export const MAX_INDEX_LINES = 200;
export const MAX_INDEX_BYTES = 25_600;
export const MAX_POINTER_CHARS = 150;
export const MAX_SUMMARY_CHARS = 80;
export const MAX_FACT_CHARS = 1_000;
export const MAX_QUERY_CHARS = 1_000;
export const MAX_SOURCE_CHARS = 200;
export const MAX_VERIFICATION_HINT_CHARS = 200;
export const MAX_ID_CHARS = 100;
export const MAX_TAG_COUNT = 20;
export const MAX_TOP_K = 20;
export const MAX_GREP_PATTERN_CHARS = 200;
export const MAX_GREP_RESULTS = 100;
export const MAX_SNIPPET_CHARS = 200;
export const MIN_API_KEY_CHARS = 16;
export const MAX_REQUEST_BYTES = 1_048_576;

export function assertTopicId(value: string): string {
  if (!TOPIC_ID_RE.test(value)) {
    throw new MemographError(
      `Invalid topic ID ${JSON.stringify(value)}; expected ^[a-z][a-z0-9_]{0,49}$`,
    );
  }
  return value;
}

export function assertAgentId(value: string): string {
  if (!AGENT_ID_RE.test(value)) {
    throw new MemographError(`Invalid agent ID ${JSON.stringify(value)}`);
  }
  return value;
}

export function assertString(value: unknown, field: string, max: number): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new MemographError(`${field} must be a non-empty string`);
  }
  if (value.length > max) {
    throw new MemographError(`${field} too long: ${value.length} > ${max}`);
  }
  return value;
}

export function assertContent(value: string, max = MAX_FACT_CHARS): string {
  return assertString(value, "content", max);
}

export function assertSource(value: string): string {
  return assertString(value, "source", MAX_SOURCE_CHARS);
}

export function assertQuery(value: string): string {
  return assertString(value, "query", MAX_QUERY_CHARS);
}

export function assertId(value: string, field: string): string {
  return assertString(value, field, MAX_ID_CHARS);
}

export function assertVerificationHint(
  value: string | null | undefined,
): string | undefined {
  if (value === undefined || value === null) return undefined;
  return assertString(value, "verification_hint", MAX_VERIFICATION_HINT_CHARS);
}

export function assertTags(value: string[] | undefined): string[] {
  if (value === undefined) return [];
  if (!Array.isArray(value) || value.length > MAX_TAG_COUNT) {
    throw new MemographError(`tags must contain at most ${MAX_TAG_COUNT} entries`);
  }
  return value.map((tag) => assertString(tag, "tag", MAX_SOURCE_CHARS));
}

export function assertConfidence(value: ConfidenceLevel | undefined): ConfidenceLevel {
  const allowed: ConfidenceLevel[] = ["verified", "observed", "inferred", "stale"];
  if (value !== undefined && !allowed.includes(value)) {
    throw new MemographError(`Invalid confidence ${JSON.stringify(value)}`);
  }
  return value ?? "observed";
}

export function assertTopK(value: number): number {
  if (!Number.isInteger(value) || value < 1 || value > MAX_TOP_K) {
    throw new MemographError(`top_k must be between 1 and ${MAX_TOP_K}`);
  }
  return value;
}

export function assertMaxResults(value: number): number {
  if (!Number.isInteger(value) || value < 1 || value > MAX_GREP_RESULTS) {
    throw new MemographError(`max_results must be between 1 and ${MAX_GREP_RESULTS}`);
  }
  return value;
}

export function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function assertLiteralPattern(value: string): string {
  return escapeRegExp(assertString(value, "pattern", MAX_GREP_PATTERN_CHARS));
}

export function assertRegexPattern(value: string): string {
  const pattern = assertString(value, "pattern", MAX_GREP_PATTERN_CHARS);
  if (SUSPICIOUS_REGEX.some((check) => check.test(pattern))) {
    throw new MemographError("Regex pattern contains a potentially catastrophic construct");
  }
  try {
    new RegExp(pattern);
  } catch {
    throw new MemographError("Invalid regex pattern");
  }
  return pattern;
}

export function assertApiKey(value: string): string {
  if (typeof value !== "string" || value.length < MIN_API_KEY_CHARS) {
    throw new MemographError(`API key must be at least ${MIN_API_KEY_CHARS} characters`);
  }
  return value;
}

function realPathAllowingMissing(target: string): string {
  let cursor = target;
  const suffix: string[] = [];
  while (!fs.existsSync(cursor)) {
    const parent = path.dirname(cursor);
    if (parent === cursor) break;
    suffix.unshift(path.basename(cursor));
    cursor = parent;
  }
  try {
    cursor = fs.realpathSync(cursor);
  } catch {
    return target;
  }
  return path.join(cursor, ...suffix);
}

export function safePath(basePath: string, ...segments: string[]): string {
  const resolvedBase = path.resolve(basePath);
  const realBase = realPathAllowingMissing(resolvedBase);
  const target = path.resolve(resolvedBase, ...segments);
  const realTarget = realPathAllowingMissing(target);
  if (realTarget !== realBase && !realTarget.startsWith(realBase + path.sep)) {
    throw new MemographError("Path escape rejected");
  }
  return target;
}

export function validateBaseUrl(value: string): string {
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    throw new MemographError("baseUrl must be an absolute http(s) URL");
  }
  if (parsed.username || parsed.password) {
    throw new MemographError("baseUrl must not contain credentials");
  }
  if (parsed.search || parsed.hash) {
    throw new MemographError("baseUrl must not contain a query string or fragment");
  }
  const loopback = LOOPBACK_HOSTS.has(parsed.hostname);
  if (parsed.protocol === "http:" && !loopback) {
    throw new MemographError("Remote baseUrl must use https");
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    throw new MemographError("baseUrl must use http or https");
  }
  parsed.pathname = parsed.pathname.replace(/\/+$/, "") + "/";
  return parsed.toString();
}

export function stableId(value: string, prefix = "id", length = 12): string {
  const digest = createHash("sha256").update(value, "utf8").digest("hex");
  return `${prefix}_${digest.slice(0, Math.max(1, Math.min(length, 64)))}`;
}

export function clipText(value: string, limit: number): string {
  if (value.length <= limit) return value;
  return `${value.slice(0, Math.max(0, limit - 1))}…`;
}

export function estimateTokens(text: string): number {
  return Math.max(1, Math.ceil(text.length / 4));
}

export function nowIso(): string {
  return new Date().toISOString();
}
