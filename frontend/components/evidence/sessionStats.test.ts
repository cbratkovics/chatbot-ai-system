import { describe, expect, it } from 'vitest';
import { computeSessionStats, percentile } from './sessionStats';
import type { ChatMsg, Telemetry } from './types';

let n = 0;
const user = (content: string): ChatMsg => ({ id: `u${++n}`, role: 'user', content });
const assistant = (telemetry: Partial<Telemetry> | undefined, extra: Partial<ChatMsg> = {}): ChatMsg => ({
  id: `a${++n}`,
  role: 'assistant',
  content: 'x',
  telemetry: telemetry as Telemetry,
  ...extra,
});

const miss = (over: Partial<Telemetry> = {}): Partial<Telemetry> => ({
  provider: 'openai',
  model: 'gpt-4o-mini',
  cache: { status: 'miss', match: null, similarity: null },
  latency_ms: 900,
  ttfb_ms: 400,
  cost_usd: 0.00002,
  cost_avoided_usd: 0,
  streamed: true,
  attempts: [{ provider: 'openai', model: 'gpt-4o-mini', outcome: 'ok', latency_ms: 880 }],
  ...over,
});

describe('percentile (nearest rank, matches bench_demo.py)', () => {
  it('returns null on empty input', () => {
    expect(percentile([], 50)).toBeNull();
  });
  it('uses round((p/100)*(n-1)) like the Python scripts', () => {
    const values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100];
    expect(percentile(values, 50)).toBe(60); // round(4.5) = 5 -> 60
    expect(percentile(values, 95)).toBe(100); // round(8.55) = 9
    expect(percentile([5], 95)).toBe(5);
    expect(percentile([3, 1, 2], 0)).toBe(1);
  });
});

describe('computeSessionStats', () => {
  it('is all-null / zero on an empty session', () => {
    const s = computeSessionStats([]);
    expect(s.answered).toBe(0);
    expect(s.hitRate).toBeNull();
    expect(s.latency).toEqual({ p50: null, p95: null, n: 0 });
    expect(s.points).toEqual([]);
    expect(s.providers).toEqual([]);
  });

  it('ignores user messages and pending assistants', () => {
    const s = computeSessionStats([user('hi'), assistant(undefined, { pending: true })]);
    expect(s.answered).toBe(0);
    expect(s.points).toHaveLength(0);
  });

  it('computes hit rate, spend and avoided cost from telemetry', () => {
    const msgs = [
      user('q'),
      assistant(miss(), { clientMs: 1000, clientTtfbMs: 450 }),
      user('q again'),
      assistant(
        {
          provider: 'openai',
          cache: { status: 'hit', match: 'exact', similarity: 1 },
          cost_usd: 0,
          cost_avoided_usd: 0.00002,
          streamed: true,
        },
        { clientMs: 40, clientTtfbMs: 30 },
      ),
      user('paraphrase'),
      assistant(
        {
          provider: 'openai',
          cache: { status: 'hit', match: 'semantic', similarity: 0.93 },
          cost_usd: 0.0000002,
          cost_avoided_usd: 0.00002,
          streamed: true,
        },
        { clientMs: 300, clientTtfbMs: 280 },
      ),
    ];
    const s = computeSessionStats(msgs);
    expect(s.answered).toBe(3);
    expect(s.hits).toBe(2);
    expect(s.exactHits).toBe(1);
    expect(s.semanticHits).toBe(1);
    expect(s.misses).toBe(1);
    expect(s.hitRate).toBeCloseTo(2 / 3);
    expect(s.spentUsd).toBeCloseTo(0.0000202, 10);
    expect(s.avoidedUsd).toBeCloseTo(0.00004, 10);
    expect(s.spentUnknown).toBe(0);
    expect(s.avoidedUnknown).toBe(0);
    expect(s.similarities).toEqual([0.93]);
    // latency is client-observed: [1000, 40, 300]
    expect(s.latency).toEqual({ p50: 300, p95: 1000, n: 3 });
    // TTFB only counts streamed misses
    expect(s.ttfbStreamedMiss).toEqual({ p50: 450, p95: 450, n: 1 });
    expect(s.providers).toEqual([
      { name: 'cache', count: 2 },
      { name: 'openai', count: 1 },
    ]);
    expect(s.points.map((p) => p.kind)).toEqual(['miss', 'hit', 'hit']);
  });

  it('treats missing new fields as unknown, not zero (older backend)', () => {
    const old = {
      provider: 'openai',
      cache: { status: 'hit' as const, backend: 'memory', similarity: 1 },
      latency_ms: 5,
      cost_usd: 0,
      streamed: true,
    };
    const s = computeSessionStats([user('q'), assistant(old)]);
    expect(s.hits).toBe(1);
    expect(s.exactHits).toBe(1); // no cache.match -> counted as exact
    expect(s.avoidedUnknown).toBe(1);
    expect(s.avoidedUsd).toBe(0);
    expect(s.similarities).toEqual([]);
    // falls back to server latency when the browser did not record clientMs
    expect(s.latency.p50).toBe(5);
  });

  it('counts unknown cost when cost_usd is null (unpriced model)', () => {
    const s = computeSessionStats([user('q'), assistant(miss({ cost_usd: null }))]);
    expect(s.spentUsd).toBe(0);
    expect(s.spentUnknown).toBe(1);
  });

  it('records failover events with their attempt chain', () => {
    const attempts = [
      { provider: 'openai', model: 'gpt-4o-mini', outcome: 'failed' as const, status_code: 503, error_code: 'simulated_outage' },
      { provider: 'groq', model: 'llama-3.1-8b-instant', outcome: 'ok' as const, latency_ms: 700 },
    ];
    const s = computeSessionStats([
      user('q'),
      assistant(miss({ provider: 'groq', model: 'llama-3.1-8b-instant', failover: true, simulated_failure: true, attempts }), {
        clientMs: 900,
      }),
    ]);
    expect(s.failovers).toHaveLength(1);
    expect(s.failovers[0]).toMatchObject({ index: 1, provider: 'groq', simulated: true, clientMs: 900 });
    expect(s.failovers[0].attempts).toHaveLength(2);
    expect(s.points[0].kind).toBe('failover');
    expect(s.providers).toEqual([{ name: 'groq', count: 1 }]);
  });

  it('keeps failed requests out of the answered count but on the timeline', () => {
    const s = computeSessionStats([user('q'), assistant(undefined, { failed: true, clientMs: 120 })]);
    expect(s.answered).toBe(0);
    expect(s.errors).toBe(1);
    expect(s.points).toEqual([{ index: 1, ms: 120, kind: 'error', label: 'request failed' }]);
    expect(s.hitRate).toBeNull();
  });

  it('bypass responses are neither hits nor misses for the hit rate', () => {
    const s = computeSessionStats([
      user('q'),
      assistant(miss({ cache: { status: 'bypass' } })),
      user('q'),
      assistant(miss()),
    ]);
    expect(s.bypass).toBe(1);
    expect(s.misses).toBe(1);
    expect(s.hitRate).toBe(0);
  });
});
