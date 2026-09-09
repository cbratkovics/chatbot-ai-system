'use client';

import { Tile } from '@/components/evidence/Tile';
import { fmtRatio, fmtScore, pathFrom, sweepPoints } from './artifact';
import { Explainer, Section, Skipped, tableClasses } from './Explainer';
import type { CacheEval, SweepRow } from './types';

const { TABLE, TH, TD } = tableClasses;
const OUTCOME: Record<string, string> = {
  true_positive: 'border-green-500/40 bg-green-500/10 text-green-300',
  true_negative: 'border-blue-500/40 bg-blue-500/10 text-blue-300',
  false_positive: 'border-red-500/40 bg-red-500/10 text-red-300',
  false_negative: 'border-amber-500/40 bg-amber-500/10 text-amber-300',
};

export function CacheEvalSection({ evalResult: c }: { evalResult?: CacheEval }) {
  return (
    <Section id="cache" title="Semantic cache: precision and recall">
      <Explainer>
        Each labelled pair has one question already cached and a second question that either should reuse that answer (a paraphrase) or must not
        (a different ask that shares the words, a negation, or a swapped name or number). Precision is how often a cache hit returned the right
        answer; recall is how many true paraphrases were caught. The threshold is the similarity the cache demands before trusting a match, and
        it was set where F1 peaked in the sweep below, not by hand.
      </Explainer>
      {!c || c.status !== 'ok' ? (
        <Skipped reason={c?.reason} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
            <Tile label="Precision" value={fmtRatio(c.precision)} sub={`${c.tp} right hits of ${(c.tp ?? 0) + (c.fp ?? 0)} hits`} why="Of every time the cache served a stored answer, how often was it the answer to the question actually asked. A wrong hit is worse than a miss." tone="green" />
            <Tile label="Recall" value={fmtRatio(c.recall)} sub={`${c.tp} of ${(c.tp ?? 0) + (c.fn ?? 0)} paraphrases caught`} why="Of every question that had a usable cached answer, how often the cache found it. Missed paraphrases cost a provider call, not correctness." tone="blue" />
            <Tile label="F1" value={fmtScore(c.f1)} sub="harmonic mean of the two" why="One number balancing precision and recall equally. The threshold below was chosen where this peaks." tone="purple" />
            <Tile label="Threshold" value={fmtScore(c.threshold, 2)} sub={`F1-optimal in sweep: ${fmtScore(c.best_threshold_by_f1, 2)}`} why="Cosine similarity the cache requires between the new question and a stored one. Lower catches more paraphrases and more traps; higher does the opposite." tone={c.threshold === c.best_threshold_by_f1 ? 'neutral' : 'amber'} />
            <Tile label="Pairs" value={String(c.n_pairs)} sub={`${c.embedding_model ?? 'embeddings'}${c.seed_hits ? ` · ${c.seed_hits} seeds shared an entry` : ''}`} why="Size of the labelled dataset in evals/data/cache_pairs.jsonl. Small on purpose so every pair can be read; the traps are adversarial, so treat the scores as a stress test." />
          </div>

          <div className="mt-5 grid gap-5 lg:grid-cols-2">
            <div>
              <h3 className="mb-2 text-sm font-medium">Confusion matrix at threshold {fmtScore(c.threshold, 2)}</h3>
              <table className={`${TABLE} max-w-sm`}>
                <caption className="sr-only">Confusion matrix: expected versus predicted cache hits</caption>
                <thead>
                  <tr>
                    <th scope="col" className={TH}></th>
                    <th scope="col" className={TH}>predicted hit</th>
                    <th scope="col" className={TH}>predicted miss</th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-t border-border">
                    <th scope="row" className={`${TH} text-left normal-case tracking-normal`}>should hit</th>
                    <td className={`${TD} text-green-300`}>{c.tp} true positive</td>
                    <td className={`${TD} text-amber-300`}>{c.fn} false negative</td>
                  </tr>
                  <tr className="border-t border-border">
                    <th scope="row" className={`${TH} text-left normal-case tracking-normal`}>should miss</th>
                    <td className={`${TD} text-red-300`}>{c.fp} false positive</td>
                    <td className={`${TD} text-blue-300`}>{c.tn} true negative</td>
                  </tr>
                </tbody>
              </table>
              <h3 className="mb-2 mt-5 text-sm font-medium">By pair kind</h3>
              <div className="overflow-x-auto">
                <table className={TABLE}>
                  <caption className="sr-only">Outcomes by pair kind</caption>
                  <thead>
                    <tr>
                      {['kind', 'n', 'TP', 'FP', 'FN', 'TN'].map((h) => (
                        <th key={h} scope="col" className={TH}>
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(c.by_kind ?? {}).map(([kind, k]) => (
                      <tr key={kind} className="border-t border-border">
                        <th scope="row" className={`${TD} text-left font-normal`}>{kind}</th>
                        <td className={TD}>{k.n}</td>
                        <td className={TD}>{k.tp}</td>
                        <td className={`${TD} ${k.fp ? 'text-red-300' : ''}`}>{k.fp}</td>
                        <td className={`${TD} ${k.fn ? 'text-amber-300' : ''}`}>{k.fn}</td>
                        <td className={TD}>{k.tn}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                Kinds: <em>paraphrase</em> and <em>normalisation</em> should hit; <em>intent</em> (same words, different ask), <em>negation</em> and{' '}
                <em>entity</em> swaps should miss.
              </p>
            </div>
            <SweepChart rows={c.sweep ?? []} threshold={c.threshold ?? null} best={c.best_threshold_by_f1 ?? null} note={c.sweep_note} />
          </div>

          <h3 className="mb-2 mt-5 text-sm font-medium">Five example pairs</h3>
          <div className="overflow-x-auto">
            <table className={TABLE}>
              <caption className="sr-only">Example pairs with similarity and outcome</caption>
              <thead>
                <tr>
                  <th scope="col" className={TH}>cached question</th>
                  <th scope="col" className={TH}>new question</th>
                  <th scope="col" className={TH}>kind</th>
                  <th scope="col" className={TH}>similarity</th>
                  <th scope="col" className={TH}>outcome</th>
                </tr>
              </thead>
              <tbody>
                {(c.examples ?? []).map((e) => (
                  <tr key={e.id} className="border-t border-border">
                    <td className={TD}>{e.a}</td>
                    <td className={TD}>{e.b}</td>
                    <td className={TD}>{e.kind}</td>
                    <td className={TD}>{e.similarity === null ? 'no candidate' : fmtScore(e.similarity)}</td>
                    <td className={TD}>
                      <span className={`rounded-full border px-2 py-0.5 text-[11px] ${OUTCOME[e.outcome] ?? ''}`}>{e.outcome.replace('_', ' ')}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Section>
  );
}

const W = 360;
const H = 160;
const PAD = 8;
const SERIES: Array<{ key: 'precision' | 'recall' | 'f1'; label: string; cls: string }> = [
  { key: 'precision', label: 'precision', cls: 'stroke-green-400' },
  { key: 'recall', label: 'recall', cls: 'stroke-blue-400' },
  { key: 'f1', label: 'F1', cls: 'stroke-purple-300' },
];

function SweepChart({ rows, threshold, best, note }: { rows: SweepRow[]; threshold: number | null; best: number | null; note?: string }) {
  if (!rows.length) return null;
  const xs = rows.map((r) => r.threshold);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const xOf = (t: number) => PAD + ((t - xMin) / (xMax - xMin || 1)) * (W - 2 * PAD);
  const atThreshold = rows.find((r) => r.threshold === threshold);
  const summary = `Threshold sweep from ${xMin.toFixed(2)} to ${xMax.toFixed(2)}: F1 peaks at ${best ?? 'n/a'}. At the configured threshold ${threshold ?? 'n/a'}: precision ${fmtRatio(atThreshold?.precision)}, recall ${fmtRatio(atThreshold?.recall)}, F1 ${fmtScore(atThreshold?.f1)}.`;
  return (
    <figure>
      <figcaption className="mb-2 text-sm font-medium">Threshold sweep</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-44 w-full rounded-lg border border-border bg-card/60" role="img" aria-label={summary}>
        <title>{summary}</title>
        {[0.25, 0.5, 0.75].map((g) => (
          <line key={g} x1={PAD} x2={W - PAD} y1={H - PAD - g * (H - 2 * PAD)} y2={H - PAD - g * (H - 2 * PAD)} className="stroke-border" strokeWidth={0.5} />
        ))}
        {threshold !== null && <line x1={xOf(threshold)} x2={xOf(threshold)} y1={PAD} y2={H - PAD} className="stroke-amber-400" strokeWidth={1.5} strokeDasharray="4 3" />}
        {SERIES.map((s) => (
          <path key={s.key} d={pathFrom(sweepPoints(rows, s.key, W, H, PAD))} fill="none" strokeWidth={2} className={s.cls} strokeLinejoin="round" />
        ))}
        <text x={PAD + 2} y={PAD + 10} className="fill-muted-foreground" fontSize={9}>
          1.0
        </text>
        <text x={PAD + 2} y={H - PAD - 2} className="fill-muted-foreground" fontSize={9}>
          {xMin.toFixed(2)}
        </text>
        <text x={W - PAD - 22} y={H - PAD - 2} className="fill-muted-foreground" fontSize={9}>
          {xMax.toFixed(2)}
        </text>
      </svg>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground" aria-label="Legend">
        {SERIES.map((s) => (
          <li key={s.key} className="flex items-center gap-1">
            <svg className="h-2.5 w-4" viewBox="0 0 16 10" aria-hidden="true">
              <line x1={0} x2={16} y1={5} y2={5} strokeWidth={2} className={s.cls} />
            </svg>
            {s.label}
          </li>
        ))}
        <li className="flex items-center gap-1">
          <svg className="h-2.5 w-4" viewBox="0 0 16 10" aria-hidden="true">
            <line x1={8} x2={8} y1={0} y2={10} strokeWidth={1.5} strokeDasharray="2 2" className="stroke-amber-400" />
          </svg>
          configured threshold
        </li>
      </ul>
      <details className="mt-2 text-xs">
        <summary className="cursor-pointer text-muted-foreground hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring">Full sweep table</summary>
        <div className="mt-2 max-h-64 overflow-auto">
          <table className={TABLE}>
            <caption className="sr-only">Precision, recall and F1 at each threshold</caption>
            <thead>
              <tr>
                {['threshold', 'precision', 'recall', 'F1', 'FP', 'FN'].map((h) => (
                  <th key={h} scope="col" className={TH}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.threshold} className={`border-t border-border ${r.threshold === threshold ? 'bg-amber-500/10' : ''}`}>
                  <td className={TD}>{r.threshold.toFixed(2)}</td>
                  <td className={TD}>{fmtRatio(r.precision)}</td>
                  <td className={TD}>{fmtRatio(r.recall)}</td>
                  <td className={TD}>{fmtScore(r.f1)}</td>
                  <td className={TD}>{r.fp}</td>
                  <td className={TD}>{r.fn}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      {note && <p className="mt-2 text-[11px] text-muted-foreground">{note}</p>}
    </figure>
  );
}
