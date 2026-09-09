'use client';

import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { fmtCost, fmtMs, fmtSimilarity } from './format';
import type { ChatMsg, HighlightKey, Telemetry } from './types';

export type RunOptions = { simulate?: boolean; standalone?: boolean; bypassCache?: boolean };
export type RunFn = (text: string, opts?: RunOptions) => Promise<ChatMsg | undefined>;

type Props = {
  open: boolean;
  onClose: () => void;
  run: RunFn;
  busy: boolean;
  backendReady: boolean;
  toggleAvailable: boolean;
  /** From /chat/health; null while unknown. Only used to explain a MISS honestly. */
  semanticEnabled: boolean | null;
  onHighlight: (key: HighlightKey) => void;
};

type StepStatus = 'idle' | 'running' | 'done' | 'skipped';
type StepState = { status: StepStatus; result?: string };

/** Q1 stays fixed so the index holds it; the paraphrase is drawn at random so a visitor to a warm,
 *  shared cache sees a semantic match rather than an exact repeat of the previous visitor's wording.
 *  The first pair scored 0.96 cosine on the live backend in the Phase 1 smoke test. */
const Q1 = 'What is the difference between P50 and P95 latency?';
const PARAPHRASES = [
  'How do P50 and P95 latency differ?',
  'Explain how P95 latency differs from P50 latency.',
  'What distinguishes P50 latency from P95 latency?',
  'P50 versus P95 latency: what is the difference between them?',
];
const Q3 = 'Name three failure modes of an LLM provider call.';
const pickParaphrase = () => PARAPHRASES[Math.floor(Math.random() * PARAPHRASES.length)];

const STEPS = (q2: string) => [
  {
    title: 'Ask a question',
    detail: `Sends “${Q1}”. Watch the answer stream and the chip under it: provider, cache MISS, latency, tokens, cost.`,
  },
  {
    title: 'Ask it differently',
    detail: `Sends “${q2}”. A paraphrase, not a repeat. If the semantic cache matches it, the chip shows HIT with the similarity score and the provider cost avoided.`,
  },
  {
    title: 'Break the primary provider',
    detail: `Sends “${Q3}” with the “Simulate provider failure” header and Cache-Control: no-cache, so the provider chain runs even if the answer is cached. The primary fails with a 503 and the fallback answers; the attempt chain appears in the Evidence rail.`,
  },
];

/** Every step is sent standalone (no conversation history): the cache key covers the whole prompt,
 *  so a paraphrase can only match the first question if both are asked without prior turns. */
const STANDALONE_NOTE = 'Each step is a standalone request without conversation history, marked on the message. Turn “Conversation memory” off to reproduce by hand.';

function describeFirst(t?: Telemetry): string {
  if (!t) return 'The request failed; see the banner above.';
  const status = t.cache?.status ?? 'miss';
  if (status === 'hit') {
    return `Cache HIT already: someone asked exactly this on this backend earlier (the cache is shared across visitors, ${
      typeof t.cache?.age_seconds === 'number' ? `cached ${Math.round(t.cache.age_seconds)} s ago` : 'still within its TTL'
    }). Step 2 still tests the paraphrase path.`;
  }
  return `Answered by ${t.provider ?? '?'} · ${t.model ?? '?'}: cache MISS, ${fmtMs(t.latency_ms)} server time${
    typeof t.ttfb_ms === 'number' ? `, first token at ${fmtMs(t.ttfb_ms)}` : ''
  }, ${fmtCost(t.cost_usd)} at list price. The answer is now cached under its exact key and, when semantic matching is on, its embedding is indexed.`;
}

function describeParaphrase(t: Telemetry | undefined, semanticEnabled: boolean | null): string {
  if (!t) return 'The request failed; see the banner above.';
  const c = t.cache ?? {};
  if (c.status === 'hit' && c.match === 'semantic') {
    return `Cache HIT by semantic match: similarity ${fmtSimilarity(c.similarity)} against threshold ${fmtSimilarity(c.threshold)}. No provider call. Avoided ${fmtCost(
      t.cost_avoided_usd,
    )} of provider cost; paid ${fmtCost(t.cost_usd)} for the embedding lookup. Server time ${fmtMs(t.latency_ms)}.`;
  }
  if (c.status === 'hit') {
    return `Cache HIT by exact key: the normalised text matched a cached prompt character for character. ${
      typeof t.cost_avoided_usd === 'number' ? `Avoided ${fmtCost(t.cost_avoided_usd)}.` : ''
    }`;
  }
  if (c.semantic === 'unavailable') {
    return 'Cache MISS: the embedding lookup was unavailable (timeout, quota or no key), so the backend fell back to exact-match and called the provider. That degradation is the designed behaviour, and the chip says “semantic n/a”.';
  }
  if (semanticEnabled === false || c.semantic === 'disabled') {
    return 'Cache MISS: this backend has semantic matching disabled (health.semantic_cache.enabled = false), so a paraphrase can only hit on an exact key. The provider answered.';
  }
  if (typeof c.similarity === 'number') {
    return `Cache MISS: the nearest cached prompt scored ${fmtSimilarity(c.similarity)}, below the threshold ${fmtSimilarity(
      c.threshold,
    )}, so the provider answered. The threshold is set from the offline eval, not by hand.`;
  }
  return `Cache MISS: nothing comparable was in this worker’s index, so ${t.provider ?? 'the provider'} answered.`;
}

function describeFailover(t?: Telemetry): string {
  if (!t) return 'The request failed; see the banner above.';
  if (!t.failover) {
    return `No failover happened: ${t.provider ?? '?'} answered directly${t.cache?.status === 'hit' ? ' from cache' : ''}. The simulate header only affects provider calls; check that the backend exposes the failure toggle.`;
  }
  const chain = (t.attempts ?? [])
    .map((a) => (a.outcome === 'ok' ? `${a.provider} ok` : `${a.provider} ${a.status_code ?? ''} ${a.error_code ?? a.outcome}`))
    .join(' → ');
  return `Failover recorded${t.simulated_failure ? ' (simulated outage)' : ''}: ${chain}. The fallback ${t.provider ?? '?'} · ${
    t.model ?? '?'
  } answered in ${fmtMs(t.latency_ms)} server time. Only the outage is simulated; the failover code path is the one that runs on a real 429 or 5xx.`;
}

export function GuidedDemo({ open, onClose, run, busy, backendReady, toggleAvailable, semanticEnabled, onHighlight }: Props) {
  const [q2, setQ2] = useState(PARAPHRASES[0]);
  const [steps, setSteps] = useState<StepState[]>(() => Array.from({ length: 3 }, (): StepState => ({ status: 'idle' })));
  const [runningAll, setRunningAll] = useState(false);
  const definitions = STEPS(q2);
  const panelRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (open) {
      panelRef.current?.focus();
      setQ2(pickParaphrase());
    }
  }, [open]);

  if (!open) return null;

  const setStep = (i: number, state: StepState) =>
    setSteps((prev) => prev.map((s, j) => (j === i ? state : s)));

  async function runStep(i: number): Promise<void> {
    if (busy) return;
    if (i === 2 && !toggleAvailable) {
      setStep(2, { status: 'skipped', result: 'This backend does not expose the failure toggle (DEMO_FAILURE_TOGGLE_ENABLED is off), so the outage cannot be simulated here.' });
      return;
    }
    setStep(i, { status: 'running' });
    const prompt = [Q1, q2, Q3][i];
    const msg = await run(prompt, { standalone: true, simulate: i === 2, bypassCache: i === 2 });
    const t = msg?.telemetry;
    if (i === 0) {
      setStep(0, { status: 'done', result: describeFirst(t) });
      onHighlight('latency');
    } else if (i === 1) {
      setStep(1, { status: 'done', result: describeParaphrase(t, semanticEnabled) });
      onHighlight(t?.cache?.status === 'hit' ? 'cache' : 'latency');
      if (t?.cache?.status === 'hit') setTimeout(() => onHighlight('cost'), 1600);
    } else {
      setStep(2, { status: 'done', result: describeFailover(t) });
      onHighlight('failover');
    }
  }

  async function runAll(): Promise<void> {
    setRunningAll(true);
    try {
      for (let i = 0; i < definitions.length; i += 1) {
        await runStep(i);
      }
    } finally {
      setRunningAll(false);
    }
  }

  const disabled = busy || runningAll || !backendReady;

  return (
    <section
      ref={panelRef}
      tabIndex={-1}
      role="region"
      aria-labelledby="guided-demo-title"
      onKeyDown={(e) => {
        if (e.key === 'Escape') onClose();
      }}
      className="border-b border-border bg-card/40 px-4 py-3 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <div className="mb-2 flex items-center justify-between">
        <h2 id="guided-demo-title" className="text-sm font-semibold">
          Guided demo · three real requests
        </h2>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={runAll}
            disabled={disabled}
            className="rounded-md bg-primary px-2.5 py-1 font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Run all
          </button>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close guided demo"
            className="rounded-md border border-border px-2 py-1 text-muted-foreground hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            Close
          </button>
        </div>
      </div>
      <p className="mb-2 text-muted-foreground">{STANDALONE_NOTE}</p>
      {!backendReady && <p className="mb-2 text-amber-300">Waiting for the backend to be reachable before running steps.</p>}
      <ol className="space-y-2">
        {definitions.map((step, i) => {
          const state = steps[i];
          return (
            <li key={step.title} className="rounded-lg border border-border bg-background/60 p-2.5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-medium text-foreground">
                    {i + 1}. {step.title}
                    <span
                      className={cn(
                        'ml-2 rounded-full border px-1.5 py-0.5 text-[10px] uppercase tracking-wide',
                        state.status === 'done' && 'border-green-500/40 text-green-300',
                        state.status === 'running' && 'border-blue-500/40 text-blue-300',
                        state.status === 'skipped' && 'border-amber-500/40 text-amber-300',
                        state.status === 'idle' && 'border-border text-muted-foreground',
                      )}
                    >
                      {state.status}
                    </span>
                  </div>
                  <p className="mt-0.5 text-muted-foreground">{step.detail}</p>
                </div>
                <button
                  type="button"
                  onClick={() => runStep(i)}
                  disabled={disabled}
                  className="shrink-0 rounded-md border border-border px-2 py-1 font-medium hover:bg-accent disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {state.status === 'running' ? 'Running…' : state.status === 'done' ? 'Run again' : 'Run'}
                </button>
              </div>
              {state.result && (
                <p role="status" aria-live="polite" className="mt-2 rounded-md border border-border/60 bg-card/60 p-2 text-foreground">
                  {state.result}
                </p>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
