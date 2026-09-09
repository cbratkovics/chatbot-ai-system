# System evals: last benchmark run

- **Run:** 2026-09-09T10:57:49+00:00 · commit `9ccfc09` (dirty tree) · 187 requests in 149.4 s · 0 failed
- **Target:** `http://localhost:8000` · cache `memory` · semantic `openai-embeddings` (text-embedding-3-small) · fallbacks `['groq:openai/gpt-oss-20b']`
- **Cost of this run:** $0.003755 spent, $0.002419 avoided (list prices from telemetry)

Every number below was observed from real requests made by `python -m evals.run`. Regenerate with `make evals`.

## Cache paraphrase eval

68 labelled pairs (`evals/data/cache_pairs.jsonl`), embeddings `text-embedding-3-small`, scored at threshold **0.76**. 6 seed prompts already hit an earlier seed; their probes are scored against that entry.

| Precision | Recall | F1 | TP | FP | FN | TN |
|---|---|---|---|---|---|---|
| 56.6% | 90.9% | 0.698 | 30 | 23 | 3 | 12 |

By kind:

| Kind | n | TP | FP | FN | TN | Precision | Recall |
|---|---|---|---|---|---|---|---|
| entity | 10 | 0 | 3 | 0 | 7 | 0.0% | n/a |
| intent | 15 | 0 | 10 | 0 | 5 | 0.0% | n/a |
| negation | 10 | 0 | 10 | 0 | 0 | 0.0% | n/a |
| normalisation | 3 | 3 | 0 | 0 | 0 | 100.0% | 100.0% |
| paraphrase | 30 | 27 | 0 | 3 | 0 | 100.0% | 90.0% |

Threshold sweep (best F1 at **0.76**):

| Threshold | Precision | Recall | F1 | FP | FN |
|---|---|---|---|---|---|
| 0.70 | 50.8% | 93.8% | 0.659 | 29 | 2 |
| 0.71 | 50.8% | 93.8% | 0.659 | 29 | 2 |
| 0.72 | 51.7% | 93.8% | 0.667 | 28 | 2 |
| 0.73 | 52.6% | 93.8% | 0.674 | 27 | 2 |
| 0.74 | 55.6% | 90.9% | 0.690 | 24 | 3 |
| 0.75 | 55.6% | 90.9% | 0.690 | 24 | 3 |
| 0.76 | 56.6% | 90.9% | 0.698 | 23 | 3 |
| 0.77 | 56.9% | 87.9% | 0.691 | 22 | 4 |
| 0.78 | 56.2% | 81.8% | 0.667 | 21 | 6 |
| 0.79 | 57.5% | 81.8% | 0.675 | 20 | 6 |
| 0.80 | 57.8% | 78.8% | 0.667 | 19 | 7 |
| 0.81 | 57.8% | 78.8% | 0.667 | 19 | 7 |
| 0.82 | 55.8% | 72.7% | 0.632 | 19 | 9 |
| 0.83 | 57.5% | 69.7% | 0.630 | 17 | 10 |
| 0.84 | 59.0% | 69.7% | 0.639 | 16 | 10 |
| 0.85 | 56.8% | 63.6% | 0.600 | 16 | 12 |
| 0.86 | 56.8% | 63.6% | 0.600 | 16 | 12 |
| 0.87 | 60.0% | 63.6% | 0.618 | 14 | 12 |
| 0.88 | 61.3% | 57.6% | 0.594 | 12 | 14 |
| 0.89 | 61.3% | 57.6% | 0.594 | 12 | 14 |
| 0.90 | 62.1% | 54.5% | 0.581 | 11 | 15 |
| 0.91 | 60.0% | 45.5% | 0.517 | 10 | 18 |
| 0.92 | 55.0% | 33.3% | 0.415 | 9 | 22 |
| 0.93 | 64.3% | 27.3% | 0.383 | 5 | 24 |
| 0.94 | 44.4% | 12.1% | 0.191 | 5 | 29 |
| 0.95 | 50.0% | 9.1% | 0.154 | 3 | 30 |
| 0.96 | 50.0% | 3.0% | 0.057 | 1 | 32 |
| 0.97 | 100.0% | 3.0% | 0.059 | 0 | 32 |
| 0.98 | 100.0% | 3.0% | 0.059 | 0 | 32 |
| 0.99 | 100.0% | 3.0% | 0.059 | 0 | 32 |

_Re-scored offline from each probe's nearest-candidate similarity as recorded at the run threshold. At another threshold the set of stored probes would differ slightly, so the sweep is an estimate; the row at the run threshold is exact._

Examples:

| Pair | Kind | Similarity | Outcome |
|---|---|---|---|
| “What is the difference between P50 and P95 latency?” → “How do P50 and P95 latency differ?” | paraphrase | 0.956 | true_positive |
| “What does a semantic cache do?” → “Explain what semantic caching does.” | paraphrase | 0.912 | true_positive |
| “Summarize the benefits of semantic caching in two sentences.” → “List the drawbacks of semantic caching in two sentences.” | intent | 0.736 | true_negative |
| “How many tokens are in a typical English sentence?” → “How many characters are in a typical English sentence?” | intent | 0.725 | true_negative |
| “What should a semantic cache store?” → “What should a semantic cache not store?” | negation | 0.828 | false_positive |

## Failover eval

10/10 runs passed every check (**100.0%**). Fallback answered by `groq · openai/gpt-oss-20b`.

| Check | Passed | Failed |
|---|---|---|
| fallback_answered | 10 | 0 |
| primary_recorded_failed | 10 | 0 |
| fallback_is_different_provider | 10 | 0 |
| first_token_delivered | 10 | 0 |
| done_event_received | 10 | 0 |
| content_non_empty | 10 | 0 |

| Latency (client-observed) | Failover p50 | Baseline p50 | Added |
|---|---|---|---|
| time to first token | 374 ms | 732 ms | -359 ms |
| total | 451 ms | 1137 ms | -686 ms |

_Client-observed from the machine that ran the eval. The simulated outage fails before the primary is called, so 'added' latency is the fallback provider's own speed relative to the primary's, not a timeout wait._

## SSE contract eval

20/20 streams passed every check (**100.0%**) across paths {'bypass': 4, 'failover': 4, 'hit_exact': 3, 'hit_semantic': 4, 'miss': 5}.

| Check | Passed | Failed |
|---|---|---|
| content_type_event_stream | 20 | 0 |
| not_gzip_encoded | 20 | 0 |
| first_event_is_meta | 20 | 0 |
| meta_before_any_delta | 20 | 0 |
| exactly_one_terminal | 20 | 0 |
| terminal_is_last | 20 | 0 |
| done_has_usage_source | 20 | 0 |
| done_has_cache_status | 20 | 0 |
| delta_payloads_are_strings | 20 | 0 |
| meta_and_done_request_id_match | 20 | 0 |

Event shapes seen: `meta delta done`

## Latency by path

| Path | n | client p50 | client p95 | client p99 | client TTFB p50 | server p50 |
|---|---|---|---|---|---|---|
| hit_exact | 14 | 2 ms | 3 ms | 14 ms | 2 ms | 0 ms |
| hit_semantic | 62 | 207 ms | 293 ms | 391 ms | 226 ms | 205 ms |
| miss | 83 | 1228 ms | 2173 ms | 2612 ms | 1070 ms | 1225 ms |
| failover | 14 | 444 ms | 515 ms | 904 ms | 398 ms | 442 ms |
| bypass | 14 | 1126 ms | 1776 ms | 2153 ms | 732 ms | 1124 ms |

_client_ms is wall time on the eval machine (includes network); server_ms is the backend's own measurement from the done event. Non-streamed samples have no client_ttfb_ms._
