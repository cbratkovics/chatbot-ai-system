import Link from 'next/link';
import staticArtifactJson from '@/lib/evals/latest.json';
import { CacheEvalSection } from './CacheEvalSection';
import { FailoverSection, SseSection } from './FailoverSseSection';
import { LatencySection } from './LatencyTable';
import { RunMetaCard } from './RunMetaCard';
import type { EvalArtifact } from './types';

// Deliberately static: no API probe, live mode or fallback transport.
const ARTIFACT = staticArtifactJson as unknown as EvalArtifact;
const REPO = 'https://github.com/cbratkovics/chatbot-ai-system';

export function EvalsView() {
  return (
    <div className="space-y-5 py-5">
      <header>
        <p className="text-xs font-medium uppercase tracking-widest text-blue-300">Historical evidence</p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Recorded system evaluations</h1>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">
          Results from the committed benchmark artifact, embedded in this static site. The run made real provider requests against a local backend;
          viewing this page makes none. These are historical observations, not current hosted performance.
          Return to the <Link href="/" className="underline underline-offset-2 hover:text-foreground">project overview</Link> for the implementation.
        </p>
      </header>
      <RunMetaCard artifact={ARTIFACT} source="committed" />
      <CacheEvalSection evalResult={ARTIFACT.cache_paraphrase} />
      <FailoverSection evalResult={ARTIFACT.failover} />
      <SseSection evalResult={ARTIFACT.sse_contract} />
      <LatencySection evalResult={ARTIFACT.latency} />
      <footer className="space-y-2 text-xs leading-relaxed text-muted-foreground">
        <p>Method and original report: <a href={`${REPO}/tree/main/evals`} className="underline">evals/</a> and{' '}
          <a href={`${REPO}/blob/main/evals/results/latest.md`} className="underline">evals/results/latest.md</a>.{' '}
          <a href={`${REPO}/blob/main/docs/adr/0008-static-public-evidence.md`} className="underline">ADR 0008</a> documents the static public experience.</p>
        <p>Offline unit and contract tests use mocked providers separately; their results are not these live-provider measurements.
          Republishing this historical run requires no monthly rerun, backend, model key or embedding call.</p>
      </footer>
    </div>
  );
}
