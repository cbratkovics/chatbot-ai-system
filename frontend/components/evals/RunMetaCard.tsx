import { fmtDate } from './artifact';
import type { ArtifactSource, EvalArtifact } from './types';

type Props = { artifact: EvalArtifact; source: ArtifactSource };

/** Timestamp, commit, size and environment of the run every number on this page comes from. */
export function RunMetaCard({ artifact, source }: Props) {
  const { run, cost } = artifact;
  const env = run.environment ?? {};
  const semantic = env.semantic_cache ?? {};
  return (
    <section aria-labelledby="run-meta-title" className="rounded-2xl border border-border bg-card/60 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="run-meta-title" className="text-base font-semibold">
          Recorded benchmark run
        </h2>
        <span
          className="rounded-full border border-border bg-background/60 px-2.5 py-0.5 text-xs text-muted-foreground"
          data-source={source}
        >
          source: committed artifact
        </span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">Embedded at build time. No live backend is contacted.</p>
      <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3 lg:grid-cols-4">
        <Item label="Run timestamp" value={fmtDate(run.timestamp)} />
        <Item label="Commit" value={`${run.commit ?? 'unknown'}${run.commit_dirty ? ' (dirty tree / uncommitted changes)' : ''}`} mono />
        <Item label="Requests" value={`${run.requests ?? 'n/a'} in ${run.duration_s ?? 'n/a'} s, ${run.failed_requests ?? 'n/a'} failed`} />
        <Item label="Target" value={run.base_url} mono />
        <Item label="Cache backend" value={env.cache ?? 'n/a'} />
        <Item label="Semantic matching" value={semantic.enabled ? `${semantic.backend ?? 'on'} · ${semantic.embedding_model ?? ''} · threshold ${semantic.threshold ?? 'n/a'}` : 'off'} />
        <Item label="Providers" value={`${env.default_model ?? 'n/a'} → ${(env.fallback_chain ?? []).join(' → ') || 'no fallback'}`} mono />
        <Item label="Historical estimated cost" value={cost ? `$${cost.estimated_usd_spent ?? 'n/a'} spent · $${cost.avoided_usd ?? 'n/a'} avoided` : 'n/a'} />
        <Item label="Python" value={run.python ?? 'n/a'} />
        <Item label="Guardrails during run" value={env.guardrails_enabled === undefined ? 'n/a' : env.guardrails_enabled ? 'on' : 'off'} />
        <Item label="Streaming transport" value={env.streaming ?? 'n/a'} />
      </dl>
      <details className="mt-3 text-xs text-muted-foreground">
        <summary className="cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring">Full recorded run metadata</summary>
        <pre className="mt-2 max-w-full overflow-x-auto rounded-lg bg-background p-3">{JSON.stringify(run, null, 2)}</pre>
      </details>
      {cost?.note && <p className="mt-3 text-xs text-muted-foreground">{cost.note}</p>}
      <p className="mt-3 text-xs text-muted-foreground">
        Original artifact: <code className="rounded bg-muted px-1">evals/results/latest.json</code>; the unchanged public copy is
        embedded from <code className="rounded bg-muted px-1">frontend/lib/evals/latest.json</code>.
        Provider costs are historical list-price estimates, not current demo hosting costs. Optional local regeneration with
        <code className="rounded bg-muted px-1">make evals</code> may incur provider charges.
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
