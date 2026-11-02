# Static evidence site release

Public experience: static project overview and committed historical evaluations. No live model
generation, backend, Redis, database or embedding API. Backend and original chat UI remain local
reference; optional provider-backed work can incur developer charges.

Validation: attach frontend lint/unit/type/build/browser results and offline backend results.
Include request audits/screenshots from `frontend/test-results/`, known limitations and the exact
run provenance. Do not regenerate paid benchmark data as a release step.

Host: existing Vercel project, root `frontend`, Node 24, `npm ci`, `npm run build`, adapter Output Directory `.next` (static artifact `out/`).
No backend environment variables; keep dashboard-injected analytics disabled. Follow
`frontend/DEPLOYMENT.md` for the owner-run production verification checklist.

Release notes must state whether deployment was actually performed and whether any Render
resources were changed. Local preparation alone does neither. Verify actual old services and
preserve important data before the owner retires them; do not revoke shared credentials.
