# ADR 0007: Embedding-based semantic cache on the demo path

**Status:** accepted (2026-09-08). Supersedes the "exact-match only" decision in
[ADR 0001](0001-optional-redis-with-memory-fallback.md); the Redis-optional decision there stands.

## Context

ADR 0001 kept the demo cache exact-match because the only similarity code in the repository
was a TF-IDF path that would have put ~160 MB of scikit-learn on the boot path of a 512 MB
instance. That path was also never wired into the request route, so "semantic cache" was a
label with no behaviour behind it. A paraphrase of a cached question was a MISS, and the UI
could not show a similarity score that was not the constant 1.0.

The showcase needs a hiring manager to see, within a minute, a paraphrase served from cache
with a real similarity score and the provider cost it avoided, and a staff engineer to be able
to read the precision/recall of that matching in `evals/results/latest.json` (ADR 0006).

## Decision

`SEMANTIC_CACHE_ENABLED=true` turns on paraphrase matching in `api/chat.py`, implemented in
`cache/semantic_match.py`:

- **Exact key first, always.** An identical repeat is served without any embedding call:
  instant, `$0.00`, `cache.match = "exact"`.
- **Embed only on an exact miss.** The final user turn is normalised and embedded with OpenAI
  `text-embedding-3-small` through the SDK already installed for chat. No new package, no new
  provider. The call has a short timeout and no retries.
- **Scope before similarity.** Candidates must share tenant (`X-Tenant-ID`, default `public`),
  model, temperature, and the exact prior conversation. Similarity applies to the current
  question only, so a long shared history cannot pull an unrelated follow-up over the threshold.
- **Bounded, in-process index.** `SEMANTIC_CACHE_MAX_ENTRIES` (default 512) entries, LRU, per
  worker, same lifetime as the memory cache. On a Redis-backed cache the index still only knows
  the prompts this worker answered; that is documented, not hidden.
- **Threshold from the eval, not by hand.** `SEMANTIC_CACHE_THRESHOLD` is set to the F1-optimal
  value from the threshold sweep in `evals/results/latest.json` and changes only with a new run.
  First run (2026-09-09, 68 pairs, `text-embedding-3-small`): F1 peaks at **0.76** (precision
  0.57, recall 0.91 on the adversarial set). `text-embedding-3-large` was measured on the same
  pairs and peaked at F1 0.69 at 0.80, within one pair of the small model at 6.5x the price per
  lookup, so the small model stays.
- **Degrade honestly.** Any embedding failure (no key, timeout, quota, network) makes the
  request behave exactly as before: exact-match lookup, provider on miss, and telemetry
  `cache.match = null`, `cache.semantic = "unavailable"`.

Telemetry is additive (ADR 0005 contract unchanged): `cache.match`, `cache.similarity` (real
cosine on a semantic hit, nearest candidate on a miss), `cache.semantic`, `cache.matched_key`,
`cache.threshold`, `cache.age_seconds`, `cost_avoided_usd` (list price of the cached usage),
and `embedding {model, tokens, latency_ms, cost_usd}`. A semantic hit's `cost_usd` is the
embedding cost it actually paid, not `$0.00`.

## Consequences

- A paraphrase can be a HIT with a score the UI can show, and every such number is observed.
- Misses on the semantic path cost one embedding call (roughly 100 to 200 ms and well under a
  millionth of a dollar each) in addition to the provider call. Exact repeats are unaffected.
- Embedding vectors are recomputed after a deploy, like the cache itself.
- The TF-IDF code in `cache/cache_key_generator.py` is no longer reachable from the demo route
  and remains only for the full-deployment cache middleware.
- Negation and entity swaps are the known weakness of embedding similarity; the cache
  paraphrase eval includes those traps on purpose, and its confusion matrix is the honest
  statement of how often they get through at the chosen threshold. At 0.76 every negation trap
  in the set is served the un-negated answer, and precision on the adversarial set is 0.57: the
  F1 optimum trades wrong hits for paraphrase recall. A production deployment would add a
  lexical guard (negation and entity agreement) or accept a higher threshold with lower recall;
  both are one env var or one function away and both would be measured by the same eval.
