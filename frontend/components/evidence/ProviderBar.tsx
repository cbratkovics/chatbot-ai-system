'use client';

import type { ProviderShare } from './sessionStats';

const COLORS: Record<string, string> = {
  cache: 'bg-green-400',
  openai: 'bg-blue-400',
  anthropic: 'bg-orange-400',
  groq: 'bg-teal-400',
};
const colorFor = (name: string) => COLORS[name] ?? 'bg-gray-400';

/** Who answered: a stacked bar of provider slots, with cache hits as their own slice. */
export function ProviderBar({ providers }: { providers: ProviderShare[] }) {
  const total = providers.reduce((sum, p) => sum + p.count, 0);
  const summary = total
    ? `Answered by: ${providers.map((p) => `${p.name} ${p.count} (${Math.round((p.count / total) * 100)}%)`).join(', ')}`
    : 'No answers yet';
  return (
    <div className="rounded-xl border border-border bg-card/60 p-3">
      <div className="mb-2 text-[11px] uppercase tracking-wide text-muted-foreground">Who answered</div>
      <div role="img" aria-label={summary} className="flex h-3 w-full overflow-hidden rounded-full bg-muted">
        {providers.map((p) => (
          <div key={p.name} className={colorFor(p.name)} style={{ width: `${(p.count / Math.max(total, 1)) * 100}%` }} />
        ))}
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-muted-foreground" aria-label="Providers">
        {providers.map((p) => (
          <li key={p.name} className="flex items-center gap-1 tabular-nums">
            <span className={`inline-block h-2.5 w-2.5 rounded-sm ${colorFor(p.name)}`} aria-hidden="true" />
            {p.name} {p.count}
          </li>
        ))}
      </ul>
    </div>
  );
}
