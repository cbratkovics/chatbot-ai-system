# Live Demo Diagnosis — `POST /api/v1/chat/completions` fails

Date: 2026-09-08. Phase 0 of the production-readiness pass. Read-only: nothing in `src/` or `frontend/` was changed.

## TL;DR

The live backend is up, CORS is correct, `/health` is green, and the request reaches OpenAI. **OpenAI rejects it with HTTP 429 `insufficient_quota` / `credit_balance_exhausted` — the account has no credits.** The backend mislabels that as a rate limit, retries it three times (wasting ~5 s), and returns `429 "OpenAI rate limit exceeded"`. The frontend throws that response away and prints `Request failed`. The Anthropic account is also out of credits, so switching models in the dropdown would fail too.

Two sentence interview version: *"The demo wasn't broken by infrastructure; it was broken by a billing state that the code reported as a rate limit and the UI reported as nothing. The fix is to classify quota errors as non-retryable 402s, surface the real error in the UI, and fail over to a free provider."*

## 1. Request path map

| Step | File | What happens |
|---|---|---|
| 1 | `frontend/components/ChatInterface/index.tsx:51-56` | Raw `fetch` to `${API_CONFIG.baseURL}/chat/completions`, body `{model, messages, stream:false}`. No timeout, no `Accept` header. |
| 2 | `frontend/components/ChatInterface/index.tsx:63-65` | `catch {}` discards status and body → `setError('Request failed')`. |
| 3 | `frontend/components/ChatInterface/index.tsx:224-227` | "Connected" pill is hardcoded JSX; it never calls `/health`. |
| 4 | `frontend/lib/config.ts:6,38-42` | Base URL defaults to `https://chatbot-ai-system.onrender.com/api/v1`; `timeout: 30000` is defined but only used by `frontend/lib/api.ts:19-21`, which `ChatInterface` does not import. |
| 5 | `src/chatbot_ai_system/server/main.py:152-161` | Middleware: CORS (added first, so **innermost**), GZip, RequestID, SlowAPI. |
| 6 | `src/chatbot_ai_system/server/main.py:204-220` | Catch-all `Exception` handler → bare `500 {"error":"Internal server error"}`. Runs in Starlette's `ServerErrorMiddleware`, **outside** CORS. |
| 7 | `src/chatbot_ai_system/api/routes.py:7,18` → `api/chat.py:35` | Router mounted at `/api/v1/chat`. |
| 8 | `src/chatbot_ai_system/api/chat.py:227-233` | `chat_completion` handler. Deps: `Settings` only. No Redis, no cache, no vector store, no auth/tenant middleware on this path. |
| 9 | `src/chatbot_ai_system/api/chat.py:132-148,171-178` | `ProviderFactory.MODEL_PROVIDER_MAP` allowlist. `gpt-3.5-turbo` **is** in it; `gpt-4o-mini` is not. Unknown model → 404. |
| 10 | `src/chatbot_ai_system/api/chat.py:181-195` | Missing key → `AuthenticationError` → 401. Otherwise builds `OpenAIProvider(timeout=30, max_retries=3)`. |
| 11 | `src/chatbot_ai_system/providers/openai_provider.py:106-138` | Retry loop, `AsyncOpenAI(max_retries=0, timeout=30)`. |
| 12 | `src/chatbot_ai_system/providers/openai_provider.py:178-195` | **Any** `openai.RateLimitError` (429) → backoff 1 s, 2 s, then `RateLimitError("OpenAI rate limit exceeded")`. OpenAI's `insufficient_quota` is also a 429, so it lands here. |
| 13 | `src/chatbot_ai_system/api/chat.py:334-340` | `RateLimitError` → `HTTPException(429, headers={"Retry-After": ...})`. |
| 14 | `src/chatbot_ai_system/server/main.py:164-184` | `http_exception_handler` rebuilds the JSON body and **drops `exc.headers`** (Retry-After is lost). |
| — | `src/chatbot_ai_system/api/chat.py:539-589` | `initialize_cache` runs at startup only (`server/main.py:92-99`). `redis_cache` is referenced by `/health` and the `/chat/cache/*` admin endpoints, **never by `chat_completion`**. |
| — | `src/chatbot_ai_system/cache/cache_key_generator.py:10-11` | Imports scikit-learn (TF-IDF) at module import, which `api/chat.py:13` triggers on every boot. |

Things that are **not** in the path (checked, not assumed): Pinecone / `vector_store` (no module outside `vector_store/` imports it; confirmed by inspecting `sys.modules` after importing the app), JWT/tenant middleware (only 4 `add_middleware` calls exist, none are auth), semantic-cache embedding calls.

## 2. Reproduction

All local runs used a clean environment (`cd` to a directory with no `.env`, provider keys and `REDIS_URL` unset, `ENVIRONMENT=production`) and a fresh uvicorn on a spare port. Script: any shell; replace `$PORT`.

```bash
# start (from repo root, then cd elsewhere so .env is not read)
PYTHONPATH=$PWD/src .venv/bin/python -m uvicorn chatbot_ai_system.server.main:app --port 8101

# the request the frontend sends
curl -s -D - -X POST http://127.0.0.1:8101/api/v1/chat/completions \
  -H 'Content-Type: application/json' -H 'Origin: https://example.vercel.app' \
  -d '{"model":"gpt-3.5-turbo","messages":[{"role":"user","content":"Say hi in three words."}],"stream":false}'
```

Results:

| Scenario | Startup | `/health` | `/chat/models` | `POST /chat/completions` |
|---|---|---|---|---|
| A. No Redis, no keys | 4.5 s | 503 `unhealthy`, `redis: not initialized`, `ai_providers: no API keys configured` | 200 | **401** `{"error":"OpenAI API key not configured…"}` in 3 ms |
| B. `REDIS_URL=redis://10.255.255.1:6379/0` (unreachable) | **~75 s** (`18:54:36` → `18:55:51`, "Timeout connecting to server"), then log says `Redis cache system initialized` anyway | not reachable inside the 30 s probe window | — | — |
| C. `OPENAI_API_KEY=sk-fake…` | 2.6 s | 503 `degraded` | 200 | **401** `{"error":"Invalid OpenAI API key"}` in 0.9 s (no retry, correct) |
| D. Live Render backend | awake | 200 `healthy`, `redis: healthy`, `ai_providers: configured: openai, anthropic`, `environment: development` | 200, correct `access-control-allow-origin` for the Vercel origin; OPTIONS preflight 200 | **429** `{"error":"OpenAI rate limit exceeded"}` after **5.18 s** (`x-process-time`), CORS headers present |

Direct provider probe with the keys in the local `.env` (prints only status and error codes; the script never echoes key material):

```
openai gpt-3.5-turbo : HTTP 429 type=insufficient_quota code=credit_balance_exhausted "You have no credits remaining…"
openai gpt-4o-mini   : HTTP 429 type=insufficient_quota code=credit_balance_exhausted
anthropic claude-3-haiku-20240307 : HTTP 400 invalid_request_error "Your credit balance is too low…"
anthropic claude-3-5-haiku-latest : HTTP 400 invalid_request_error "Your credit balance is too low…"
```

The 5.18 s live latency matches the code exactly: attempt 1 (~0.7 s) + backoff ~1 s + attempt 2 + backoff ~2 s + attempt 3, then raise.

CORS-on-500 check (in-process, `TestClient`, a throwaway route that raises `RuntimeError`):

```
/api/v1/chat/models : HTTP 200 access-control-allow-origin=http://localhost:3000
/__boom             : HTTP 500 access-control-allow-origin=None
```

## 3. Root causes, ranked by evidence

### RC1 — OpenAI account has no credits; code reports it as a rate limit and retries it (CONFIRMED, live)
- Evidence: live 429 in 5.18 s; direct probe returns `insufficient_quota` / `credit_balance_exhausted`; the same error for `gpt-4o-mini`, so it is not model-specific.
- Code: `providers/openai_provider.py:178-195` treats every `openai.RateLimitError` as transient. OpenAI uses HTTP 429 for both `rate_limit_exceeded` (transient) and `insufficient_quota` (permanent until billing changes).
- Minimal fix: (a) add credits and a hard monthly limit in the OpenAI dashboard; (b) in the provider, inspect `e.code` / `e.body["error"]["type"]`: if `insufficient_quota` → raise `QuotaExceededError` (already defined in `providers/base.py:135`) with `status_code=402`, `retryable=False`, no backoff; map it to HTTP 402 in `api/chat.py`. Same treatment for Anthropic's 400 "credit balance is too low".
- Why it matters in an interview: a permanent error was being retried, which triples cost pressure on a real rate limit and hides a billing problem behind a transient-looking status.

### RC2 — Frontend discards the error (CONFIRMED, code)
- `ChatInterface/index.tsx:56,63-65`: `throw new Error(...)` inside `try`, then `catch {}` with no argument. Status, `request_id`, and message are lost; user sees `Request failed`.
- Minimal fix: read `res.status` and `await res.json().catch(() => null)`, render `error.error` + `request_id` in the banner. Keep the message sanitized (no stack traces come from the backend anyway).

### RC3 — Unhandled 500s are invisible to the browser (CONFIRMED, test)
- The catch-all `Exception` handler (`server/main.py:204`) executes in `ServerErrorMiddleware`, which wraps the whole app including `CORSMiddleware`. Its JSON 500 has no `Access-Control-Allow-Origin`, so the browser reports a network error and `fetch` rejects with a `TypeError` — indistinguishable from the backend being down.
- The chat route currently converts everything to `HTTPException` (`api/chat.py:350-357`) so this is latent there, but it applies to every other route and to any future bug.
- Minimal fix: a tiny error-catching middleware registered *inside* CORS (i.e. `add_middleware` called before `CORSMiddleware`), returning the same structured error body. Then the `Exception` handler becomes a last resort that should never fire.

### RC4 — Unreachable Redis blocks startup for ~75 s and lies about it (CONFIRMED, local)
- `cache/redis_cache.py:146-156`: `ConnectionPool.from_url` with no `socket_connect_timeout`; `ping()` waits out the OS TCP timeout. `server/main.py:96-97` logs "Redis cache system initialized" even though `initialize_cache` swallowed the failure (`api/chat.py:586-589`).
- On Render this turns a Redis hiccup or a stale `REDIS_URL` into a failed health check / restart loop during the free-tier cold start.
- Minimal fix: `socket_connect_timeout=2`, `socket_timeout=2`; on failure fall back to an in-process cache and log one warning; `/health` reports `cache: "memory"` vs `"redis"`.

### RC5 — The cache is not on the request path at all (CONFIRMED, code)
- `chat_completion` never reads or writes `redis_cache`; `cached`, `cache_key`, `similarity_score` in the response are always `False`/`None`. `SEMANTIC_CACHE_ENABLED` and `CACHE_WARMING_ENABLED` affect only startup and the admin endpoints.
- Not a cause of the failure, but it means the "semantic cache" and "cache hit rate" claims are not exercised by the demo. Phase 1/2 must wire it in for the telemetry chip to show HIT/MISS honestly.

### RC6 — scikit-learn is imported on every boot (CONFIRMED, measured)
- `cache/cache_key_generator.py:10-11` pulls in numpy/scipy/sklearn. Importing the app alone: **2.8 s wall, 160 MB RSS** on this machine, before uvicorn or any request. On a 512 MB free-tier instance with `--workers 2` (`render.yaml:9`) that is a large share of memory and a slower cold start.
- Minimal fix: lazy-import sklearn inside the semantic path, or replace TF-IDF with exact-match hashing for the demo (Phase 1 decision).

### RC7 — Stale model allowlists and dead failover flag (CONFIRMED, code)
- `api/chat.py:132-148` and `providers/openai_provider.py:35-43` list only `gpt-3.5-*` / `gpt-4-*preview`; `gpt-4o-mini` is absent. `providers/anthropic_provider.py:34-41` lists `claude-2.x`, `claude-instant-1.2`, and 2024-dated Claude 3 models, several of which are retired at Anthropic. The UI shows all 13 as selectable.
- `ENABLE_FALLBACK` (`config/settings.py:79`) is never read on this path; `ProviderFactory` picks exactly one provider and there is no failover in `chat_completion`. The README's "automatic failover" is not what the demo executes.
- Minimal fix: one model table keyed by provider, defaults to `gpt-4o-mini`; failover implemented in the route (Phase 1).

### RC8 — No timeout, no wake-up state, fake "Connected" pill (CONFIRMED, code)
- `ChatInterface` uses raw `fetch` with no `AbortController`; the browser's own limit (~5 min in Chrome) applies. So a Render cold start (~30–60 s) does **not** cause `Request failed`; it causes a silent spinner. The 30 s timeout in `lib/api.ts` is unused by this component.
- The "Connected" indicator (`index.tsx:224-227`) is static JSX. It would say Connected with the backend down.
- Minimal fix: `/health` probe on mount with a "waking up the backend" state, 60 s timeout on the first call, honest connection pill.

### RC9 — `Retry-After` header dropped (minor)
- `server/main.py:176-184` builds a new `JSONResponse` and ignores `exc.headers`. Fix: pass `headers=exc.headers`.

### Also observed
- **Render config drift.** `render.yaml` declares `plan: starter`, a managed Redis service, `ENVIRONMENT=production`, `--workers 2`, and a placeholder `CORS_ORIGINS`. The live service reports `environment: development` and accepts the real Vercel origin, so the dashboard was configured by hand and `render.yaml` no longer describes it. Phase 1 should make `render.yaml` match the free-tier reality (single worker, no Redis dependency).
- **Local venv is stale.** `.venv/bin/*` shebangs point at `~/Desktop/chatbot-ai-system/.venv/bin/python` (old repo path), so `poetry run pytest` / `poetry run mypy` fail locally with "bad interpreter". `ruff` works because it is a native binary. Recreating the venv (`poetry install`, no dependency changes) fixes it. I worked around it with `.venv/bin/python -m …`.
- Baseline gates (run with the workaround): see section 5.

## 4. Minimal fix set for Phase 1 (proposed, not applied)

1. Provider error classification: `insufficient_quota` → 402 `QuotaExceededError`, non-retryable; Anthropic credit error likewise. (`openai_provider.py`, `anthropic_provider.py`, `api/chat.py`)
2. Structured error envelope `{error:{code,message,provider,request_id}}` returned from one place, inside the CORS boundary; `Retry-After` preserved. (`server/main.py`, `api/chat.py`)
3. Frontend: show status + message + request id; `/health` probe with wake-up state; 60 s first-call timeout. (`ChatInterface/index.tsx`)
4. Redis: 2 s connect timeout, in-memory fallback, honest `/health` and startup log. (`redis_cache.py`, `api/chat.py`, `server/main.py`)
5. Wire the cache into `chat_completion` so HIT/MISS is real. (`api/chat.py`)
6. Default model `gpt-4o-mini`; prune retired models; add a free-tier fallback provider with real failover on 401/402/429/5xx/timeout. (Phase 1 item 4)
7. Lazy-import or drop sklearn from the boot path. (`cache_key_generator.py`)

## 5. Quality-gate baseline (before any change)

Run with `.venv/bin/python -m …` because of the stale-venv shebangs (see above). Same commands as the CI gates otherwise.

| Gate | Result |
|---|---|
| `ruff check .` | clean |
| `mypy src/ --ignore-missing-imports` | `Success: no issues found in 163 source files` |
| `pytest tests/` | **76 failed, 218 passed, 36 skipped** in 5 min 28 s |

The suite is **not green today**, before any change. Breakdown of the 76 failures:

| File | Failures | Sampled cause |
|---|---|---|
| `tests/integration/test_api_endpoints.py` | 19 | routes that do not exist (`404 == 200` ×6), auth-gated routes hit without a token (`401 == 200` ×3), response shapes that were never implemented (`refresh_token`, `prometheus` content type, `memory_usage_mb`, `pong`) |
| `tests/integration/test_rate_limiting.py` | 12 | tests a per-tenant / cost-based / distributed limiter API that the app never wires in (only slowapi's default limit is registered) |
| `tests/integration/test_websocket_flow.py` | 10 | tests a WebSocket protocol (auth, heartbeat, broadcast, binary) the mounted handlers do not implement |
| `tests/integration/test_database_operations.py` | 8 | `get_async_engine() got an unexpected keyword argument 'url'`, `User has no attribute 'chats'`, un-awaitable `MagicMock` — stale ORM interface |
| `tests/integration/test_cache_integration.py` | 8 | calls `redis.asyncio.create_redis_pool` (removed from redis-py years ago) and expects a `cached` key the response never sets |
| `tests/integration/test_provider_failover.py` | 7 | `ValidationError … for CompletionRequest` — request model fields no longer match |
| `tests/integration/test_production_readiness.py` | 6 | `assert False` — checks hardcoded to fail / placeholders |
| `tests/integration/test_model_switching.py` | 6 | `core/models/anthropic_provider.py:67: AttributeError` — the second, older provider implementation under `core/models/` is broken |

Every failure is under `tests/integration/`; `tests/unit/`, `tests/contract/`, and the top-level tests pass. None of the 76 fails because a service is missing: they fail because the tests describe an API surface that was never built or has since drifted. This is also the reason there are two provider stacks (`providers/` used by the app, `core/models/` used only by tests). Recommendation for Phase 1: quarantine `tests/integration/` behind the existing `integration` marker (`-m "not integration"` in the default gate) and delete tests for endpoints that do not exist, rather than building features to satisfy them. Your call.

Phase 1 will treat this list as the baseline: new tests must pass, and I will not count a pre-existing failure as "introduced" unless it appears outside this list. Whether to fix or quarantine the pre-existing failures is a scope decision for you.

## 6. What Chris needs to verify in the dashboards (names only, never values)

**OpenAI platform**
- [ ] Billing → add prepaid credits. This is the actual outage.
- [ ] Set a **hard** monthly usage limit of $5 (Phase 1 target) and an email alert at $3.
- [ ] Confirm the key used on Render belongs to the project whose credits you just added (project-scoped keys can point at a different budget).

**Render (backend service)**
- [ ] `OPENAI_API_KEY` — set, and the same key the probe above will accept once credits exist.
- [ ] `ANTHROPIC_API_KEY` — either add Anthropic credits or plan to remove it from the demo; today it fails with "credit balance too low".
- [ ] `ENVIRONMENT` — live reports `development`; decide whether that is intentional (it currently only affects `/redoc` and log text).
- [ ] `CORS_ORIGINS` — confirmed working for `https://chatbot-ai-system.vercel.app`; note the exact value so `render.yaml` can be corrected.
- [ ] `REDIS_URL` — confirm whether a Render Key Value instance is attached and on which plan; Phase 1 makes it optional either way.
- [ ] `DEFAULT_MODEL`, `REQUEST_TIMEOUT`, `MAX_RETRIES` — note current values; Phase 1 changes defaults to `gpt-4o-mini`, 30 s, 2.
- [ ] Start command — confirm whether it still uses `--workers 2` (memory pressure on 512 MB) and which plan the service is actually on (`render.yaml` says `starter`).
- [ ] After Phase 1: `ENABLE_VECTOR_SEARCH` (leave unset/false), fallback provider key name (to be decided: `GROQ_API_KEY` or `GEMINI_API_KEY`), and the demo guardrail variables.

**Vercel (frontend)**
- [ ] `NEXT_PUBLIC_API_URL` — points at the Render service (the code also falls back to it when unset).
- [ ] `NEXT_PUBLIC_WS_URL` — only needed if the WebSocket path is used in Phase 2.
- [ ] `vercel.json` CSP `connect-src` already allows the Render origin; it also allows `https://*.pinecone.io`, which can be removed once vector search is flagged off.

**Local**
- [ ] Recreate the virtualenv so `poetry run …` works again (`poetry env remove --all && poetry install`, no dependency changes).
