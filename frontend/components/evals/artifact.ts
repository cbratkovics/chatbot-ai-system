/** Pure helpers for the /evals page: choosing between the live and build-time artifact, and chart maths. */

import type { EvalArtifact, SweepRow } from './types';

export const SUPPORTED_SCHEMA = 1;

function isRecord(x: unknown): x is Record<string, unknown> {
  return typeof x === 'object' && x !== null;
}

/** Accept a live payload only when it is a schema-1 artifact with a run block. */
export function parseArtifact(data: unknown): EvalArtifact | null {
  if (!isRecord(data) || data.schema_version !== SUPPORTED_SCHEMA) return null;
  const run = data.run;
  if (!isRecord(run) || typeof run.timestamp !== 'string') return null;
  return data as unknown as EvalArtifact;
}

/** Prefer the live artifact when it is valid and at least as new as the build-time copy. */
export function chooseArtifact(staticArtifact: EvalArtifact, live: EvalArtifact | null): { artifact: EvalArtifact; source: 'live' | 'static' } {
  if (!live) return { artifact: staticArtifact, source: 'static' };
  const liveTs = Date.parse(live.run.timestamp);
  const staticTs = Date.parse(staticArtifact.run.timestamp);
  if (Number.isFinite(liveTs) && Number.isFinite(staticTs) && liveTs < staticTs) {
    return { artifact: staticArtifact, source: 'static' };
  }
  return { artifact: live, source: 'live' };
}

export type Point = { x: number; y: number };

/** Map sweep rows to chart coordinates for one metric; rows with a null metric are skipped. */
export function sweepPoints(rows: SweepRow[], metric: 'precision' | 'recall' | 'f1', width: number, height: number, pad = 4): Point[] {
  if (!rows.length) return [];
  const xs = rows.map((r) => r.threshold);
  const xMin = Math.min(...xs);
  const xMax = Math.max(...xs);
  const span = xMax - xMin || 1;
  return rows
    .filter((r) => typeof r[metric] === 'number')
    .map((r) => ({
      x: pad + ((r.threshold - xMin) / span) * (width - 2 * pad),
      y: height - pad - (r[metric] as number) * (height - 2 * pad),
    }));
}

export function pathFrom(points: Point[]): string {
  return points.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
}

export function fmtRatio(x: number | null | undefined): string {
  if (x === null || x === undefined || Number.isNaN(x)) return 'n/a';
  return `${(x * 100).toFixed(1)}%`;
}

export function fmtScore(x: number | null | undefined, digits = 3): string {
  if (x === null || x === undefined || Number.isNaN(x)) return 'n/a';
  return x.toFixed(digits);
}

export function fmtDate(iso: string): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return iso;
  return new Date(t).toISOString().replace('T', ' ').replace(/\.\d+Z$/, ' UTC').replace('Z', ' UTC');
}
