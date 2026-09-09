/** Mirrors the backend `telemetry` object on the `done` event / JSON response (ADR 0005, 0007).
 *  Every field is optional: older deployments may lack the Phase 1 additions
 *  (`cost_avoided_usd`, `cache.match`, `cache.semantic`, `embedding`). */

export type Role = 'user' | 'assistant' | 'system';
export type CacheStatus = 'hit' | 'miss' | 'bypass';
export type CacheMatch = 'exact' | 'semantic';
export type SemanticState = 'disabled' | 'not_needed' | 'hit' | 'miss' | 'unavailable';

export type Attempt = {
  provider: string;
  model: string;
  outcome: 'ok' | 'failed' | 'skipped';
  status_code?: number | null;
  error_code?: string | null;
  message?: string | null;
  latency_ms?: number;
};

export type CacheInfo = {
  status?: CacheStatus;
  backend?: string;
  similarity?: number | null;
  match?: CacheMatch | null;
  semantic?: SemanticState;
  matched_key?: string | null;
  threshold?: number | null;
  age_seconds?: number;
};

export type Usage = {
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  source?: 'provider' | 'estimated' | 'none' | string;
};

export type EmbeddingInfo = {
  model?: string | null;
  tokens?: number;
  latency_ms?: number | null;
  cost_usd?: number;
};

export type Telemetry = {
  request_id?: string;
  provider?: string;
  model?: string;
  cache?: CacheInfo;
  latency_ms?: number;
  ttfb_ms?: number | null;
  usage?: Usage;
  cost_usd?: number | null;
  cost_avoided_usd?: number | null;
  embedding?: EmbeddingInfo;
  attempts?: Attempt[];
  failover?: boolean;
  simulated_failure?: boolean;
  streamed?: boolean;
};

export type ChatMsg = {
  id: string;
  role: Role;
  content: string;
  telemetry?: Telemetry;
  pending?: boolean;
  failed?: boolean;
  /** Wall time in this browser from send to the final event. */
  clientMs?: number;
  /** Wall time in this browser from send to the first content delta. */
  clientTtfbMs?: number;
  /** User turn sent without conversation history (memory off, or a guided-demo step). */
  standalone?: boolean;
};

export type SemanticCacheHealth = {
  enabled?: boolean;
  backend?: string | null;
  embedding_model?: string | null;
  threshold?: number | null;
  index_entries?: number;
  max_entries?: number;
};

export type ChatHealth = {
  status?: string;
  cache?: string;
  default_model?: string;
  fallback_chain?: string[];
  semantic_cache?: SemanticCacheHealth;
  demo?: { failure_toggle_enabled?: boolean; simulate_header?: string };
};

export type HighlightKey = 'cache' | 'cost' | 'latency' | 'failover';
export type Highlight = { key: HighlightKey; nonce: number } | null;
