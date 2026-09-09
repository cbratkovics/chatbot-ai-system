# ADR 0003: Provider failover policy

**Status:** accepted (2026-09-08)

## Context

The live demo went down because OpenAI returned HTTP 429 `insufficient_quota` (no credits), the
provider code treated every 429 as a transient rate limit and retried it three times, and the
route had no fallback provider at all despite an `ENABLE_FALLBACK` setting
(`docs/DIAGNOSIS.md`, RC1 and RC7).

## Decision

`providers/chain.py` tries the provider that owns the requested model, then each `FALLBACK_MODELS`
entry in order, and records every attempt in the response.

| Error | Action |
|---|---|
| 401 auth, 402 quota (`insufficient_quota`, "credit balance"), 429 rate limit, 5xx, timeout, connection error, unknown model | fail over to the next provider |
| Other 4xx (bad request, content filter) | return immediately; the caller must change the request |
| Quota errors | never retried in place; they are permanent until billing changes |

- The primary is OpenAI `gpt-4o-mini`; the fallback is Groq `llama-3.1-8b-instant` through the
  OpenAI-compatible endpoint, so no new SDK was needed.
- Streaming fails over only before the first token. Once bytes are on the wire, switching
  providers would splice two answers together, so a mid-stream error is reported in-band instead.
- The reported error after a total failure is the first real upstream failure, not "no key
  configured", so a billing problem reads as a billing problem.
- A demo-only switch (`DEMO_FAILURE_TOGGLE_ENABLED` + `X-Demo-Simulate-Failure: 1`) makes the
  primary fail with a 503 before it is called, so failover can be demonstrated on demand and is
  labelled `simulated` in the telemetry.

## Consequences

- Every response carries `attempts[]` and a `failover` flag; the UI shows them.
- Legacy model ids (`gpt-3.5-turbo`) map to current ones so a stale env var cannot 404 the demo.
- The older `providers/orchestrator.py` (load-balancing strategies, circuit breakers) remains for
  the full deployment and is not on the demo path.
