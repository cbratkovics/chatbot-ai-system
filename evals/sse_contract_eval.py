"""SSE contract eval (ADR 0005): ``meta -> delta* -> done | error`` on every kind of request.

Runs a mix of paths (miss, exact hit, semantic hit, failover, bypass) and checks each stream
for the invariants the frontend relies on.
"""

from __future__ import annotations

import random
import time
from typing import Any, Callable, Dict, List

from .client import EvalClient, Sample

# Distinct subjects for the fresh prompts: prompts that differ only by a number are entity-swap
# traps of each other and would semantically hit one another instead of exercising the miss path.
FRESH_TOPICS = [
    "a circuit breaker", "exponential backoff", "a dead-letter queue", "an idempotency key",
    "a health check", "a canary deployment", "a token bucket", "a write-ahead log",
    "a bloom filter", "consistent hashing", "a leader election", "a saga pattern",
    "a sidecar proxy", "a service mesh", "connection pooling", "a jitter delay",
    "a feature flag", "a blue-green deployment", "a message broker", "a rate limiter",
]

CHECKS = (
    "content_type_event_stream",
    "not_gzip_encoded",  # browsers send Accept-Encoding: gzip; a gzipped stream buffers to the end
    "first_event_is_meta",
    "meta_before_any_delta",
    "exactly_one_terminal",
    "terminal_is_last",
    "done_has_usage_source",
    "done_has_cache_status",
    "delta_payloads_are_strings",
    "meta_and_done_request_id_match",
)


def check_events(sample: Sample) -> Dict[str, bool]:
    events = sample.events
    kinds = [e for e, _ in events]
    terminals = [i for i, k in enumerate(kinds) if k in ("done", "error")]
    done = next((d for e, d in events if e == "done" and isinstance(d, dict)), None)
    meta = next((d for e, d in events if e == "meta" and isinstance(d, dict)), None)
    first_delta = kinds.index("delta") if "delta" in kinds else None
    first_meta = kinds.index("meta") if "meta" in kinds else None
    has_done = done is not None
    return {
        "content_type_event_stream": sample.content_type.startswith("text/event-stream"),
        "not_gzip_encoded": sample.content_encoding.lower() != "gzip",
        "first_event_is_meta": bool(kinds) and (kinds[0] == "meta" or kinds[0] == "error"),
        "meta_before_any_delta": first_delta is None or (first_meta is not None and first_meta < first_delta),
        "exactly_one_terminal": len(terminals) == 1,
        "terminal_is_last": bool(terminals) and terminals[-1] == len(kinds) - 1,
        "done_has_usage_source": (not has_done) or (done.get("usage") or {}).get("source") in ("provider", "estimated"),
        "done_has_cache_status": (not has_done) or (done.get("cache") or {}).get("status") in ("hit", "miss", "bypass"),
        "delta_payloads_are_strings": all(isinstance(d, dict) and isinstance(d.get("content"), str) for e, d in events if e == "delta"),
        "meta_and_done_request_id_match": (not has_done) or meta is None or meta.get("request_id") == done.get("request_id"),
    }


def score(samples: List[Sample]) -> Dict[str, Any]:
    results = [check_events(s) for s in samples]
    passed = sum(1 for r in results if all(r.values()))
    return {
        "n": len(samples),
        "passed": passed,
        "pass_rate": round(passed / len(samples), 4) if samples else None,
        "checks": {name: {"passed": sum(1 for r in results if r[name]), "failed": sum(1 for r in results if not r[name])} for name in CHECKS},
        "paths": {p: sum(1 for s in samples if s.path == p) for p in sorted({s.path for s in samples})},
        "event_shapes": sorted({" ".join(dict.fromkeys(e for e, _ in s.events)) for s in samples}),
        "failures": [
            {"prompt": s.prompt, "path": s.path, "events": [e for e, _ in s.events][:12], "failed_checks": [k for k, v in r.items() if not v]}
            for s, r in zip(samples, results)
            if not all(r.values())
        ][:10],
    }


def run(client: EvalClient, n: int = 20, log: Callable[[str], None] = print) -> Dict[str, Any]:
    started = time.perf_counter()
    health = client.health()
    toggle = bool((health.get("demo") or {}).get("failure_toggle_enabled"))
    nonce = random.randint(1000, 9999)
    samples: List[Sample] = []
    base = f"In one sentence, what is a bulkhead in a resilient system? (run {nonce})"
    plan: List[Dict[str, Any]] = []
    topics = iter(FRESH_TOPICS)
    for i in range(n):
        slot = i % 5
        if slot == 0:
            plan.append({"prompt": f"In one sentence, what is {next(topics)}? (run {nonce})", "note": "fresh (miss)"})
        elif slot == 1:
            plan.append({"prompt": base, "note": "repeat (exact hit)"})
        elif slot == 2:
            plan.append({"prompt": f"Explain in a single sentence what a bulkhead means in a resilient system. (run {nonce})", "note": "paraphrase (semantic hit if enabled)"})
        elif slot == 3 and toggle:
            plan.append({"prompt": f"In one sentence, what is {next(topics)}? (run {nonce})", "simulate": True, "bypass": True, "note": "failover"})
        else:
            plan.append({"prompt": f"In one sentence, what is {next(topics)}? (run {nonce})", "bypass": True, "note": "bypass"})
    for i, step in enumerate(plan, 1):
        s = client.complete(step["prompt"], stream=True, simulate=step.get("simulate", False), bypass=step.get("bypass", False), max_tokens=120, eval="sse_contract", note=step["note"])
        samples.append(s)
        r = check_events(s)
        log(f"  sse {i:>2}/{n} {'pass' if all(r.values()) else 'FAIL ' + ','.join(k for k, v in r.items() if not v):<28} {s.path:<12} {step['note']}")
    return {"status": "ok", "duration_s": round(time.perf_counter() - started, 1), **score(samples), "_samples": samples}
