# ADR 0008: Static public overview and recorded evidence

**Status:** implemented for review (2026-11-02); not promoted to production.

## Decision

The public Next.js app exports `/` and `/evals/` as static files. The overview links source and
ADRs; evaluations embed the unchanged `frontend/lib/evals/latest.json`. No live API check,
composer, replay, key entry or backend URL is present in the public import graph. There is no
provider, Redis, database, font service, analytics account or runtime server requirement.

This supersedes ADR 0006's public live-artifact preference and the historical hosted-demo scope
in ADRs 0001–0007. Their gateway implementations remain optional local reference. Historical
reports, including the dirty commit and costs, are preserved; publishing them does not require
a new paid evaluation. No synthetic transcript is inferred from aggregate measurements.

## Consequences

- Eligible free static hosting can serve the public site for $0. Existing Render resources do
  not disappear when code changes; the owner must verify and retire them separately.
- Local generation/embeddings may cost money. Offline CI blocks outbound networking and never
  supplies provider secrets; existing useful tests and deterministic timing remain.
- The original chat UI requires an explicit temporary local mount, development mode and a
  loopback API URL. Production rejects legacy backend env settings; query strings cannot opt in.
- CSP limits connections/assets to the site; system fonts remove build-time Google requests.
- Static-browser tests record/block requests before navigation, inspect generated output, and
  check direct refresh, mobile and keyboard behavior. They do not fake successful backend replies.
- Replay is deferred. It is unnecessary to retire paid services and requires separate provenance
  if added later.
