'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { API_CONFIG } from '@/lib/config';
import { fetchWithTimeout } from '@/lib/sse';
import staticArtifactJson from '@/lib/evals/latest.json';
import { chooseArtifact, parseArtifact } from './artifact';
import { CacheEvalSection } from './CacheEvalSection';
import { FailoverSection, SseSection } from './FailoverSseSection';
import { LatencySection } from './LatencyTable';
import { RunMetaCard } from './RunMetaCard';
import type { ArtifactSource, EvalArtifact } from './types';

/** Build-time copy written by `python -m evals.run`; the page works from this alone while the backend sleeps. */
const STATIC_ARTIFACT = staticArtifactJson as unknown as EvalArtifact;
const LIVE_TIMEOUT_MS = 8_000;

type LiveState = 'checking' | 'live' | 'unreachable' | 'older';

export function EvalsView() {
  const [artifact, setArtifact] = useState<EvalArtifact>(STATIC_ARTIFACT);
  const [source, setSource] = useState<ArtifactSource>('static');
  const [liveState, setLiveState] = useState<LiveState>('checking');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetchWithTimeout(`${API_CONFIG.baseURL}/evals/latest`, { headers: { Accept: 'application/json' } }, LIVE_TIMEOUT_MS);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const live = parseArtifact(await res.json());
        if (cancelled) return;
        const chosen = chooseArtifact(STATIC_ARTIFACT, live);
        setArtifact(chosen.artifact);
        setSource(chosen.source);
        setLiveState(chosen.source === 'live' ? 'live' : live ? 'older' : 'unreachable');
      } catch {
        if (!cancelled) setLiveState('unreachable');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-5">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">System evals</h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
          Scripted evaluations run against a live backend and committed to the repository. Every number on this page is from the last run;
          nothing is typed in by hand. The <Link href="/" className="underline underline-offset-2 hover:text-foreground">chat page</Link> shows the
          same telemetry per message as it happens.
        </p>
      </header>
      <RunMetaCard artifact={artifact} source={source} liveState={liveState} />
      <CacheEvalSection evalResult={artifact.cache_paraphrase} />
      <FailoverSection evalResult={artifact.failover} />
      <SseSection evalResult={artifact.sse_contract} />
      <LatencySection evalResult={artifact.latency} />
      <footer className="space-y-1 text-xs text-muted-foreground">
        <p>
          Method and code: <code className="rounded bg-muted px-1">evals/</code> in the repository, summarised in{' '}
          <code className="rounded bg-muted px-1">evals/results/latest.md</code>. Design decision: ADR 0006, system evals as committed artifacts.
        </p>
        <p>
          The backend also exposes Prometheus counters at <code className="rounded bg-muted px-1">/metrics</code>. They are per worker and reset on every
          deploy and free-tier sleep, like the in-process cache, so they describe the current process only; the evals above are the durable record.
        </p>
      </footer>
    </div>
  );
}
