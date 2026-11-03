export type ConfidenceLevel = "verified" | "observed" | "inferred" | "stale";

export interface MemoryFact {
  fact_id: string;
  topic_id: string;
  content: string;
  source: string;
  confidence: ConfidenceLevel;
  verification_hint: string | null;
  created_at: string;
  last_verified: string | null;
  contradicts_ids: string[];
  meta: Record<string, unknown>;
}

export interface TopicFile {
  topic_id: string;
  topic_name: string;
  agent_id: string;
  facts: MemoryFact[];
  tags: string[];
  file_path: string;
  created_at: string;
  last_modified: string;
}

export interface WriteResult {
  success: boolean;
  skipped: boolean;
  skip_reason: string | null;
  error: string | null;
  fact_id: string | null;
}

export interface Status {
  provider: string;
  model: string;
  local: boolean;
  agent_id: string;
  auto_consolidate: boolean;
  skeptical_mode: boolean;
  base_path: string;
  db_path: string;
  topics: { total: number; total_facts: number };
  index: {
    pointers: number;
    lines: number;
    bytes: number;
    max_lines: number;
    max_bytes: number;
  };
  last_consolidated: string | null;
  sessions_since_last: number;
  usage: Record<string, number>;
}

export interface ContextResult {
  text: string;
  total_tokens: number;
  index_tokens: number;
  topic_tokens: number;
  topics_loaded: string[];
  pressure_level: string;
  available_input: number;
}

export interface DreamResult {
  run_id: string;
  skipped: boolean;
  skip_reason: string | null;
  status: string;
  operations_applied: number;
  facts_created: number;
  facts_merged: number;
  contradictions_resolved: number;
  confidence_promoted: number;
  error: string | null;
  duration_ms: number;
  gate_report: Record<string, unknown> | null;
}

export interface MemographEvent {
  type: string;
  payload: Record<string, unknown>;
  timestamp: string;
}

export interface EventSubscription extends AsyncIterableIterator<MemographEvent> {
  close(): void;
}

export interface HealthResponse {
  status: string;
  version: string;
}

export interface RememberRequest {
  topic_id: string;
  content: string;
  source?: string;
  confidence?: ConfidenceLevel;
  tags?: string[];
  verification_hint?: string | null;
}

export interface UpdateRequest {
  topic_id: string;
  fact_id: string;
  new_content?: string | null;
  new_confidence?: ConfidenceLevel | null;
  verification_source?: string | null;
}

export interface ContextRequest {
  query: string;
  max_topics?: number;
  token_budget?: number | null;
}

export interface GrepRequest {
  pattern: string;
  max_results?: number;
  regex?: boolean;
}

export interface IndexResponse {
  index: string;
}

export interface PruneResponse {
  pointers_removed: number;
}

export interface RememberOptions {
  confidence?: ConfidenceLevel;
  tags?: string[];
  topicName?: string;
  verificationHint?: string | null;
  meta?: Record<string, unknown>;
}

export interface UpdateOptions {
  newContent?: string;
  newConfidence?: ConfidenceLevel;
  verificationSource?: string;
}

export interface LocalMemographOptions {
  basePath?: string;
  agentId?: string;
}
