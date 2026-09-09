"""Failover eval: with the primary forced down, does the fallback answer, and what does it cost in time?

Each run streams a fresh prompt with the ``X-Demo-Simulate-Failure`` header and
``Cache-Control: no-cache`` so the provider chain always executes. A run passes when every
check below holds. Added latency compares against baseline streams of different fresh prompts
sent without the header, so both sides are real provider calls.
"""

from __future__ import annotations

import random
import time
from typing import Any, Callable, Dict, List

from .client import EvalClient, Sample
from .stats import summarize

FAILURE_MODES = ["a quota exhaustion", "a rate limit", "a timeout", "a malformed response", "an auth error",
                 "a model deprecation", "a partial stream", "a network partition", "a content filter", "a 5xx outage"]
PRINCIPLES = ["timeouts", "retries with jitter", "circuit breaking", "graceful degradation", "idempotency",
              "bulkheads", "observability", "backpressure", "fail-fast validation", "health checks"]

CHECKS = (
    "fallback_answered",  # telemetry.failover True and last attempt ok
    "primary_recorded_failed",  # attempts[0] failed with 503 simulated_outage
    "fallback_is_different_provider",
    "first_token_delivered",  # at least one delta and a client ttfb
    "done_event_received",
    "content_non_empty",
)


def check_sample(s: Sample) -> Dict[str, bool]:
    t = s.telemetry or {}
    attempts = t.get("attempts") or []
    first, last = (attempts[0] if attempts else {}), (attempts[-1] if attempts else {})
    return {
        "fallback_answered": bool(t.get("failover")) and last.get("outcome") == "ok",
        "primary_recorded_failed": first.get("outcome") == "failed" and first.get("status_code") == 503 and first.get("error_code") == "simulated_outage",
        "fallback_is_different_provider": bool(first) and bool(last) and first.get("provider") != last.get("provider"),
        "first_token_delivered": s.ttfb_ms is not None and any(e == "delta" for e, _ in s.events),
        "done_event_received": bool(s.events) and s.events[-1][0] == "done",
        "content_non_empty": bool(s.content.strip()),
    }


def score(samples: List[Sample], baseline: List[Sample]) -> Dict[str, Any]:
    results = [check_sample(s) for s in samples]
    passed = sum(1 for r in results if all(r.values()))
    checks = {name: {"passed": sum(1 for r in results if r[name]), "failed": sum(1 for r in results if not r[name])} for name in CHECKS}
    fo_ttfb = summarize([s.ttfb_ms for s in samples if s.ttfb_ms is not None])
    fo_total = summarize([s.client_ms for s in samples if s.client_ms is not None])
    base_ttfb = summarize([s.ttfb_ms for s in baseline if s.ttfb_ms is not None])
    base_total = summarize([s.client_ms for s in baseline if s.client_ms is not None])
    primary_fail_ms = [
        (s.telemetry.get("attempts") or [{}])[0].get("latency_ms") for s in samples if s.ok
    ]
    fallback = next((s for s in samples if s.ok and s.telemetry.get("failover")), None)
    diff = lambda a, b: None if a["p50"] is None or b["p50"] is None else round(a["p50"] - b["p50"], 1)  # noqa: E731
    return {
        "n": len(samples),
        "passed": passed,
        "success_rate": round(passed / len(samples), 4) if samples else None,
        "checks": checks,
        "fallback_provider": fallback.telemetry.get("provider") if fallback else None,
        "fallback_model": fallback.telemetry.get("model") if fallback else None,
        "latency_ms": {
            "failover": {"ttfb": fo_ttfb, "total": fo_total},
            "baseline": {"ttfb": base_ttfb, "total": base_total},
            "added_ttfb_p50": diff(fo_ttfb, base_ttfb),
            "added_total_p50": diff(fo_total, base_total),
            "simulated_primary_failure_ms": summarize([x for x in primary_fail_ms if x is not None]),
            "note": (
                "Client-observed from the machine that ran the eval. The simulated outage fails "
                "before the primary is called, so 'added' latency is the fallback provider's own "
                "speed relative to the primary's, not a timeout wait."
            ),
        },
        "failures": [
            {"prompt": s.prompt, "error": s.error, "failed_checks": [k for k, v in r.items() if not v]}
            for s, r in zip(samples, results)
            if not all(r.values())
        ][:10],
    }


def run(client: EvalClient, n: int = 10, log: Callable[[str], None] = print) -> Dict[str, Any]:
    health = client.health()
    if not (health.get("demo") or {}).get("failure_toggle_enabled"):
        return {"status": "skipped", "reason": "DEMO_FAILURE_TOGGLE_ENABLED is off on this backend", "n": n}
    if not health.get("fallback_chain"):
        return {"status": "skipped", "reason": "no fallback chain configured", "n": n}
    started = time.perf_counter()
    nonce = random.randint(1000, 9999)
    samples, baseline = [], []
    for i in range(n):
        prompt = f"In two sentences, describe {FAILURE_MODES[i % len(FAILURE_MODES)]} as a failure mode of an LLM provider call. (run {nonce})"
        s = client.complete(prompt, stream=True, simulate=True, bypass=True, max_tokens=200, eval="failover", role="failover")
        samples.append(s)
        r = check_sample(s)
        log(f"  failover {i + 1:>2}/{n} {'pass' if all(r.values()) else 'FAIL ' + ','.join(k for k, v in r.items() if not v)} {s.client_ms or 0:>6.0f} ms ttfb={s.ttfb_ms}")
    for i in range(n):
        prompt = f"In two sentences, describe {PRINCIPLES[i % len(PRINCIPLES)]} as a design principle of a resilient API. (run {nonce})"
        s = client.complete(prompt, stream=True, bypass=True, max_tokens=200, eval="failover", role="baseline")
        baseline.append(s)
        log(f"  baseline {i + 1:>2}/{n} {s.path:<8} {s.client_ms or 0:>6.0f} ms ttfb={s.ttfb_ms}")
    return {
        "status": "ok",
        "duration_s": round(time.perf_counter() - started, 1),
        "fallback_chain": health.get("fallback_chain"),
        **score(samples, baseline),
        "_samples": samples + baseline,
    }
