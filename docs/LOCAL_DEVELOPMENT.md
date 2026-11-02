# Optional local gateway development

The public static site needs only the frontend commands in the root README. This guide is for
explicit developer execution of the retained FastAPI gateway; provider-backed actions can incur
charges. No backend host, Docker, Redis, Postgres or model key is needed to read the source.

Use Python 3.11/3.12, Poetry 2.1.4 and Node 24.x. In a cloud task, use the existing isolated
checkout; do not create another worktree unless explicitly requested.

```bash
poetry install --no-interaction
# Only if you want local provider calls; do not overwrite an existing .env:
# cp .env.example .env
# Add your own provider key securely to the backend environment or ignored .env.
# Never place keys in NEXT_PUBLIC_* variables.
make dev
```

The API starts with an in-process cache when `REDIS_URL` is absent. Leave `DATABASE_URL` unset,
`ENABLE_VECTOR_SEARCH=false` and optionally `SEMANTIC_CACHE_ENABLED=false` for a minimal setup.
Without provider keys `/health` reports `unhealthy` with `no API keys configured`; this does not
prevent startup, `/docs` or `/api/v1/evals/latest`. Do not supply fake keys to make health look green.

Optional request after configuring a real key (not a release verification step):

```bash
curl -X POST http://localhost:8000/api/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"Say hello."}],"stream":true}'
```

`SEMANTIC_CACHE_ENABLED=true` may make OpenAI embedding calls on an exact miss. Redis-to-memory
fallback does not remove those provider costs. Local guardrails are not a provider account spend
limit. The legacy auth/full-deployment modules are reference implementations, not a production
security claim.

## Original chat UI reference

`frontend/components/ChatInterface/index.tsx`, its Evidence rail, guided live demo and SSE client
remain in source. They are excluded from every public route and production bundle; no query or
UI switch enables them. See [frontend/local-reference/README.md](../frontend/local-reference/README.md)
for an explicit local-only mounting example. Production builds reject backend URL settings, and
the retained UI configuration rejects non-development mode and non-loopback backends.

## Tests and optional infrastructure

`poetry run pytest tests/ -q` uses test doubles and blocks outbound networking by default. Live
markers additionally require `ALLOW_LIVE_TESTS=1` and their named `TEST_*` variable; do not opt in
as part of an ordinary release. Unit/contract results are not real-provider benchmarks.

`make up` and `make up-full` are optional local Docker infrastructure examples. They are not
required for the default public workflow. The frontend container serves the static export;
it no longer talks to the gateway. Do not apply Terraform/Helm or import historical Render
blueprints to set up the static demo.

`make evals` is an optional chargeable run against localhost, not CI. It writes both artifact
copies and their report; never rerun merely to republish the recorded evidence. `make bench`
requires explicit `BENCH_ARGS='--base-url http://localhost:8000'` and can also incur charges.
