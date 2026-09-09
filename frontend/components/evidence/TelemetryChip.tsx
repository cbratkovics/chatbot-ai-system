'use client';

import { cn } from '@/lib/utils';
import { fmtCost, fmtSimilarity } from './format';
import type { HighlightKey, Telemetry } from './types';

const PILL = 'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] leading-4 whitespace-nowrap';
const NEUTRAL = `${PILL} border-border bg-background/60 text-muted-foreground`;
const HL = 'ring-2 ring-amber-400 motion-safe:animate-pulse';

function cacheLabel(t: Telemetry): { text: string; title: string; tone: string } {
  const c = t.cache ?? {};
  const backend = c.backend ?? '?';
  if (c.status === 'hit') {
    const semantic = c.match === 'semantic';
    const sim = typeof c.similarity === 'number' ? fmtSimilarity(c.similarity) : null;
    return {
      text: `cache HIT${semantic ? ' · semantic' : ''}${sim ? ` ${sim}` : ''}`,
      title: `${semantic ? 'Semantic (paraphrase) hit' : 'Exact-key hit'} · backend ${backend}${
        sim ? ` · similarity ${sim}` : ''
      }${typeof c.threshold === 'number' ? ` · threshold ${fmtSimilarity(c.threshold)}` : ''}${
        typeof c.age_seconds === 'number' ? ` · cached ${Math.round(c.age_seconds)} s ago` : ''
      }`,
      tone: 'border-green-500/40 bg-green-500/10 text-green-300',
    };
  }
  const status = (c.status ?? 'miss').toUpperCase();
  const nearest = typeof c.similarity === 'number' ? ` · nearest cached prompt ${fmtSimilarity(c.similarity)}` : '';
  return {
    text: `cache ${status}`,
    title: `Cache ${status.toLowerCase()} · backend ${backend}${nearest}${
      c.semantic === 'unavailable' ? ' · semantic lookup unavailable, exact-match only' : ''
    }`,
    tone: 'border-purple-500/40 bg-purple-500/10 text-purple-300',
  };
}

/** The per-message evidence: provider, model, cache, latency, tokens, cost, failover. */
export function TelemetryChip({ t, highlight = null }: { t: Telemetry; highlight?: HighlightKey | null }) {
  const cache = cacheLabel(t);
  const failed = (t.attempts ?? []).filter((a) => a.outcome === 'failed');
  const usage = t.usage ?? {};
  const est = usage.source === 'estimated' ? '~' : '';
  const avoided = typeof t.cost_avoided_usd === 'number' && t.cost_avoided_usd > 0 ? t.cost_avoided_usd : null;
  const ttfb = typeof t.ttfb_ms === 'number' ? t.ttfb_ms : null;

  return (
    <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Response telemetry">
      <li
        className={`${PILL} border-blue-500/40 bg-blue-500/10 text-blue-300`}
        title="Provider slot and model that answered"
        aria-label={`Answered by ${t.provider ?? 'unknown provider'}, model ${t.model ?? 'unknown'}`}
      >
        {t.provider ?? '?'} · {t.model ?? '?'}
      </li>
      <li
        className={cn(PILL, cache.tone, highlight === 'cache' && HL)}
        title={cache.title}
        aria-label={cache.title}
      >
        {cache.text}
      </li>
      <li
        className={cn(NEUTRAL, highlight === 'latency' && HL)}
        title={ttfb !== null ? `Server latency; time to first token ${Math.round(ttfb)} ms` : 'Server-side latency'}
        aria-label={`Server latency ${Math.round(t.latency_ms ?? 0)} milliseconds${
          ttfb !== null ? `, first token at ${Math.round(ttfb)} milliseconds` : ''
        }`}
      >
        {Math.round(t.latency_ms ?? 0)} ms{ttfb !== null ? ` · ttfb ${Math.round(ttfb)}` : ''}
      </li>
      <li
        className={NEUTRAL}
        title={
          usage.source === 'estimated'
            ? 'Token counts estimated locally (provider did not report usage)'
            : 'Token counts reported by the provider'
        }
        aria-label={`${est ? 'Estimated ' : ''}${usage.prompt_tokens ?? 0} prompt tokens, ${usage.completion_tokens ?? 0} completion tokens`}
      >
        {est}
        {usage.prompt_tokens ?? 0} in / {est}
        {usage.completion_tokens ?? 0} out
      </li>
      <li
        className={cn(NEUTRAL, highlight === 'cost' && HL, avoided !== null && 'border-green-500/40 text-green-300')}
        title={
          avoided !== null
            ? `Paid ${fmtCost(t.cost_usd)} (embedding lookup only); avoided ${fmtCost(avoided)} of provider cost at list price`
            : 'Estimated from list prices'
        }
        aria-label={`Cost ${fmtCost(t.cost_usd)}${avoided !== null ? `, avoided ${fmtCost(avoided)}` : ''}`}
      >
        {fmtCost(t.cost_usd)}
        {avoided !== null ? ` · saved ${fmtCost(avoided)}` : ''}
      </li>
      {t.streamed && (
        <li className={NEUTRAL} title="Delivered as Server-Sent Events" aria-label="Streamed">
          streamed
        </li>
      )}
      {t.cache?.semantic === 'unavailable' && (
        <li
          className={`${PILL} border-amber-500/50 bg-amber-500/10 text-amber-300`}
          title="The embedding lookup failed or timed out; this request used exact-match only"
          aria-label="Semantic lookup unavailable, exact-match only"
        >
          semantic n/a
        </li>
      )}
      {t.failover && (
        <li
          className={cn(PILL, 'border-amber-500/50 bg-amber-500/10 text-amber-300', highlight === 'failover' && HL)}
          title={failed.map((a) => `${a.provider}/${a.model}: ${a.status_code ?? ''} ${a.error_code ?? ''}`).join('\n')}
          aria-label={`Failover: ${failed.map((a) => a.provider).join(', ')} failed, ${t.provider ?? 'fallback'} answered${
            t.simulated_failure ? ', simulated outage' : ''
          }`}
        >
          failover: {failed.map((a) => a.provider).join(', ')} → {t.provider}
          {t.simulated_failure ? ' (simulated)' : ''}
        </li>
      )}
    </ul>
  );
}
