import WebSocket from "ws";

import type {
  ContextRequest,
  ContextResult,
  DreamResult,
  EventSubscription,
  GrepRequest,
  HealthResponse,
  IndexResponse,
  MemographEvent,
  PruneResponse,
  RememberRequest,
  Status,
  TopicFile,
  UpdateRequest,
  WriteResult,
} from "./types.js";
import {
  MAX_REQUEST_BYTES,
  MemographError,
  assertApiKey,
  assertRegexPattern,
  validateBaseUrl,
} from "./validation.js";

export interface MemographClientOptions {
  baseUrl: string;
  apiKey: string;
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
  maxRequestBytes?: number;
}

class WsEventSubscription implements EventSubscription {
  private readonly queue: MemographEvent[] = [];
  private readonly waiters: Array<(result: IteratorResult<MemographEvent>) => void> = [];
  private closed = false;

  constructor(private readonly ws: WebSocket) {
    ws.on("message", (data) => {
      try {
        const event = JSON.parse(String(data)) as MemographEvent;
        this.push(event);
      } catch {
        // Ignore malformed frames; the server only emits JSON events.
      }
    });
    ws.on("close", () => this.close(false));
    ws.on("error", () => this.close(false));
  }

  private push(event: MemographEvent): void {
    if (this.closed) return;
    const waiter = this.waiters.shift();
    if (waiter) {
      waiter({ done: false, value: event });
    } else {
      this.queue.push(event);
    }
  }

  async next(): Promise<IteratorResult<MemographEvent>> {
    const queued = this.queue.shift();
    if (queued) return { done: false, value: queued };
    if (this.closed) return { done: true, value: undefined };
    return new Promise((resolve) => this.waiters.push(resolve));
  }

  [Symbol.asyncIterator](): AsyncIterableIterator<MemographEvent> {
    return this;
  }

  close(terminate = true): void {
    if (this.closed) return;
    this.closed = true;
    for (const waiter of this.waiters.splice(0)) {
      waiter({ done: true, value: undefined });
    }
    if (
      terminate &&
      (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)
    ) {
      this.ws.close();
    }
  }
}

export class MemographClient {
  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly fetchImpl: typeof fetch;
  private readonly timeoutMs: number;
  private readonly maxRequestBytes: number;

  constructor(options: MemographClientOptions) {
    this.baseUrl = validateBaseUrl(options.baseUrl);
    this.apiKey = assertApiKey(options.apiKey);
    this.fetchImpl = options.fetchImpl ?? globalThis.fetch;
    this.timeoutMs = options.timeoutMs ?? 30_000;
    this.maxRequestBytes = options.maxRequestBytes ?? MAX_REQUEST_BYTES;
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    if (typeof init.body === "string") {
      const bytes = new TextEncoder().encode(init.body).length;
      if (bytes > this.maxRequestBytes) {
        throw new MemographError("Request body too large", 413);
      }
    }
    const url = new URL(path.replace(/^\//, ""), this.baseUrl).toString();
    const headers = new Headers(init.headers);
    headers.set("X-API-Key", this.apiKey);
    if (init.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    const response = await this.fetchImpl(url, {
      ...init,
      headers,
      signal: AbortSignal.timeout(this.timeoutMs),
    });
    const text = await response.text();
    let body: unknown = text;
    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        // Keep the raw text for error reporting.
      }
    }
    if (!response.ok) {
      throw new MemographError(
        `Memograph API returned ${response.status}: ${text}`,
        response.status,
        body,
      );
    }
    return body as T;
  }

  private jsonBody(value: unknown): string {
    return JSON.stringify(value);
  }

  health(): Promise<HealthResponse> {
    return this.request<HealthResponse>("health");
  }

  openapi(): Promise<Record<string, unknown>> {
    return this.request<Record<string, unknown>>("openapi.json");
  }

  status(): Promise<Status> {
    return this.request<Status>("status");
  }

  remember(payload: RememberRequest): Promise<WriteResult> {
    return this.request<WriteResult>("remember", {
      method: "POST",
      body: this.jsonBody(payload),
    });
  }

  recall(query: string, topK = 3, verify = false): Promise<TopicFile[]> {
    const params = new URLSearchParams({ query, top_k: String(topK), verify: String(verify) });
    return this.request<TopicFile[]>(`recall?${params.toString()}`);
  }

  forget(topicId: string, factId?: string): Promise<{ forgotten: boolean }> {
    return this.request<{ forgotten: boolean }>("forget", {
      method: "POST",
      body: this.jsonBody({ topic_id: topicId, fact_id: factId ?? null }),
    });
  }

  update(payload: UpdateRequest): Promise<{ updated: boolean }> {
    return this.request<{ updated: boolean }>("update", {
      method: "POST",
      body: this.jsonBody(payload),
    });
  }

  context(payload: ContextRequest): Promise<ContextResult> {
    return this.request<ContextResult>("context", {
      method: "POST",
      body: this.jsonBody(payload),
    });
  }

  dream(force = false): Promise<DreamResult> {
    return this.request<DreamResult>("dream", {
      method: "POST",
      body: this.jsonBody({ force }),
    });
  }

  prune(): Promise<PruneResponse> {
    return this.request<PruneResponse>("prune", { method: "POST" });
  }

  index(): Promise<IndexResponse> {
    return this.request<IndexResponse>("index");
  }

  grep(payload: GrepRequest): Promise<Array<Record<string, unknown>>> {
    if (payload.regex) assertRegexPattern(payload.pattern);
    return this.request<Array<Record<string, unknown>>>("grep", {
      method: "POST",
      body: this.jsonBody(payload),
    });
  }

  events(): EventSubscription {
    const url = new URL("events", this.baseUrl);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(url.toString(), {
      headers: { "X-API-Key": this.apiKey },
    });
    return new WsEventSubscription(ws);
  }
}
