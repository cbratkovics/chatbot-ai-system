# Static evidence release handoff — 2026-11-02

Local review branch: `review/static-evidence-site`, based on `f900816f3e3bb046638ca1c16cef078e96921df5`.
This report records local review-candidate validation, not external CI or deployment success.
Review publication and any observed preview results are reported separately in the PR/handoff.
No merge, production promotion, cloud service/plan change, credential revocation or live provider
invocation is part of this release preparation. Render resources have not been changed.
Optional replay is deferred; the migration and combined $0 cost target remain unverified.

## Implemented

- Static project overview replaces public chat, with source/design/evidence links and explicit
  no-hosted-generation labelling. The original UI/SSE/evidence code stays local-reference source.
- Evaluations embed only the pre-existing frontend artifact, with its historical timestamp,
  localhost target, dirty commit, counts, costs and limitations. Both JSON artifacts and the
  original Markdown report remain byte-for-byte unchanged relative to the baseline commit. The existing frontend
  copy omits only the root JSON's top-level `samples`; a test verifies the remaining data matches.
- Static Next.js export with trailing-slash directories; system fonts; same-origin-only CSP;
  no analytics code, external font requests, live API probe, query-driven live mode or composer.
- Legacy backend URL settings fail a public production build. Retained local chat config requires
  development mode and an explicit loopback URL. Browser checks inspect exported bundles for leaks.
- CI runs static frontend and offline backend gates on standard runners, retains artifacts for
  three days, and has no deployment or paid-evaluation job. Docker image validation is manual-only.
- Historical Render blueprint moved to `docs/deployment/render.legacy.yaml`, auto-deploy disabled
  in that reference file. This neither inventories nor changes real services. README, About draft,
  hosting/local guides and historical deployment banners describe the new boundary.
- Two formerly provider-reaching readiness tests now check a deterministic chat reply and an
  actually protected refresh endpoint. No FastAPI application logic or auth policy was changed.
  Offline tests reject external DNS/connects; live-marked tests require explicit opt-in.
- Final review made `installCommand: npm ci` explicit in Vercel configuration and added an
  overview-refresh browser assertion. It caught an obsolete CI-readiness test requiring Pinecone
  credentials; that test now asserts the offline CI gates and absence of provider-secret inputs.
  The first final-review run had 355 passed and one such failure; after that correction the
  complete suite returned to 356 passed. No test was removed or newly skipped to achieve this.

## Executed checks

| Command / check | Local outcome |
|---|---|
| `cd frontend && npm ci` | Passed from updated lockfile; 474 packages |
| `npm run lint` | Passed; repaired the obsolete `next lint` script and excluded generated output |
| `npm test` | 19 passed in four suites, including artifact provenance and local-mode guard |
| `npx tsc --noEmit` and `npm run typecheck` | Passed |
| `npm run build` | Passed; `/`, `/evals/`, static 404; 31 exported files |
| `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium npm run test:browser` | 4 passed, desktop and mobile emulation, against `out/` |
| `ALLOW_LIVE_TESTS=0 make test` (Poetry, with `-ra`/external JUnit output) | 356 passed, 48 skipped, 2 expected failures; zero failures |
| `make lint` | Passed |
| `make typecheck` | Passed, 171 source files |
| `poetry check` and `poetry build` (Poetry 2.1.4) | Passed; wheel and sdist built |
| Both Compose files: `docker compose -f <file> config --no-interpolate` | Parsed successfully; existing obsolete-version warning only |
| Workflow YAML parse, artifact diff and `git diff --check` | Passed |

### Backend outcomes, kept distinct

The final run collected 406 tests: **356 passed, 48 skipped, 2 expected failures**, zero failures
and zero unexpected passes. The 48 skips are:

| Category | Count | Reason |
|---|---|---|
| Full-stack E2E: failover scenarios / multi-tenant flows / user journeys | 25 (11 / 6 / 8) | Existing class-level skips require a running application at localhost:8000 |
| Legacy WebSocket integration | 10 | Existing class-level skip says protocol tests need refactoring to match the API |
| WebSocket flow against a running server | 10 | Existing live markers require `TEST_BASE_URL`; additionally gated by explicit `ALLOW_LIVE_TESTS=1` |
| Redis integration | 1 | Existing live marker requires `TEST_REDIS_URL` and opt-in |
| Database integration | 1 | Existing live marker requires `TEST_DATABASE_URL` and opt-in |
| Async-client WebSocket smoke | 1 | Existing explicit skip requires Starlette TestClient |

The two strict expected failures already exist at the baseline commit, unchanged in this branch:

- `tests/integration/test_api_endpoints.py::TestAuthenticationEndpoints::test_login_returns_refresh_token`:
  login builds a refresh token, but the `AuthResponse` response model drops that field.
- `tests/integration/test_provider_failover.py::TestProviderFailover::test_concurrent_request_handling`:
  the legacy orchestrator's least-loaded selection minimizes free semaphore permits, selecting
  the busiest provider instead of spreading concurrent requests.

This change introduced neither known defect nor the underlying skip declarations. It adds an
explicit opt-in to already live-marked tests to prevent accidental external calls. No skipped or
expected-failing result is counted as passing. These omissions limit gateway/full-stack claims;
none is a prerequisite for the public overview/evaluation static-release acceptance criteria,
which are exercised separately against `out/` without a gateway, Redis, database or provider.

Existing deprecation/AsyncMock warnings remain. Docker containers, live providers, the optional
local UI mount, a hosted deployment, and the Python 3.11 CI matrix were not executed here.
Browser coverage is Chromium desktop/mobile emulation, not a Safari/device certification.

## Browser evidence and outgoing requests

Request interception and mechanism instrumentation are installed before navigation. Tests abort
external requests and socket connections rather than returning fake successful API responses.
They cover overview, eval navigation, reloads at `/evals` and `/evals/`, mobile page width,
keyboard tooltip/sweep-table interaction, skip link, and query strings that cannot activate chat.

The final audit recorded 66 requests in each desktop/mobile scenario, all same-origin HTML,
CSS, JavaScript and static RSC `.txt` navigation files.
No external origins, API calls, Axios/XHR, WebSocket, EventSource, beacon, worker, font or analytics
requests were observed. No browser console errors, page exceptions or permanent loading states
were observed. Generated HTML/JS/CSS/TXT/JSON files were scanned for hosted endpoints and common
provider-key patterns; no matches. This is local artifact evidence, not proof of production output.

Screenshots and full request logs are generated under the ignored local directory:

- `frontend/test-results/static-site-overview-recor-1b359-esh-need-only-static-assets-desktop/`
- `frontend/test-results/static-site-overview-recor-1b359-esh-need-only-static-assets-mobile/`

Each contains `overview.png`, `evals.png`, and `request-audit.json`. Sanitized PNGs from this local
static-export run are preserved for review in [images/static-phase1/](images/static-phase1/):
[desktop overview](images/static-phase1/desktop-overview.png),
[desktop evals](images/static-phase1/desktop-evals.png),
[mobile overview](images/static-phase1/mobile-overview.png),
[mobile evals](images/static-phase1/mobile-evals.png). They show only public static content and
historical labelled-eval data, not user conversations, account panels or secret values.
Raw request logs, generated HTML reports and traces are not committed. The generated browser
report is `frontend/playwright-report/index.html`; CI retains its outputs for three days.
These are local visual evidence, not screenshots of a deployed site.

## Host settings and owner verification

Existing Vercel project: eligible Hobby account, root **frontend**, Node **24.x**, install
**npm ci**, build **npm run build**, adapter Output Directory **.next** (static artifact **out/**),
no backend environment variables. Remove
`NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL` from every deployment scope. Keep dashboard-injected
Web Analytics/Speed Insights disabled. No replacement Python host is needed.

The earlier `out` host-override instruction was incorrect for Vercel CLI 65.4.0's Next adapter.
That adapter reads Next manifests from its Output Directory before detecting the static export.
The reviewed correction explicitly sets `.next`, retaining the Next.js preset and portable `out/`.
A plain `next build` success alone does not validate this adapter packaging step.

Local correction validation used the published `@vercel/next@27.0.0` bundled with Vercel CLI
65.4.0, installed in an isolated tooling directory. Its actual build/packaging API reproduced
`NEXT_NO_ROUTES_MANIFEST` with `outputDirectory: out`; `.next` returned 32 static `FileFsRef`
outputs, including overview/evals, and zero functions. No Vercel deployment or account
credentials were used.
Frontend lint, type checks, 19 unit tests and four exported-site browser checks passed again;
the browser regression check now verifies the internal manifests and successful `out/` export.
Actual Preview response headers and the new hosted packaging result remain external checks.

Before retiring paid resources, use the minimal production checklist in
[frontend/DEPLOYMENT.md](../frontend/DEPLOYMENT.md): verify real-domain static paths, Network/CSP,
no runtime functions/secrets, correct provenance, free-plan eligibility/limits, and actual old
Render/Redis inventory with important data preserved. SQL Genius was not inspected or changed;
its free-hosting eligibility and usage are a separate prerequisite to the combined $0 claim.
The current live URL and billing have not been verified by this local change.

## Changed-file inventory

The following paths comprise the review candidate changes. `render.yaml` was moved to the
historical path above; the original gateway implementation and recorded results are retained.

- `.env.example`
- `.github/CONTRIBUTING.md`
- `.github/RELEASE_TEMPLATE.md`
- `.github/workflows/ci.yml`
- `Makefile`
- `README.md`
- `docker-compose.yml`
- `docker/docker-compose.prod.yml`
- `docs/DEMO_SCRIPT.md`
- `docs/DEPLOYMENT_CHECKLIST.md`
- `docs/LOCAL_DEVELOPMENT.md`
- `docs/PRODUCTION_DEPLOYMENT.md`
- `docs/STATIC_RELEASE_VALIDATION.md`
- `docs/VERCEL_CONFIG_NOTES.md`
- `docs/adr/0006-system-evals-as-committed-artifacts.md`
- `docs/adr/0008-static-public-evidence.md`
- `docs/adr/README.md`
- `docs/architecture/ARCHITECTURE.md`
- `docs/deployment/render.legacy.yaml`
- `docs/guides/README_DEMO.md`
- `docs/images/static-phase1/desktop-evals.png`
- `docs/images/static-phase1/desktop-overview.png`
- `docs/images/static-phase1/mobile-evals.png`
- `docs/images/static-phase1/mobile-overview.png`
- `docs/portfolio/GITHUB_ABOUT.md`
- `frontend/.dockerignore`
- `frontend/.gitignore`
- `frontend/DEPLOYMENT.md`
- `frontend/Dockerfile`
- `frontend/README.md`
- `frontend/app/layout.tsx`
- `frontend/app/page.tsx`
- `frontend/components/AppNav.tsx`
- `frontend/components/ChatInterface/index.tsx`
- `frontend/components/evals/CacheEvalSection.tsx`
- `frontend/components/evals/EvalsView.tsx`
- `frontend/components/evals/FailoverSseSection.tsx`
- `frontend/components/evals/LatencyTable.tsx`
- `frontend/components/evals/RunMetaCard.tsx`
- `frontend/components/evals/artifact.test.ts`
- `frontend/components/evals/artifact.ts`
- `frontend/components/evals/types.ts`
- `frontend/eslint.config.mjs`
- `frontend/lib/config.test.ts`
- `frontend/lib/config.ts`
- `frontend/local-reference/README.md`
- `frontend/next.config.js`
- `frontend/nginx.static.conf`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/playwright.config.ts`
- `frontend/postcss.config.mjs`
- `frontend/scripts/serve-export.py`
- `frontend/tests/static-site.spec.ts`
- `frontend/vercel.json`
- `render.yaml`
- `scripts/bench_demo.py`
- `tests/conftest.py`
- `tests/integration/test_production_readiness.py`
- `tests/unit/test_offline_network.py`
