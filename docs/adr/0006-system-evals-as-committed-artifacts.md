# ADR 0006: System evals as committed artifacts; the UI shows observed numbers only

**Status:** accepted (2026-09-09)

## Context

The README used to carry a benchmark table with placeholders ("*run the script*") and a demo
script with example latencies typed from memory. The chat UI showed per-message telemetry but
nothing aggregate, and nothing measured whether the cache returned the *right* answer, only
whether it returned one. A hiring manager had no way to see precision or recall; a staff
engineer had no way to check a claim without running the system.

## Decision

1. **Evals are code in the repository** (`evals/`), runnable with one command
   (`make evals`, `python -m evals.run --base-url ...`) against any live backend:
   - cache paraphrase eval: a labelled dataset (`evals/data/cache_pairs.jsonl`) of paraphrases
     that should hit and near-duplicates, negations and entity swaps that must not; precision,
     recall, F1, confusion matrix, per-kind breakdown and a threshold sweep;
   - failover eval: simulated primary outage, per-check pass counts, added latency versus
     baseline;
   - SSE contract eval: the `meta -> delta* -> done | error` invariants over mixed paths;
   - latency eval: client and server P50/P95/P99 per path.
2. **The result is a committed artifact**, `evals/results/latest.json`, schema-versioned and
   stamped with run timestamp, commit SHA (read-only `git rev-parse`), target URL, request count
   and cost. A Markdown twin (`latest.md`) is the human summary. A run with any failed request is
   written to `last-failed.json` and never replaces `latest.json`.
3. **The UI shows observed numbers only.** The chat page's Evidence rail derives every figure
   from the telemetry of the session's own requests through a pure, unit-tested function, and
   labels a missing field as unknown rather than zero. The `/evals` page renders the committed
   artifact (embedded at build time so it works while the backend sleeps) and prefers the live
   copy from `GET /api/v1/evals/latest` when the backend answers with one at least as new,
   saying which source is on screen. No number on either page is typed in by hand, and each
   tile carries a one-line explanation of what it means.
4. **Tuning decisions come from the artifact.** The semantic-cache threshold is the F1-optimal
   value from the sweep (ADR 0007), and changes only with a new run.
5. **Scoring functions are unit-tested on fixture data**, so the maths behind the artifact is
   checked without a network.

## Consequences

- Claims in the README are links to the artifact or to `/evals`, not sentences with numbers.
- The evals found real defects on their first runs: Groq's gpt-oss returning empty answers at the
  demo's token cap, an outer rate limiter poisoning a run, and a rounding mismatch between the
  Python and TypeScript percentile functions. That is the point of running them.
- The cache eval is adversarial by design and reports precision of 0.57 on its trap set at the
  chosen threshold. Publishing that number is the honest cost of publishing any number.
- A full run costs well under a cent and about two and a half minutes, but needs a backend with
  `DEMO_GUARDRAILS_ENABLED=false RATE_LIMIT_ENABLED=false`; the runner warns otherwise.
- The frontend carries a copy of the artifact (`frontend/lib/evals/latest.json`) because the
  Vercel build only sees the `frontend` directory. The runner writes both copies; they must be
  committed together.
