# 3-Minute Interview Demo Script

Everything below is on screen at [chatbot-ai-system.vercel.app](https://chatbot-ai-system.vercel.app).
Open the page **before** the call: Render's free tier sleeps after 15 idle minutes and takes
30–60 s to wake. The status pill says "Waking up the backend" while it does.

Have `docs/DIAGNOSIS.md` and `docs/adr/` open in another tab in case they ask "why".

## 0:00 — Frame it (one sentence, before any click)

> "This is a chat service where the engineering is visible: every answer shows which provider
> answered, whether the cache hit, the latency, the token cost, and what failed over."

## 0:15 — First question (streaming + telemetry)

**Click:** type *"In one sentence, what does a semantic cache do?"* and press Enter.

**Point at:** the tokens arriving live, then the chip under the answer:
`openai · gpt-4o-mini` · `cache MISS` · `~900 ms · ttfb 400` · `28 in / 22 out` · `$0.00002` · `streamed`.

**Say:**
> "Streaming is Server-Sent Events on the same POST endpoint. I chose SSE over the WebSocket
> path because it's a plain HTTP response: it survives the free-tier proxy, needs no reconnection
> protocol, and the failover and cache logic is computed once for both JSON and streamed
> answers. Token counts come from OpenAI's usage chunk; the cost is list price."

## 0:50 — Same question again (cache HIT)

**Click:** press the up arrow or retype the identical question. Enter.

**Point at:** `cache HIT (1.00)` · single-digit ms · `$0.00` · no provider in the attempt log.

**Say:**
> "Exact-match cache on the normalised prompt, model and temperature. It's an in-process LRU
> because the demo runs with no Redis; set `REDIS_URL` and the same interface is backed by Redis.
> The health endpoint tells you which one is live. I deliberately kept semantic matching behind a
> flag: TF-IDF would put 160 MB of scikit-learn on the boot path of a 512 MB instance."

If asked why not embeddings: "Paraphrase matching is a feature for a real workload with a
similarity threshold you can tune against real traffic. For a demo it would just make the HIT
harder to explain."

## 1:25 — Simulate a provider outage (failover)

**Click:** tick **Simulate provider failure** (top right). Ask a *new* question, e.g.
*"Name three failure modes of an LLM provider call."*

**Point at:** the chip: `groq · llama-3.1-8b-instant` and the amber badge
`failover: openai → groq (simulated)`. Hover it: `openai/gpt-4o-mini: 503 simulated_outage`.

**Say:**
> "The toggle sends one header; the server refuses to call the primary and records a 503, then
> the chain moves to Groq. The only simulated part is the outage itself; the failover code is the
> same path that runs when OpenAI returns a real 429 or 5xx. Failover triggers on 401, 402, 429,
> 5xx and timeouts; a 4xx that's the caller's fault does not fail over. On streams it only fails
> over before the first token, because you can't splice two answers together."

**Then say the origin story, because it is the best part:**
> "This demo was actually down when I started this pass. OpenAI was returning 429
> `insufficient_quota`, the code treated it as a rate limit and retried three times, and the UI
> said 'Request failed'. Now a quota error is a non-retryable 402 with the provider name and a
> request id in the banner, and the chain falls over to a free provider."

## 2:15 — Untick the toggle, show the guardrails

**Click:** untick the toggle. Open `/api/v1/chat/health` in a new tab
(`https://chatbot-ai-system.onrender.com/api/v1/chat/health`).

**Point at:** `"cache": "memory"`, `"providers_configured"`, `"guardrails": {... "tokens_used_today": N}`.

**Say:**
> "Cost control without a database: per-IP limits per minute and per day, a 400-token cap, the
> last eight messages only, and a shared daily token budget that returns a friendly 429 saying
> 'try tomorrow'. Worst case for a full day is under ten cents, and the OpenAI account has a hard
> cap behind that. Infrastructure cost is zero: Vercel Hobby, Render free tier, no Redis."

## 2:45 — Close on the process

**Say:**
> "The repo has a diagnosis doc with the reproduction commands, five one-page ADRs for these
> decisions, and a test triage where I un-quarantined 79 failing integration tests: twelve tested
> an API that never existed and were deleted with git evidence, the rest were stale fixtures and
> drift. Coverage is 31% and the README says so."

Stop talking. Let them ask.

## Likely questions, short answers

- **Why Groq as fallback?** OpenAI-compatible endpoint, so it reuses the same client with a
  different base URL: zero new dependencies. Free tier is enough for a demo.
- **Why one worker?** The cache and rate limits are in-process. Two workers would halve the
  hit rate and double the limits. Redis fixes both when you have it.
- **What would you do first with a budget?** Redis for shared cache and limits, then real
  semantic matching with a threshold tuned on logged prompts, then Prometheus on `/metrics`.
- **What's not real in this repo?** Four modules are labelled design sketches in their first
  line. The tenants and API-key routers are stubs. `docs/TEST_TRIAGE.md` lists twelve places
  where the code, not the tests, is wrong.

## If something goes wrong live

| Symptom | Do |
|---|---|
| "Waking up the backend" for over a minute | Talk through the architecture diagram; refresh once. |
| `402 provider_quota_exhausted [openai]` | Say "that's the real error this demo used to hide"; tick the toggle off and on, Groq answers. |
| `429 rate_limited` | You hit ten per minute; that's the guardrail working. Wait for `Retry-After`. |
| Chip shows `~` before token counts | Provider didn't report usage; counts are a local tiktoken estimate and labelled so. |
