'use client';

import Link from 'next/link';
import { FailoverTimeline } from './FailoverTimeline';
import { fmtCost, fmtMs, fmtPct, fmtSimilarity } from './format';
import { ProviderBar } from './ProviderBar';
import type { SessionStats } from './sessionStats';
import { percentile } from './sessionStats';
import { Sparkline } from './Sparkline';
import { Tile } from './Tile';
import type { Highlight } from './types';

type Props = {
  stats: SessionStats;
  highlight: Highlight;
  /** From /chat/health; null while unknown. Decides how the cache tile is worded. */
  semanticEnabled: boolean | null;
  onStartDemo: () => void;
};

const WHY = {
  hitRate:
    'The semantic cache serves repeats and paraphrases without a provider call. Every hit is a free, near-instant answer. Rate = hits ÷ (hits + misses) in this session.',
  cost: 'Spent is the list-price cost of every provider and embedding call this session. Avoided is what the cached answers would have cost if the provider had been called again.',
  latency:
    'Wall time measured in this browser from send to the final event, so it includes the network and any free-tier wake-up. P50 is the typical request; P95 is the slow tail.',
  ttfb: 'Time to the first streamed token on cache misses, measured here. It is what a user feels as responsiveness while the rest of the answer is still streaming.',
  failover:
    'Requests where the primary provider failed (401, 402, 429, 5xx, timeout) and a fallback answered instead. Each one is listed below with the attempt chain the backend recorded.',
};

export function EvidenceRail({ stats, highlight, semanticEnabled, onStartDemo }: Props) {
  const empty = stats.answered === 0 && stats.errors === 0;
  const hl = (key: NonNullable<Highlight>['key']) => highlight?.key === key;
  const medianSim = percentile(stats.similarities, 50);

  return (
    <div className="flex h-full flex-col gap-3 text-sm">
      <div>
        <h2 className="text-base font-semibold">Evidence</h2>
        <p className="text-[11px] text-muted-foreground">Derived from this session’s telemetry only. Reloading clears it.</p>
      </div>

      {empty ? (
        <EmptyState onStartDemo={onStartDemo} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2">
            <Tile
              label="Cache hit rate"
              value={fmtPct(stats.hitRate)}
              sub={`${stats.hits} hit${stats.hits === 1 ? '' : 's'}${
                stats.semanticHits ? ` · ${stats.semanticHits} semantic${medianSim !== null ? ` (median ${fmtSimilarity(medianSim)})` : ''}` : ''
              }${semanticEnabled === false ? ' · exact-match only on this backend' : ''}`}
              why={WHY.hitRate}
              tone="green"
              highlight={hl('cache')}
            />
            <Tile
              label="Spent vs avoided"
              value={`${fmtCost(stats.spentUsd)} spent`}
              sub={
                stats.avoidedUnknown
                  ? `avoided n/a for ${stats.avoidedUnknown} hit${stats.avoidedUnknown === 1 ? '' : 's'} (backend predates cost_avoided_usd)`
                  : `${fmtCost(stats.avoidedUsd)} avoided${stats.spentUnknown ? ` · ${stats.spentUnknown} unpriced` : ''}`
              }
              why={WHY.cost}
              tone={stats.avoidedUsd > 0 ? 'green' : 'neutral'}
              highlight={hl('cost')}
            />
            <Tile
              label="Latency p50 / p95"
              value={`${fmtMs(stats.latency.p50)} / ${fmtMs(stats.latency.p95)}`}
              sub={`client-observed, n=${stats.latency.n}`}
              why={WHY.latency}
              tone="blue"
              highlight={hl('latency')}
            />
            <Tile
              label="TTFB on misses"
              value={fmtMs(stats.ttfbStreamedMiss.p50)}
              sub={stats.ttfbStreamedMiss.n ? `median of ${stats.ttfbStreamedMiss.n} streamed miss${stats.ttfbStreamedMiss.n === 1 ? '' : 'es'}` : 'no streamed misses yet'}
              why={WHY.ttfb}
              tone="purple"
              highlight={hl('latency')}
            />
            <Tile
              label="Failovers"
              value={String(stats.failovers.length)}
              sub={stats.failovers.some((f) => f.simulated) ? 'includes simulated outages' : stats.failovers.length ? 'real upstream failures' : 'none this session'}
              why={WHY.failover}
              tone={stats.failovers.length ? 'amber' : 'neutral'}
              highlight={hl('failover')}
            />
            <Tile
              label="Answered"
              value={String(stats.answered)}
              sub={stats.errors ? `${stats.errors} failed request${stats.errors === 1 ? '' : 's'}` : 'no failed requests'}
              why="How many assistant answers carried telemetry. Failed requests are counted separately and appear red on the timeline."
            />
          </div>
          <Sparkline points={stats.points} highlight={hl('latency')} />
          <ProviderBar providers={stats.providers} />
          <FailoverTimeline events={stats.failovers} highlight={hl('failover')} />
        </>
      )}

      <p className="mt-auto pt-2 text-[11px] text-muted-foreground">
        Offline precision/recall for the cache, failover and SSE contract:{' '}
        <Link href="/evals" className="underline underline-offset-2 hover:text-foreground">
          /evals
        </Link>
        .
      </p>
    </div>
  );
}

function EmptyState({ onStartDemo }: { onStartDemo: () => void }) {
  return (
    <div className="rounded-xl border border-dashed border-border p-4 text-xs text-muted-foreground">
      <p className="mb-2 font-medium text-foreground">Nothing measured yet.</p>
      <p className="mb-2">
        Send a message and this panel fills in from the telemetry on each answer: cache hit rate, money spent versus
        avoided, client-observed latency, time to first token, and every provider failover with its attempt chain.
      </p>
      <p className="mb-3">
        The fastest way to see all three ideas is the guided demo: one question, a paraphrase that hits the semantic
        cache, and a simulated outage that fails over.
      </p>
      <button
        type="button"
        onClick={onStartDemo}
        className="rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        Open the guided demo
      </button>
    </div>
  );
}
