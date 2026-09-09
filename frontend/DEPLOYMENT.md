# Frontend Deployment (Vercel Hobby)

The frontend is a Next.js 15 app deployed on Vercel. It talks to one backend URL and
nothing else. There is no Redis, Pinecone, or database requirement for the demo: the
backend degrades gracefully and reports what it is using on `/health`.

## What runs in the demo

| Component | Demo | Full deployment |
|---|---|---|
| Frontend | Vercel Hobby (this app) | same |
| Backend API | Render free tier, one uvicorn worker | any container host |
| Response cache | in-process LRU (per worker, resets on deploy) | Redis via `REDIS_URL` |
| Providers | OpenAI `gpt-4o-mini` → Groq `openai/gpt-oss-20b` failover | any subset of OpenAI / Anthropic / Groq |
| Vector search | off (`ENABLE_VECTOR_SEARCH=false`) | Pinecone behind the flag |

## Vercel project settings

1. Root Directory: `frontend`
2. Framework preset: Next.js
3. Node version: 20.x
4. Build / install commands: defaults (`npm run build`, `npm ci`)

## Environment variables (Vercel dashboard)

```bash
NEXT_PUBLIC_API_URL=https://chatbot-ai-system.onrender.com
```

That is the only variable the demo needs. The app appends `/api/v1` if it is missing
and falls back to the Render URL above when the variable is unset. Optional:

```bash
NEXT_PUBLIC_APP_NAME=AI Chat System
```

## Backend environment variables (Render dashboard)

See `render.yaml` at the repo root for the full list with defaults. The ones that matter:

| Variable | Purpose |
|---|---|
| `OPENAI_API_KEY` | primary provider. Set a hard monthly limit in the OpenAI dashboard. |
| `GROQ_API_KEY` | free-tier fallback provider (optional but recommended for the failover demo) |
| `CORS_ORIGINS` | JSON array containing your Vercel origin, e.g. `["https://chatbot-ai-system.vercel.app"]` |
| `DEFAULT_MODEL` | `gpt-4o-mini` |
| `FALLBACK_MODELS` | `groq:openai/gpt-oss-20b` |
| `DEMO_*` | per-IP rate limits, token cap, history cap, daily token budget |
| `DEMO_FAILURE_TOGGLE_ENABLED` | `true` shows the "Simulate provider failure" switch; the UI then sends `X-Demo-Simulate-Failure: 1` |
| `REDIS_URL` | leave unset on the free tier; the in-process cache is used automatically |

## Cold starts

Render's free tier sleeps after 15 minutes idle and takes 30–60 s to wake. The UI
handles this: the status pill shows "Waking up the backend", the first request has a
60 s timeout and one retry, and later requests use a 30 s timeout.

## Verify after deploy

```bash
# backend health: cache backend and configured providers
curl https://chatbot-ai-system.onrender.com/health

# models the demo can serve (default first)
curl https://chatbot-ai-system.onrender.com/api/v1/chat/models

# a completion; response includes telemetry{provider, model, cache, latency_ms, usage, cost_usd, attempts}
curl -X POST https://chatbot-ai-system.onrender.com/api/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Say hi in three words."}]}'

# the same, streamed as Server-Sent Events (what the UI uses)
curl -N -X POST https://chatbot-ai-system.onrender.com/api/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Count to five."}],"stream":true}'
```

Expected `/health`:

```json
{"status": "healthy", "checks": {"cache": "memory", "ai_providers": "configured: openai, groq", "default_model": "gpt-4o-mini", "fallback_chain": ["groq:openai/gpt-oss-20b"]}}
```

Errors are always `{"error": {"code", "message", "provider", "request_id"}}` with a real
status (401/402/404/422/429/502/503/504). The UI shows that line verbatim, so a
provider billing problem reads as `402 provider_quota_exhausted [openai]: …`, not
"Request failed".

## CORS

The backend's `CORS_ORIGINS` must include the exact Vercel origin. Preview deployments
have unique origins; add them explicitly or test previews against a local backend.
`frontend/vercel.json` already allows `connect-src` to the Render host.

## Troubleshooting

- **"Backend unreachable" after 60 s**: the Render service is down or still building. Check the Render dashboard logs.
- **`401 provider_auth_error`**: the key named in the message is missing on Render.
- **`402 provider_quota_exhausted`**: that provider's account has no credits. Failover to Groq only happens if `GROQ_API_KEY` is set.
- **`429 rate_limited` / `daily_limit_reached` / `demo_budget_exhausted`**: demo guardrails. Raise the `DEMO_*` limits on Render if you need more for a session.
- **Build errors on Vercel**: see `TAILWIND_V3_MIGRATION.md`; Tailwind v3 is used deliberately because v4's native binaries did not install on Vercel.
