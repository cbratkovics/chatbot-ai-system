# ADR 0004: In-process demo guardrails

**Status:** accepted (2026-09-08)

## Context

The demo is a public URL with a real, prepaid API key behind it. The monthly budget is $0 of
infrastructure and at most $5 of OpenAI spend (hard-capped in the OpenAI dashboard). A single
abusive client must not be able to burn that budget, and the protection must not require a
database or Redis.

## Decision

`api/guardrails.py` enforces, in the worker process and configurable by `DEMO_*` env vars:

| Limit | Default | Response |
|---|---|---|
| Requests per IP per minute | 10 | 429 `rate_limited`, `Retry-After` |
| Requests per IP per day | 40 | 429 `daily_limit_reached` |
| `max_tokens` per request | ≤ 400 | silently clamped |
| Conversation history sent to the provider | last 8 messages (+ system prompt) | silently trimmed |
| Total tokens per day, all users | 150 000 | 429 `demo_budget_exhausted`, "try tomorrow" |

Client IP is the first hop of `X-Forwarded-For` (Render sets it), falling back to the socket
peer. The daily token budget counts provider-reported usage, or a local estimate when the
provider does not report it.

## Consequences

- Worst case per day is bounded by the token budget: 150k tokens of `gpt-4o-mini` is under $0.10.
- State is per worker and resets on redeploy; a determined attacker could get a fresh budget by
  waiting for a deploy. Acceptable for a demo, documented as such, and the OpenAI hard cap is the
  real backstop.
- The legacy `slowapi` limiter (100 req/min for all routes) remains as a coarse outer layer.
