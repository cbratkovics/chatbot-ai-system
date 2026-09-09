import { describe, expect, it } from 'vitest';
import { chooseArtifact, fmtDate, fmtRatio, parseArtifact, pathFrom, sweepPoints } from './artifact';
import type { EvalArtifact, SweepRow } from './types';

const art = (timestamp: string): EvalArtifact => ({ schema_version: 1, run: { timestamp, base_url: 'x' } });

describe('parseArtifact', () => {
  it('accepts schema 1 with a run block and rejects anything else', () => {
    expect(parseArtifact(art('2026-09-09T10:00:00+00:00'))).not.toBeNull();
    expect(parseArtifact({ schema_version: 2, run: { timestamp: 'x' } })).toBeNull();
    expect(parseArtifact({ schema_version: 1 })).toBeNull();
    expect(parseArtifact(null)).toBeNull();
    expect(parseArtifact('nope')).toBeNull();
  });
});

describe('chooseArtifact', () => {
  it('falls back to the static copy when live is missing or older', () => {
    const s = art('2026-09-09T10:00:00+00:00');
    expect(chooseArtifact(s, null)).toEqual({ artifact: s, source: 'static' });
    expect(chooseArtifact(s, art('2026-09-08T10:00:00+00:00')).source).toBe('static');
  });
  it('prefers live when it is the same run or newer', () => {
    const s = art('2026-09-09T10:00:00+00:00');
    expect(chooseArtifact(s, art('2026-09-09T10:00:00+00:00')).source).toBe('live');
    expect(chooseArtifact(s, art('2026-09-10T10:00:00+00:00')).source).toBe('live');
  });
});

describe('sweep chart maths', () => {
  const rows: SweepRow[] = [
    { threshold: 0.7, tp: 1, fp: 1, fn: 0, tn: 0, precision: 0.5, recall: 1, f1: 0.667 },
    { threshold: 0.8, tp: 1, fp: 0, fn: 0, tn: 1, precision: 1, recall: 1, f1: 1 },
    { threshold: 0.9, tp: 0, fp: 0, fn: 1, tn: 1, precision: null, recall: 0, f1: null },
  ];
  it('maps thresholds to x and metric to inverted y, skipping nulls', () => {
    const pts = sweepPoints(rows, 'f1', 104, 54, 2);
    expect(pts).toHaveLength(2);
    expect(pts[0].x).toBeCloseTo(2, 6);
    expect(pts[0].y).toBeCloseTo(54 - 2 - 0.667 * 50, 6);
    expect(pts[1].x).toBeCloseTo(52, 6);
    expect(pts[1].y).toBeCloseTo(2, 6);
    expect(sweepPoints([], 'f1', 100, 50)).toEqual([]);
  });
  it('renders an SVG path', () => {
    expect(pathFrom([{ x: 1, y: 2 }, { x: 3.14159, y: 4 }])).toBe('M1.0,2.0 L3.1,4.0');
    expect(pathFrom([])).toBe('');
  });
});

describe('formatting', () => {
  it('prints ratios and dates without inventing values', () => {
    expect(fmtRatio(0.5664)).toBe('56.6%');
    expect(fmtRatio(null)).toBe('n/a');
    expect(fmtDate('2026-09-09T10:57:49+00:00')).toBe('2026-09-09 10:57:49 UTC');
    expect(fmtDate('garbage')).toBe('garbage');
  });
});
