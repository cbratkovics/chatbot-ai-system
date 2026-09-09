/** Shape of evals/results/latest.json (schema_version 1) as written by `python -m evals.run`. */

export type Summary = {
  n: number;
  p50: number | null;
  p95: number | null;
  p99: number | null;
  min: number | null;
  max: number | null;
  mean: number | null;
};

export type SweepRow = {
  threshold: number;
  tp: number;
  fp: number;
  fn: number;
  tn: number;
  precision: number | null;
  recall: number | null;
  f1: number | null;
};

export type KindRow = {
  n: number;
  tp: number;
  fp: number;
  fn: number;
  tn: number;
  precision: number | null;
  recall: number | null;
  f1: number | null;
};

export type Example = {
  id: string;
  kind: string;
  label: 'hit' | 'miss';
  a: string;
  b: string;
  similarity: number | null;
  predicted_hit: boolean;
  correct_entry: boolean;
  outcome: 'true_positive' | 'false_positive' | 'false_negative' | 'true_negative';
};

export type CacheEval = {
  status: 'ok' | 'skipped';
  reason?: string;
  n_pairs: number;
  threshold?: number | null;
  tp?: number;
  fp?: number;
  fn?: number;
  tn?: number;
  precision?: number | null;
  recall?: number | null;
  f1?: number | null;
  by_kind?: Record<string, KindRow>;
  sweep?: SweepRow[];
  best_threshold_by_f1?: number | null;
  sweep_note?: string;
  examples?: Example[];
  dataset?: string;
  dataset_sha256_16?: string;
  embedding_model?: string | null;
  seed_hits?: number;
  seed_failures?: number;
  probe_failures?: number;
  duration_s?: number;
};

export type CheckCounts = Record<string, { passed: number; failed: number }>;

export type FailoverEval = {
  status: 'ok' | 'skipped';
  reason?: string;
  n: number;
  passed?: number;
  success_rate?: number | null;
  checks?: CheckCounts;
  fallback_provider?: string | null;
  fallback_model?: string | null;
  fallback_chain?: string[];
  latency_ms?: {
    failover: { ttfb: Summary; total: Summary };
    baseline: { ttfb: Summary; total: Summary };
    added_ttfb_p50: number | null;
    added_total_p50: number | null;
    simulated_primary_failure_ms?: Summary;
    note?: string;
  };
};

export type SseEval = {
  status: 'ok' | 'skipped';
  reason?: string;
  n: number;
  passed?: number;
  pass_rate?: number | null;
  checks?: CheckCounts;
  paths?: Record<string, number>;
  event_shapes?: string[];
};

export type LatencyPath = {
  n: number;
  client_ms: Summary;
  client_ttfb_ms: Summary;
  server_ms: Summary;
  server_ttfb_ms: Summary;
  streamed_share?: number;
};

export type LatencyEval = {
  status: 'ok' | 'skipped';
  n?: number;
  errors?: number;
  paths?: Record<string, LatencyPath>;
  note?: string;
};

export type RunInfo = {
  timestamp: string;
  commit?: string | null;
  commit_dirty?: boolean;
  base_url: string;
  duration_s?: number;
  requests?: number;
  failed_requests?: number;
  python?: string;
  environment?: {
    cache?: string;
    semantic_cache?: { enabled?: boolean; backend?: string | null; embedding_model?: string | null; threshold?: number | null; max_entries?: number };
    default_model?: string;
    fallback_chain?: string[];
    guardrails_enabled?: boolean;
    streaming?: string;
  };
};

export type EvalArtifact = {
  schema_version: number;
  run: RunInfo;
  cache_paraphrase?: CacheEval;
  failover?: FailoverEval;
  sse_contract?: SseEval;
  latency?: LatencyEval;
  cost?: { requests?: number; estimated_usd_spent?: number; avoided_usd?: number; note?: string };
};

export type ArtifactSource = 'live' | 'static';
