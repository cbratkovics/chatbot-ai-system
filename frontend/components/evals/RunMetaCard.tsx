'use client';

import { fmtDate } from './artifact';
import type { ArtifactSource, EvalArtifact } from './types';

type Props = { artifact: EvalArtifact; source: ArtifactSource; liveState: 'checking' | 'live' | 'unreachable' | 'older' };

const SOURCE_TEXT: Record<Props['liveState'], string> = {
  checking: 'showing the copy committed at build time; checking the live API…',
  live: 'served live by the backend, and identical to or newer than the committed copy',
  unreachable: 'showing the copy committed at build time; the backend did not answer (it may be asleep)',
  older: 'showing the copy committed at build time, which is newer than what the backend serves',
};

/** Timestamp, commit, size and environment of the run every number on this page comes from. */
export function RunMetaCard({ artifact, source, liveState }: Props) {
  const { run, cost } = artifact;
  const env = run.environment ?? {};
  const semantic = env.semantic_cache ?? {};
  return (
    <section aria-labelledby="run-meta-title" className="rounded-2xl border border-border bg-card/60 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="run-meta-title" className="text-base font-semibold">
          Last benchmark run
        </h2>
        <span
          className={`rounded-full border px-2.5 py-0.5 text-xs ${source === 'live' ? 'border-green-500/40 bg-green-500/10 text-green-300' : 'border-border bg-background/60 text-muted-foreground'}`}
          role="status"
        >
          source: {source === 'live' ? 'live API' : 'committed artifact'}
        </span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">{SOURCE_TEXT[liveState]}</p>
      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3 lg:grid-cols-4">
        <Item label="Run timestamp" value={fmtDate(run.timestamp)} />
        <Item label="Commit" value={`${run.commit ?? 'unknown'}${run.commit_dirty ? ' (uncommitted changes)' : ''}`} mono />
        <Item label="Requests" value={`${run.requests ?? 'n/a'} in ${run.duration_s ?? 'n/a'} s${run.failed_requests ? `, ${run.failed_requests} failed` : ''}`} />
        <Item label="Target" value={run.base_url} mono />
        <Item label="Cache backend" value={env.cache ?? 'n/a'} />
        <Item label="Semantic matching" value={semantic.enabled ? `${semantic.backend ?? 'on'} · ${semantic.embedding_model ?? ''} · threshold ${semantic.threshold ?? 'n/a'}` : 'off'} />
        <Item label="Providers" value={`${env.default_model ?? 'n/a'} → ${(env.fallback_chain ?? []).join(' → ') || 'no fallback'}`} mono />
        <Item label="Cost of this run" value={cost ? `$${cost.estimated_usd_spent ?? 'n/a'} spent · $${cost.avoided_usd ?? 'n/a'} avoided` : 'n/a'} />
      </dl>
      <p className="mt-3 text-xs text-muted-foreground">
        Regenerate with <code className="rounded bg-muted px-1">make evals</code> against a local backend. The artifact lives at{' '}
        <code className="rounded bg-muted px-1">evals/results/latest.json</code>; this page also embeds a copy at build time so it works while the backend sleeps.
      </p>
    </section>
  );
}

function Item({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className={`mt-0.5 break-words ${mono ? 'font-mono text-xs' : ''}`}>{value}</dd>
    </div>
  );
}
