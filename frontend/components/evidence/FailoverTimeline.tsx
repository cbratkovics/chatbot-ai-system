'use client';

import { cn } from '@/lib/utils';
import { fmtMs } from './format';
import type { FailoverEvent } from './sessionStats';
import type { Attempt } from './types';

function attemptText(a: Attempt): string {
  if (a.outcome === 'ok') return `${a.provider}/${a.model} ok${a.latency_ms ? ` ${fmtMs(a.latency_ms)}` : ''}`;
  if (a.outcome === 'skipped') return `${a.provider}/${a.model} skipped${a.error_code ? ` (${a.error_code})` : ''}`;
  return `${a.provider}/${a.model} ${a.status_code ?? ''} ${a.error_code ?? 'failed'}`.trim();
}

const OUTCOME_CLASS: Record<Attempt['outcome'], string> = {
  ok: 'border-green-500/40 bg-green-500/10 text-green-300',
  failed: 'border-red-500/40 bg-red-500/10 text-red-300',
  skipped: 'border-border bg-background/60 text-muted-foreground',
};

/** Every failover this session, as the attempt chain the backend recorded (ADR 0003). */
export function FailoverTimeline({ events, highlight = false }: { events: FailoverEvent[]; highlight?: boolean }) {
  return (
    <div className={cn('rounded-xl border border-border bg-card/60 p-3', highlight && 'ring-2 ring-amber-400 motion-safe:animate-pulse')}>
      <div className="mb-2 text-[11px] uppercase tracking-wide text-muted-foreground">Failover timeline</div>
      {events.length === 0 ? (
        <p className="text-xs text-muted-foreground">
          No failovers yet. Tick “Simulate provider failure” or run Demo step 3 to force the primary to fail with a 503.
        </p>
      ) : (
        <ol className="space-y-2" aria-label="Failover events">
          {events.map((e) => (
            <li key={e.index} className="text-xs">
              <div className="mb-1 flex items-center justify-between text-muted-foreground">
                <span>
                  message #{e.index}
                  {e.simulated ? ' · simulated outage' : ''}
                </span>
                {typeof e.clientMs === 'number' && <span className="tabular-nums">{fmtMs(e.clientMs)} total</span>}
              </div>
              <ol className="flex flex-wrap items-center gap-1" aria-label={`Attempt chain for message ${e.index}`}>
                {e.attempts.map((a, i) => (
                  <li key={i} className="flex items-center gap-1">
                    {i > 0 && (
                      <span aria-hidden="true" className="text-muted-foreground">
                        →
                      </span>
                    )}
                    <span className={cn('rounded-full border px-2 py-0.5 text-[11px]', OUTCOME_CLASS[a.outcome])} title={a.message ?? undefined}>
                      {attemptText(a)}
                    </span>
                  </li>
                ))}
              </ol>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
