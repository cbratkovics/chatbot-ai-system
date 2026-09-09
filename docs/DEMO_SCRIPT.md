# 3-Minute Interview Demo Script

Everything below is on screen at [chatbot-ai-system.vercel.app](https://chatbot-ai-system.vercel.app).
Open the page **before** the call: Render's free tier sleeps after 15 idle minutes and takes
30–60 s to wake. The status pill says "Waking up the backend" while it does.

Have `docs/DIAGNOSIS.md` and `docs/adr/` open in another tab in case they ask "why".

## 0:00 — Frame it (one sentence, before any click)

> "This is a chat service where the engineering is visible: every answer shows which provider
> answered, whether the cache hit, the latency, the token cost, and what failed over."

## 0:10 — Or just press Demo, then Run all

The guided demo sends the three requests below as standalone messages and explains each result
in place, while the **Evidence** rail on the right keeps score. If you have thirty seconds, do
that and narrate. If you have three minutes, drive it by hand:

## 0:15 — First question (streaming + telemetry)

**Click:** type *"In one sentence, what does a semantic cache do?"* and press Enter.

**Point at:** the tokens arriving live, then the chip under the answer:
`openai · gpt-4o-mini` · `cache MISS` · `~900 ms · ttfb 400` · `28 in / 22 out` · `$0.00002` · `streamed`.

**Say:**
> "Streaming is Server-Sent Events on the same POST endpoint. I chose SSE over the WebSocket
> path because it's a plain HTTP response: it survives the free-tier proxy, needs no reconnection
> protocol, and the failover and cache logic is computed once for both JSON and streamed
> answers. Token counts come from OpenAI's usage chunk; the cost is list price."

## 0:50 — Ask it differently (semantic cache HIT)

**Click:** type a paraphrase, e.g. *"Explain briefly what semantic caching does."* Enter.
("Conversation memory" is off by default, so each message is a standalone request and the cache
key is the question alone.)

**Point at:** `cache HIT · semantic 0.9x` · ~200 ms · `$1.8e-7 · saved $2e-5`. The Evidence rail's
"Spent vs avoided" tile moves.

**Say:**
> "Exact key first, free and instant. On an exact miss the question is embedded and compared
> against what this worker has answered, scoped to the same model, temperature and prior
> conversation, so a follow-up can't drag an unrelated answer over the threshold. The threshold
> isn't a guess: `/evals` has precision and recall on 68 labelled pairs and a sweep, and the
> default is where F1 peaks. That page also shows the honest part: negation traps still get
> through, because embeddings can't tell 'should' from 'should not'. That's the next thing I'd fix,
> and the eval is how I'd know it worked."

## 1:25 — Simulate a provider outage (failover)

**Click:** tick **Simulate provider failure** (top right). Ask a *new* question, e.g.
*"Name three failure modes of an LLM provider call."*

**Point at:** the chip: `groq · openai/gpt-oss-20b` and the amber badge
`failover: openai → groq (simulated)`. The Evidence rail's failover timeline shows the attempt
chain `openai/gpt-4o-mini 503 simulated_outage → groq/openai/gpt-oss-20b ok`.

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

**Click:** open **Evals** in the header.

**Say:**
> "Nothing on these pages is typed in. The chat page derives its numbers from the session's own
> telemetry; this page renders a committed eval artifact with its run timestamp and commit, and
> switches to the live copy when the backend is awake. The evals found three real bugs on their
> first runs. The repo has a diagnosis doc, seven one-page ADRs, and a test triage that
> un-quarantined 79 failing integration tests. Coverage is 31% and the README says so."

Stop talking. Let them ask.

## Likely questions, short answers

- **Why Groq as fallback?** OpenAI-compatible endpoint, so it reuses the same client with a
  different base URL: zero new dependencies. Free tier is enough for a demo.
- **Why one worker?** The cache and rate limits are in-process. Two workers would halve the
  hit rate and double the limits. Redis fixes both when you have it.
- **What would you do first with a budget?** Redis for the shared cache and limits, a lexical
  guard (negation and entity agreement) in front of the semantic match with the eval as the
  gate, then scrape `/metrics` into a real Prometheus.
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
