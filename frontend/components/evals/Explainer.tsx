/** Two or three plain-English sentences under each section heading. */
export function Explainer({ children }: { children: React.ReactNode }) {
  return <p className="mb-4 max-w-3xl text-sm leading-relaxed text-muted-foreground">{children}</p>;
}

export function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby={`${id}-title`} className="rounded-2xl border border-border bg-background/95 p-5 shadow-xl">
      <h2 id={`${id}-title`} className="mb-2 text-lg font-semibold">
        {title}
      </h2>
      {children}
    </section>
  );
}

export function Skipped({ reason }: { reason?: string }) {
  return (
    <p role="status" className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-300">
      This eval was skipped in the last run{reason ? `: ${reason}` : ''}.
    </p>
  );
}

const TABLE = 'w-full text-sm';
const TH = 'px-2 py-1.5 text-left text-[11px] uppercase tracking-wide text-muted-foreground';
const TD = 'px-2 py-1.5 tabular-nums align-top';
export const tableClasses = { TABLE, TH, TD };
