/** Display helpers. Every input is an observed number; these only decide how to print it. */

export function fmtCost(usd: number | null | undefined): string {
  if (usd === null || usd === undefined || Number.isNaN(usd)) return 'n/a';
  if (usd === 0) return '$0.00';
  if (usd < 0.0001) return `$${usd.toExponential(1)}`;
  return `$${usd.toFixed(usd < 0.01 ? 5 : 4)}`;
}

export function fmtMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || Number.isNaN(ms)) return 'n/a';
  if (ms >= 10_000) return `${(ms / 1000).toFixed(1)} s`;
  return `${Math.round(ms)} ms`;
}

export function fmtPct(ratio: number | null | undefined): string {
  if (ratio === null || ratio === undefined || Number.isNaN(ratio)) return 'n/a';
  return `${Math.round(ratio * 100)}%`;
}

export function fmtSimilarity(s: number | null | undefined): string {
  if (s === null || s === undefined || Number.isNaN(s)) return 'n/a';
  return s.toFixed(2);
}
