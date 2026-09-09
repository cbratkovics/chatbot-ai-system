'use client';

import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

export type Tone = 'neutral' | 'green' | 'purple' | 'amber' | 'blue' | 'red';

const TONES: Record<Tone, string> = {
  neutral: 'text-foreground',
  green: 'text-green-300',
  purple: 'text-purple-300',
  amber: 'text-amber-300',
  blue: 'text-blue-300',
  red: 'text-red-300',
};

type Props = {
  label: string;
  value: string;
  sub?: string;
  /** One line for a non-expert: what this number means and why it matters. */
  why: string;
  tone?: Tone;
  highlight?: boolean;
};

/** One headline number with an accessible "why this matters" tooltip. */
export function Tile({ label, value, sub, why, tone = 'neutral', highlight = false }: Props) {
  return (
    <div
      role="group"
      aria-label={`${label}: ${value}${sub ? `, ${sub}` : ''}`}
      className={cn(
        'rounded-xl border border-border bg-card/60 px-3 py-2.5 transition-shadow',
        highlight && 'ring-2 ring-amber-400 motion-safe:animate-pulse',
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</span>
        <Tooltip>
          <TooltipTrigger asChild>
            <button
              type="button"
              aria-label={`Why ${label.toLowerCase()} matters`}
              className="inline-flex h-4 w-4 items-center justify-center rounded-full border border-border text-[10px] leading-none text-muted-foreground hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              ?
            </button>
          </TooltipTrigger>
          <TooltipContent>{why}</TooltipContent>
        </Tooltip>
      </div>
      <div className={cn('mt-1 text-lg font-semibold leading-tight tabular-nums', TONES[tone])}>{value}</div>
      {sub && <div className="mt-0.5 text-[11px] text-muted-foreground">{sub}</div>}
    </div>
  );
}
