# Static public hosting

This release exports the project overview and recorded `/evals/` page. It does not host chat,
Python, Redis, a database or provider/embedding calls. The existing Vercel project is the initial
target. A feature-branch preview may be created for review; production promotion is a separate
action. This release preparation does not alter existing Render resources.

## Exact Vercel settings (owner action after review)

| Setting | Value |
|---|---|
| Account / plan | Eligible Vercel Hobby account, within free usage limits |
| Root Directory | `frontend` |
| Framework Preset | Next.js (static export configured in `next.config.js`) |
| Node.js Version | `24.x` |
| Install Command | `npm ci` |
| Build Command | `npm run build` |
| Output Directory | `out` |
| Environment variables | None required; remove `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL` in all deployment scopes |

No rewrites, SPA fallback, functions, API routes, proxy, font service, analytics account or backend
host is needed. Keep Web Analytics and Speed Insights disabled in the project dashboard (they
could inject scripts outside repository control). The export uses directory-style trailing
slashes; `/evals` redirects to `/evals/` and resolves to `evals/index.html` on a static host.

`vercel.json` allows connections only to the site's own origin. The static Next.js hydration
scripts need `script-src 'unsafe-inline'`; `unsafe-eval` and external connection/image/font
allowlists have been removed. Do not add hosted provider keys, even to preview environments.
Vercel is configured to apply these headers from `frontend/vercel.json`; verify the actual preview
response headers before accepting the host configuration. The local server only validates the
policy against exported assets, not the remote host. Another static host must apply equivalent
headers separately.

## Reproduce before release

```bash
npm ci
npm run lint
npm test
npx tsc --noEmit
npm run typecheck
npm run build
npx playwright install chromium
npm run test:browser
npm start                       # static out/, with the same configured headers
```

Screenshots and request audits are written under `test-results/`; the browser test uses no
successful network mocks and fails on external requests, page errors or escaped live code.
The test server is only a file server. To host portably, copy `out/` to any directory-style
static host; there is no runtime Node/Python application to deploy.

## Minimal production verification checklist

- Open overview and directly refresh `/evals` and `/evals/` on the actual public domain, on desktop
  and mobile; check keyboard navigation, tooltips and the full sweep table.
- Inspect Network from before navigation: only same-origin static files; no Render/provider/
  embedding/Pinecone, remote fonts, analytics, sockets or beacons. Verify response CSP/headers.
- Confirm static labelling, no composer/online/loading state, and historical run metadata:
  September 9, 2026, dirty `9ccfc09`, localhost, 187 requests; precision 56.6%, 23 false positives.
- Inspect the deployed build output for static assets only, no functions/proxy routes/secrets.
  A local build does not prove the platform's deployed output or dashboard injection settings.
- Confirm both this site and SQL Genius meet free hosting eligibility/limits. SQL Genius is
  outside this repository and has not been verified by this change.
- Before retiring old resources, preserve important data and verify actual Render services,
  Redis instances and billing in the owner's account. The old blueprint names are not proof of
  inventory. Then the owner can retire unused resources separately. Do not revoke shared keys
  without checking their consumers. **No Render resource has been changed by this task.**

Historical optional backend hosting: `docs/deployment/render.legacy.yaml`. Do not import it for
the static release. Local provider-backed work may incur charges and is not the $0 public runtime.
