# ADR 0005: Server-Sent Events for the demo's streaming path

**Status:** accepted (2026-09-08)

## Context

The repository already had a WebSocket endpoint (`/ws/chat`) with its own message protocol,
heartbeats, and a separate provider factory. The Phase 2 goal was a visible live token stream in
the default UI path on Render's free tier, behind a proxy that sleeps idle instances.

## Decision

Streaming uses Server-Sent Events over the existing `POST /api/v1/chat/completions` endpoint
(`"stream": true`), emitting `meta`, `delta`, `done`, and `error` events.

Why SSE rather than the WebSocket path:

- It is a normal HTTP response. It passes through Render's proxy, CORS, and the error-envelope
  middleware unchanged, and it can be reproduced with `curl -N`.
- One request, one answer, one connection: no reconnection protocol, no heartbeat state, no
  duplicated provider factory to keep in sync with the failover chain.
- Failover, cache HIT/MISS, guardrails, and telemetry are computed once in the same route for
  JSON and SSE; the WebSocket path would have needed all of it reimplemented.
- The UI needs a fetch reader and a 20-line parser, versus a WebSocket client with reconnection.

## Consequences

- The WebSocket endpoint stays for the full deployment and its own tests; the demo does not use it.
- An error after the first token cannot change the HTTP status; it is sent as an `error` event
  with any partial content, and the UI shows it in the banner.
- Token usage on streams comes from OpenAI's trailing usage chunk when available, otherwise from a
  local tiktoken estimate that the telemetry labels `estimated`.
