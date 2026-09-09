import { describe, expect, it } from 'vitest';
import { fmtCost, fmtMs, fmtPct, fmtSimilarity } from './format';

describe('format helpers', () => {
  it('prints costs at a readable precision and never invents a value', () => {
    expect(fmtCost(undefined)).toBe('n/a');
    expect(fmtCost(null)).toBe('n/a');
    expect(fmtCost(0)).toBe('$0.00');
    expect(fmtCost(0.00002)).toBe('$2.0e-5');
    expect(fmtCost(0.0042)).toBe('$0.00420');
    expect(fmtCost(0.25)).toBe('$0.2500');
  });
  it('prints milliseconds and seconds', () => {
    expect(fmtMs(null)).toBe('n/a');
    expect(fmtMs(912.4)).toBe('912 ms');
    expect(fmtMs(12_345)).toBe('12.3 s');
  });
  it('prints ratios and similarities', () => {
    expect(fmtPct(null)).toBe('n/a');
    expect(fmtPct(2 / 3)).toBe('67%');
    expect(fmtSimilarity(0.9557)).toBe('0.96');
    expect(fmtSimilarity(undefined)).toBe('n/a');
  });
});
