'use client';

import { cn } from '@/lib/utils';
import { fmtMs } from './format';
import type { LatencyPoint, PathKind } from './sessionStats';

const FILL: Record<PathKind, string> = {
  hit: 'fill-green-400',
  miss: 'fill-purple-400',
  failover: 'fill-amber-400',
  error: 'fill-red-400',
};
const LEGEND: Array<[PathKind, string]> = [
  ['hit', 'cache hit'],
  ['miss', 'miss'],
  ['failover', 'failover'],
  ['error', 'error'],
];

const W = 320;
const H = 56;

/** One bar per answered message, height = client-observed latency, colour = path taken. */
export function Sparkline({ points, highlight = false }: { points: LatencyPoint[]; highlight?: boolean }) {
  const known = points.map((p) => p.ms).filter((ms): ms is number => ms !== null);
  const max = Math.max(1, ...known);
  const n = Math.max(points.length, 1);
  const slot = W / n;
  const gap = Math.min(4, slot * 0.25);
  const counts = points.reduce<Record<PathKind, number>>(
    (acc, p) => ({ ...acc, [p.kind]: acc[p.kind] + 1 }),
    { hit: 0, miss: 0, failover: 0, error: 0 },
  );
  const summary = `Latency per message, ${points.length} messages: ${counts.hit} cache hits, ${counts.miss} misses, ${counts.failover} failovers, ${counts.error} errors. Fastest ${fmtMs(
    known.length ? Math.min(...known) : null,
  )}, slowest ${fmtMs(known.length ? Math.max(...known) : null)}.`;

  return (
    <figure className={cn('rounded-xl border border-border bg-card/60 p-3', highlight && 'ring-2 ring-amber-400 motion-safe:animate-pulse')}>
      <figcaption className="mb-2 flex items-center justify-between text-[11px] uppercase tracking-wide text-muted-foreground">
        <span>Latency per message</span>
        <span className="normal-case tracking-normal">max {fmtMs(known.length ? max : null)}</span>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-14 w-full" role="img" aria-label={summary}>
        <title>{summary}</title>
        <line x1={0} y1={H - 0.5} x2={W} y2={H - 0.5} className="stroke-border" strokeWidth={1} />
        {points.map((p, i) => {
          const x = i * slot + gap / 2;
          const width = Math.max(2, slot - gap);
          if (p.ms === null) {
            return (
              <rect key={p.index} x={x} y={H - 6} width={width} height={4} className="fill-muted-foreground/60">
                <title>{`#${p.index} ${p.label}: latency unknown`}</title>
              </rect>
            );
          }
          const height = Math.max(2, (p.ms / max) * (H - 6));
          return (
            <rect key={p.index} x={x} y={H - 2 - height} width={width} height={height} rx={1} className={FILL[p.kind]}>
              <title>{`#${p.index} ${p.label}: ${fmtMs(p.ms)}`}</title>
            </rect>
          );
        })}
      </svg>
      <ol className="sr-only">
        {points.map((p) => (
          <li key={p.index}>{`Message ${p.index}: ${p.label}, ${fmtMs(p.ms)}`}</li>
        ))}
      </ol>
      <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted-foreground" aria-label="Legend">
        {LEGEND.map(([kind, label]) => (
          <li key={kind} className="flex items-center gap-1">
            <svg className="h-2.5 w-2.5" viewBox="0 0 10 10" aria-hidden="true">
              <rect width={10} height={10} rx={2} className={FILL[kind]} />
            </svg>
            {label}
          </li>
        ))}
      </ul>
    </figure>
  );
}
