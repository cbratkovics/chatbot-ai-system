/** Pure derivation of the Evidence rail from this session's messages. No fetches, no side effects.
 *  Every number here traces back to a field the backend put on a `done` event or to a timestamp
 *  this browser took around the request. Missing fields count as "unknown", never as zero. */

import type { Attempt, ChatMsg, Telemetry } from './types';

export type PathKind = 'hit' | 'miss' | 'failover' | 'error';

export type LatencyPoint = {
  index: number;
  ms: number | null;
  kind: PathKind;
  label: string;
  similarity?: number | null;
};

export type FailoverEvent = {
  index: number;
  attempts: Attempt[];
  provider?: string;
  model?: string;
  simulated: boolean;
  clientMs?: number;
};

export type ProviderShare = { name: string; count: number };

export type SessionStats = {
  answered: number;
  errors: number;
  hits: number;
  exactHits: number;
  semanticHits: number;
  misses: number;
  bypass: number;
  hitRate: number | null;
  spentUsd: number;
  spentUnknown: number;
  avoidedUsd: number;
  avoidedUnknown: number;
  latency: { p50: number | null; p95: number | null; n: number };
  ttfbStreamedMiss: { p50: number | null; p95: number | null; n: number };
  failovers: FailoverEvent[];
  providers: ProviderShare[];
  points: LatencyPoint[];
  similarities: number[];
};

/** Nearest-rank percentile, the same definition `scripts/bench_demo.py` and `evals/stats.py` use. */
export function percentile(values: number[], pct: number): number | null {
  if (!values.length) return null;
  const ordered = [...values].sort((a, b) => a - b);
  const index = Math.min(ordered.length - 1, Math.max(0, Math.round((pct / 100) * (ordered.length - 1))));
  return ordered[index];
}

function isFiniteNumber(x: unknown): x is number {
  return typeof x === 'number' && Number.isFinite(x);
}

function pathKind(t: Telemetry): PathKind {
  if (t.failover) return 'failover';
  return t.cache?.status === 'hit' ? 'hit' : 'miss';
}

export function computeSessionStats(messages: ChatMsg[]): SessionStats {
  const stats: SessionStats = {
    answered: 0,
    errors: 0,
    hits: 0,
    exactHits: 0,
    semanticHits: 0,
    misses: 0,
    bypass: 0,
    hitRate: null,
    spentUsd: 0,
    spentUnknown: 0,
    avoidedUsd: 0,
    avoidedUnknown: 0,
    latency: { p50: null, p95: null, n: 0 },
    ttfbStreamedMiss: { p50: null, p95: null, n: 0 },
    failovers: [],
    providers: [],
    points: [],
    similarities: [],
  };

  const latencies: number[] = [];
  const ttfbs: number[] = [];
  const providerCounts = new Map<string, number>();
  let index = 0;

  for (const m of messages) {
    if (m.role !== 'assistant' || m.pending) continue;
    index += 1;
    const t = m.telemetry;

    if (!t) {
      if (m.failed) {
        stats.errors += 1;
        stats.points.push({ index, ms: m.clientMs ?? null, kind: 'error', label: 'request failed' });
      }
      continue;
    }

    stats.answered += 1;
    const status = t.cache?.status;
    const kind = pathKind(t);

    if (status === 'hit') {
      stats.hits += 1;
      if (t.cache?.match === 'semantic') stats.semanticHits += 1;
      else stats.exactHits += 1;
      if (isFiniteNumber(t.cache?.similarity) && t.cache?.match === 'semantic') {
        stats.similarities.push(t.cache.similarity);
      }
      if (isFiniteNumber(t.cost_avoided_usd)) stats.avoidedUsd += t.cost_avoided_usd;
      else stats.avoidedUnknown += 1; // backend predates cost_avoided_usd
      providerCounts.set('cache', (providerCounts.get('cache') ?? 0) + 1);
    } else {
      if (status === 'bypass') stats.bypass += 1;
      else stats.misses += 1;
      const name = t.provider || 'unknown';
      providerCounts.set(name, (providerCounts.get(name) ?? 0) + 1);
    }

    if (isFiniteNumber(t.cost_usd)) stats.spentUsd += t.cost_usd;
    else stats.spentUnknown += 1;

    const ms = m.clientMs ?? t.latency_ms ?? null;
    if (isFiniteNumber(ms)) latencies.push(ms);
    if (t.streamed && status !== 'hit' && isFiniteNumber(m.clientTtfbMs)) ttfbs.push(m.clientTtfbMs);

    if (t.failover) {
      stats.failovers.push({
        index,
        attempts: t.attempts ?? [],
        provider: t.provider,
        model: t.model,
        simulated: Boolean(t.simulated_failure),
        clientMs: m.clientMs,
      });
    }

    stats.points.push({
      index,
      ms: isFiniteNumber(ms) ? ms : null,
      kind,
      label: `${status ?? 'unknown'}${t.cache?.match === 'semantic' ? ' (semantic)' : ''} · ${t.provider ?? '?'}`,
      similarity: t.cache?.similarity ?? null,
    });
  }

  const decided = stats.hits + stats.misses;
  stats.hitRate = decided ? stats.hits / decided : null;
  stats.latency = { p50: percentile(latencies, 50), p95: percentile(latencies, 95), n: latencies.length };
  stats.ttfbStreamedMiss = { p50: percentile(ttfbs, 50), p95: percentile(ttfbs, 95), n: ttfbs.length };
  stats.providers = [...providerCounts.entries()]
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
  stats.spentUsd = round(stats.spentUsd);
  stats.avoidedUsd = round(stats.avoidedUsd);
  return stats;
}

function round(usd: number): number {
  return Math.round(usd * 1e10) / 1e10;
}
