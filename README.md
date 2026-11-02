# Multi-provider AI Chat Platform

A FastAPI / Next.js LLM gateway reference implementation with SSE streaming, provider failover,
optional caching, request guardrails and inspectable evaluation artifacts.

The public release in this branch is a **static project overview and recorded evaluation site**.
Live model generation is not hosted by this release. The gateway and original chat interface
remain available as optional local reference. No backend, managed Redis, database, model API or
embedding API is needed to build or serve the public site.

The existing Vercel project is the intended host; this change has **not been promoted to production**. It does
not establish what the currently published URL serves, and it does not stop existing bills.
The owner must verify deployment and the actual Render resources separately.

The static export is eligible for $0 hosting on a Vercel Hobby account that meets its eligibility
and usage limits. SQL Genius must also remain within eligible free static hosting for the two
projects' combined public runtime cost to be $0; SQL Genius was not inspected or changed here.
Optional local provider calls and existing cloud resources are outside that claim.

## Explore the engineering

| Capability | Implementation / design |
|---|---|
| Provider chain and recorded attempts | [providers/chain.py](src/chatbot_ai_system/providers/chain.py), [ADR 0003](docs/adr/0003-provider-failover-policy.md) |
| SSE `meta → delta* → done/error` and structured errors | [api/chat.py](src/chatbot_ai_system/api/chat.py), [api/errors.py](src/chatbot_ai_system/api/errors.py), [ADR 0005](docs/adr/0005-sse-streaming-over-websocket.md) |
| Redis-to-memory fallback; optional semantic lookup | [cache/](src/chatbot_ai_system/cache/), [ADR 0001](docs/adr/0001-optional-redis-with-memory-fallback.md), [ADR 0007](docs/adr/0007-semantic-cache-on-the-demo-path.md) |
| In-process request and token guardrails | [api/guardrails.py](src/chatbot_ai_system/api/guardrails.py), [ADR 0004](docs/adr/0004-demo-guardrails.md) |
| Committed evidence and scoring | [evals/](evals/), [ADR 0006](docs/adr/0006-system-evals-as-committed-artifacts.md) |
| Static public release boundary | [ADR 0008](docs/adr/0008-static-public-evidence.md) |

The [architecture diagrams](docs/architecture/ARCHITECTURE.md) describe the optional gateway,
not services running behind the static site. Historical screenshots are not evidence of a
current deployment; no placeholder screenshots are used by the public page.

## Build and serve the public site

Requires Node **24.x**, npm **9+** and Python 3 for the local static file server. No `.env` file
or provider key is required. Do not configure `NEXT_PUBLIC_API_URL` or `NEXT_PUBLIC_WS_URL`:
production builds reject those legacy backend settings.

```bash
cd frontend
npm ci
npm run lint
npm test
npm run typecheck
npm run build                 # Next.js static export → out/
npm start                     # serves out/; no Next runtime server
```

Open the overview and `/evals/` on the local static server. Directory-style paths support direct
refresh. All fonts and assets are local; no analytics, provider calls, hidden live mode or replay
are included. GitHub links are explicit navigation, not background requests.

Browser checks establish request blocking/recording before navigation and serve the **export**
with the configured security headers. They cover desktop/mobile layouts, keyboard interactions,
direct `/evals` refresh, unchanged run metadata, and outgoing requests without successful API mocks.

```bash
cd frontend
npx playwright install chromium          # one-time test tooling; no model calls
npm run test:browser
# If Chromium is already installed:
# PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium npm run test:browser
```

[Vercel settings and production verification](frontend/DEPLOYMENT.md) specify root `frontend`,
build `npm run build`, adapter Output Directory `.next`. The portable static artifact remains
`out/`; Vercel discovers it through Next’s export metadata. No deployment command is run by these instructions.

## Read the recorded evidence

The unchanged [JSON](evals/results/latest.json) and [Markdown report](evals/results/latest.md)
record the September 9, 2026 run against **localhost**, commit `9ccfc09` with a **dirty tree**:
187 requests in 149.4 seconds, with list-price estimates of $0.003755 spent and $0.002419 avoided.
The public `/evals/` page embeds the existing [frontend copy](frontend/lib/evals/latest.json), which omits the root artifact’s top-level per-request `samples` block and otherwise preserves the same run.
Viewing or republishing it makes no model or embedding requests and requires no monthly rerun.

- Semantic cache: **56.6% precision**, 90.9% recall, **23 false positives** among 68 adversarial
  labelled pairs. Wrong-answer reuse is a correctness limitation, not dependable semantic accuracy.
- The threshold sweep is an **offline estimate** from recorded nearest-candidate similarities;
  it is not a fresh live run at every threshold.
- Failover: 10/10 checks passed with a simulated primary 503 before calling the primary and real
  fallback responses. This small sample is **not an availability guarantee** or a timeout benchmark.
- Streaming contract: 20/20 recorded streams passed the event/metadata checks.
- Latency values describe that localhost run and its provider connections, **not current hosted latency**.

Offline tests and synthetic test-double timings are separate evidence. The deterministic
provider-orchestrator timing harness is [tests/test_provider_failover.py](tests/test_provider_failover.py),
with its provenance in [benchmarks/](benchmarks/). It is not a real-provider latency measurement.

## Optional local gateway

See [local development](docs/LOCAL_DEVELOPMENT.md) for Python/Poetry setup, API requests and the
original chat UI reference. The API boots without Redis, Postgres or provider keys; generating
answers/embeddings requires your own backend provider configuration and may incur charges.
Never put credentials in `NEXT_PUBLIC_*` variables or browser key entry.

```bash
poetry install --no-interaction
poetry run pytest tests/ -q    # offline by default; live-marked tests skip
poetry run ruff check .
poetry run mypy src/ --ignore-missing-imports
poetry check
poetry build
```

Offline tests forbid outbound DNS/connects while allowing loopback test servers. Live-marked
checks require both `ALLOW_LIVE_TESTS=1` and an explicit `TEST_*` service target. Normal CI sets
`ALLOW_LIVE_TESTS=0`, receives no provider credentials, and does not run provider-backed evals,
deployment hooks, managed services or persistent infrastructure. It retains short-lived artifacts
on standard GitHub runners; account usage limits still apply.

`make help` lists static, test and optional gateway targets. `make evals` and `make bench` are
explicit local developer actions that can make chargeable provider requests; they are not release
steps. [Historical hosting examples](docs/deployment/render.legacy.yaml) are opt-in reference,
not an inventory of live infrastructure or a requirement for the public demo.

Source layout: `frontend/` public static UI and retained chat source; `src/chatbot_ai_system/`
gateway; `tests/` offline/live-marked checks; `evals/` recorded evidence and optional runners;
`docker/` and `infrastructure/` optional full-stack examples. Historical audits and known gaps
remain in [docs/TEST_TRIAGE.md](docs/TEST_TRIAGE.md) and [docs/DIAGNOSIS.md](docs/DIAGNOSIS.md).

[MIT license](LICENSE) · [GitHub About draft](docs/portfolio/GITHUB_ABOUT.md)
