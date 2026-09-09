# ADR 0001: Redis is optional; in-process LRU cache is the fallback

**Status:** accepted (2026-09-08)

## Context

The demo runs on Render's free tier. A managed Redis is either a paid add-on or a separate
free instance that can be unreachable during cold starts. Before this decision an unreachable
`REDIS_URL` blocked startup for ~75 s and the cache was not even on the request path
(`docs/DIAGNOSIS.md`, RC4 and RC5).

## Decision

- `REDIS_URL` unset, or unreachable within `CACHE_CONNECT_TIMEOUT_SECONDS` (2 s), falls back to
  `cache/memory_cache.py`: a bounded LRU with TTL that exposes the same methods as `RedisCache`.
- `/health` reports `cache: "redis"` or `cache: "memory"`; memory is a healthy state.
- Cache keys are exact matches on the normalised prompt (lower-cased, whitespace-collapsed,
  trailing punctuation stripped) plus model and temperature. TF-IDF similarity matching remains
  available behind `SEMANTIC_CACHE_ENABLED=true` and imports scikit-learn lazily.

## Consequences

- Zero infrastructure cost and no startup dependency. The demo boots with nothing but one API key.
- The memory cache is per worker and resets on deploy. That is acceptable for a demo and is why
  `render.yaml` runs one worker.
- Exact-match keys mean "ask the same question twice" is a HIT and a paraphrase is a MISS. The UI
  shows which. Semantic matching is an opt-in, not a default, because it would put ~160 MB of
  scikit-learn on the boot path of a 512 MB instance.
