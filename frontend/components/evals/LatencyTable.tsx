'use client';

import { fmtMs } from '@/components/evidence/format';
import { Explainer, Section, Skipped, tableClasses } from './Explainer';
import type { LatencyEval } from './types';

const { TABLE, TH, TD } = tableClasses;
const LABEL: Record<string, string> = {
  hit_exact: 'cache hit, exact',
  hit_semantic: 'cache hit, semantic',
  miss: 'miss (provider call)',
  failover: 'failover (fallback provider)',
  bypass: 'bypass (cache skipped)',
};

export function LatencySection({ evalResult: l }: { evalResult?: LatencyEval }) {
  return (
    <Section id="latency" title="Latency by path">
      <Explainer>
        Client numbers are wall time measured by the machine that ran the evals, including the network; server numbers are what the backend
        reported for the same requests in its done event. P50 is the typical request, P95 and P99 are the slow tail. Every request the other
        evals made is pooled here, plus a block of exact repeats so the hit path has enough samples.
      </Explainer>
      {!l || l.status !== 'ok' ? (
        <Skipped />
      ) : (
        <div className="overflow-x-auto">
          <table className={TABLE}>
            <caption className="sr-only">Latency percentiles per request path</caption>
            <thead>
              <tr>
                {['path', 'n', 'client p50', 'client p95', 'client p99', 'client first token p50', 'server p50', 'server p95'].map((h) => (
                  <th key={h} scope="col" className={TH}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(l.paths ?? {}).map(([path, p]) => (
                <tr key={path} className="border-t border-border">
                  <th scope="row" className={`${TD} text-left font-normal`}>{LABEL[path] ?? path}</th>
                  <td className={TD}>{p.n}</td>
                  <td className={TD}>{fmtMs(p.client_ms.p50)}</td>
                  <td className={TD}>{fmtMs(p.client_ms.p95)}</td>
                  <td className={TD}>{fmtMs(p.client_ms.p99)}</td>
                  <td className={TD}>{fmtMs(p.client_ttfb_ms.p50)}</td>
                  <td className={TD}>{fmtMs(p.server_ms.p50)}</td>
                  <td className={TD}>{fmtMs(p.server_ms.p95)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {l.note && <p className="mt-2 text-xs text-muted-foreground">{l.note}</p>}
        </div>
      )}
    </Section>
  );
}
