import Link from 'next/link';
import artifact from '@/lib/evals/latest.json';
import { fmtDate, fmtRatio } from '@/components/evals/artifact';

const REPO = 'https://github.com/cbratkovics/chatbot-ai-system';
const features = [
  ['Provider failover', 'A provider chain records each attempt and tries configured fallbacks on authentication, quota, rate-limit, server and timeout errors.', 'src/chatbot_ai_system/providers/chain.py'],
  ['Streaming & errors', 'Server-Sent Events carry metadata, content deltas and a terminal event. Structured errors keep status codes and request IDs inspectable.', 'src/chatbot_ai_system/api/chat.py'],
  ['Optional caching', 'An exact-match cache runs in memory when Redis is absent. Optional embedding similarity adds paraphrase reuse, with correctness tradeoffs exposed below.', 'src/chatbot_ai_system/cache/semantic_match.py'],
  ['Request guardrails', 'Per-IP request limits, output caps and an in-process daily token budget bound local demo usage. Telemetry describes each request.', 'src/chatbot_ai_system/api/guardrails.py'],
];
const linkClass = 'inline-flex items-center justify-center rounded-lg border border-border px-4 py-2.5 text-sm font-medium hover:bg-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ring';

export default function Home() {
  return (
    <div className="space-y-10 py-5 sm:py-10">
      <section aria-labelledby="overview-title" className="relative overflow-hidden rounded-2xl border border-border bg-card p-6 sm:p-10">
        <div aria-hidden="true" className="pointer-events-none absolute -right-24 -top-28 h-80 w-80 rounded-full bg-blue-500/10 blur-3xl" />
        <p className="text-xs font-medium uppercase tracking-widest text-blue-300">Static project demo</p>
        <h1 id="overview-title" className="mt-4 max-w-3xl text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">An LLM gateway you can inspect.</h1>
        <p className="mt-5 max-w-2xl text-base leading-relaxed text-muted-foreground">
          A FastAPI / Next.js reference implementation for provider failover, SSE streaming,
          caching and request guardrails. Explore the source and recorded evaluation results.
          Live model generation is not hosted.
        </p>
        <div className="mt-7 flex flex-wrap gap-3">
          <Link href="/evals/" className={`${linkClass} border-blue-500/50 bg-blue-500/15 text-blue-200`}>Explore recorded evaluations →</Link>
          <a href={REPO} className={linkClass}>View source on GitHub ↗</a>
        </div>
        <p className="mt-6 text-xs leading-relaxed text-muted-foreground">Static files only · No model calls · No backend or database required</p>
      </section>

      <section aria-labelledby="implementation-title">
        <h2 id="implementation-title" className="text-2xl font-semibold tracking-tight">The implementation</h2>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">The gateway remains available as source and an optional local application. These capabilities are implemented in Python; this public site presents their design and evidence.</p>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          {features.map(([title, description, path]) => (
            <article key={title} className="rounded-xl border border-border bg-card/60 p-5">
              <h3 className="text-base font-semibold"><a href={`${REPO}/blob/main/${path}`} className="underline decoration-border underline-offset-4 hover:text-blue-300">{title} ↗</a></h3>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{description}</p>
            </article>
          ))}
        </div>
      </section>

      <section aria-labelledby="evidence-title" className="rounded-2xl border border-border p-6 sm:p-8">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="evidence-title" className="text-2xl font-semibold tracking-tight">Evidence, including the limitations</h2>
          <span className="text-xs text-muted-foreground">Recorded {fmtDate(artifact.run.timestamp)}</span>
        </div>
        <div className="mt-5 grid gap-5 md:grid-cols-3">
          <div><p className="text-3xl font-semibold tabular-nums text-amber-300">{fmtRatio(artifact.cache_paraphrase.precision)}</p><h3 className="mt-1 text-sm font-medium">Semantic-cache precision</h3><p className="mt-2 text-sm leading-relaxed text-muted-foreground">{artifact.cache_paraphrase.fp} false positives across {artifact.cache_paraphrase.n_pairs} labelled pairs. This adversarial result exposes wrong-answer reuse; it does not establish dependable semantic accuracy.</p></div>
          <div><p className="text-3xl font-semibold tabular-nums">{artifact.failover.passed}/{artifact.failover.n}</p><h3 className="mt-1 text-sm font-medium">Failover checks passed</h3><p className="mt-2 text-sm leading-relaxed text-muted-foreground">A simulated primary outage with real fallback calls in one historical run. A small sample of control flow, not an availability guarantee.</p></div>
          <div><p className="text-3xl font-semibold tabular-nums">{artifact.sse_contract.passed}/{artifact.sse_contract.n}</p><h3 className="mt-1 text-sm font-medium">Streaming contracts passed</h3><p className="mt-2 text-sm leading-relaxed text-muted-foreground">Recorded event-order and metadata checks across cache, miss and failover paths. Localhost timings on the eval page are not current hosted latency.</p></div>
        </div>
        <p className="mt-6 text-sm leading-relaxed text-muted-foreground">The evaluation page preserves the run target, commit with uncommitted changes, sample counts and historical provider cost estimates. Offline tests use test doubles separately; no new benchmark or synthetic transcript is presented here.</p>
        <Link href="/evals/" className="mt-4 inline-block text-sm text-blue-300 underline underline-offset-4">Read the full run and threshold-sweep caveats →</Link>
      </section>

      <section aria-labelledby="design-title" className="grid gap-6 md:grid-cols-2">
        <div>
          <h2 id="design-title" className="text-xl font-semibold">Follow the design decisions</h2>
          <ul className="mt-3 space-y-3 text-sm text-blue-300">
            <li><a className="underline underline-offset-4" href={`${REPO}/blob/main/docs/adr/README.md`}>Architecture decision records ↗</a></li>
            <li><a className="underline underline-offset-4" href={`${REPO}/blob/main/docs/architecture/ARCHITECTURE.md`}>Gateway architecture and request flow ↗</a></li>
            <li><a className="underline underline-offset-4" href={`${REPO}/blob/main/evals/results/latest.md`}>Original evaluation report ↗</a></li>
          </ul>
        </div>
        <div className="rounded-xl border border-border bg-card/60 p-5">
          <h2 className="text-lg font-semibold">Run the gateway locally, optionally</h2>
          <p className="mt-2 text-sm leading-relaxed text-muted-foreground">The API boots without Redis or a database. Generating new answers or embeddings requires your own provider configuration and may incur provider charges. Credentials stay on the backend.</p>
          <a className="mt-3 inline-block text-sm text-blue-300 underline underline-offset-4" href={`${REPO}/blob/main/docs/LOCAL_DEVELOPMENT.md`}>Local setup and original chat UI reference ↗</a>
        </div>
      </section>
      <footer className="border-t border-border pt-5 text-xs leading-relaxed text-muted-foreground">Public demo runtime: static HTML, CSS and JavaScript. Eligible free static hosting can serve it for $0; historical evaluation costs belong to the recorded run. No analytics or live provider integration is included.</footer>
    </div>
  );
}
