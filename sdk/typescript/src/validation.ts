import { createHash } from "node:crypto";

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
