'use client';

import { fmtMs } from '@/components/evidence/format';
import { Tile } from '@/components/evidence/Tile';
import { fmtRatio } from './artifact';
import { Explainer, Section, Skipped, tableClasses } from './Explainer';
import type { CheckCounts, FailoverEval, SseEval } from './types';

const { TABLE, TH, TD } = tableClasses;

function ChecksTable({ checks, caption }: { checks: CheckCounts; caption: string }) {
  return (
    <table className={TABLE}>
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr>
          <th scope="col" className={TH}>check</th>
          <th scope="col" className={TH}>passed</th>
          <th scope="col" className={TH}>failed</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(checks).map(([name, k]) => (
          <tr key={name} className="border-t border-border">
            <th scope="row" className={`${TD} text-left font-mono text-xs font-normal`}>{name}</th>
            <td className={`${TD} text-green-300`}>{k.passed}</td>
            <td className={`${TD} ${k.failed ? 'text-red-300' : ''}`}>{k.failed}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const rateTone = (rate: number | null | undefined) => (rate === 1 ? 'green' : rate === null || rate === undefined ? 'neutral' : rate >= 0.9 ? 'amber' : 'red');

export function FailoverSection({ evalResult: f }: { evalResult?: FailoverEval }) {
  const lat = f?.latency_ms;
  return (
    <Section id="failover" title="Provider failover">
      <Explainer>
        Each run forces the primary provider to fail with a 503 before it is called, then checks that a different provider answered, that the
        failure was recorded in the attempt log, and that the first token still streamed. Added latency compares against normal runs made the
        same way without the outage, so both sides are real provider calls.
      </Explainer>
      {!f || f.status !== 'ok' ? (
        <Skipped reason={f?.reason} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Tile label="Runs passed" value={`${f.passed}/${f.n}`} sub={fmtRatio(f.success_rate)} why="A run passes only when every check in the table holds: fallback answered, primary failure recorded, different provider, first token delivered, done event, non-empty answer." tone={rateTone(f.success_rate)} />
            <Tile label="Fallback" value={f.fallback_provider ?? 'n/a'} sub={f.fallback_model ?? ''} why="The provider slot and model that answered after the primary failed, exactly as the chip on the chat page reports it." tone="blue" />
            <Tile label="First token" value={`${fmtMs(lat?.failover.ttfb.p50)} vs ${fmtMs(lat?.baseline.ttfb.p50)}`} sub={`added ${fmtMs(lat?.added_ttfb_p50)} at p50`} why="Median time to the first streamed token with the outage versus without. Negative means the fallback provider was faster than the primary on this run." />
            <Tile label="Total time" value={`${fmtMs(lat?.failover.total.p50)} vs ${fmtMs(lat?.baseline.total.p50)}`} sub={`added ${fmtMs(lat?.added_total_p50)} at p50`} why="Median wall time for the whole streamed answer with the outage versus without, measured by the machine that ran the eval." />
          </div>
          <div className="mt-4 overflow-x-auto">
            <ChecksTable checks={f.checks ?? {}} caption="Failover checks with pass and fail counts" />
          </div>
          {lat?.note && <p className="mt-2 text-xs text-muted-foreground">{lat.note}</p>}
        </>
      )}
    </Section>
  );
}

export function SseSection({ evalResult: s }: { evalResult?: SseEval }) {
  return (
    <Section id="sse" title="Streaming contract">
      <Explainer>
        Every streamed answer must follow one shape: a meta event, then content deltas, then exactly one done or error event, delivered as
        Server-Sent Events that are never gzip-compressed. These are the guarantees the chat page relies on, checked across cache hits, misses,
        bypasses and failovers.
      </Explainer>
      {!s || s.status !== 'ok' ? (
        <Skipped reason={s?.reason} />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            <Tile label="Streams passed" value={`${s.passed}/${s.n}`} sub={fmtRatio(s.pass_rate)} why="A stream passes only when all invariants in the table hold. One violation anywhere fails the stream." tone={rateTone(s.pass_rate)} />
            <Tile label="Paths covered" value={String(Object.keys(s.paths ?? {}).length)} sub={Object.entries(s.paths ?? {}).map(([p, n]) => `${p} ${n}`).join(' · ')} why="Which request paths the streams took. The contract has to hold on every one of them, not just the happy path." tone="blue" />
            <Tile label="Event shapes" value={String((s.event_shapes ?? []).length)} sub={(s.event_shapes ?? []).join(' | ')} why="Distinct sequences of event types seen. The contract allows exactly two: meta delta done, and meta done for an empty answer, plus a lone error." />
          </div>
          <div className="mt-4 overflow-x-auto">
            <ChecksTable checks={s.checks ?? {}} caption="Streaming contract invariants with pass and fail counts" />
          </div>
        </>
      )}
    </Section>
  );
}
