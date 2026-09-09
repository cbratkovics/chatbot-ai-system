"""Latency eval: client-observed P50/P95/P99 per path, pooled from every request the other evals made.

Paths: ``hit_exact``, ``hit_semantic``, ``miss``, ``failover``, ``bypass``. Client time is measured
from the machine running the eval; server ``latency_ms`` and ``ttfb_ms`` from the telemetry sit
beside it so the network share is visible. A short dedicated block of exact repeats is added so
the hit path has enough samples.
"""

from __future__ import annotations

import random
import time
from typing import Any, Callable, Dict, List

from .client import EvalClient, Sample
from .stats import summarize


def score(samples: List[Sample]) -> Dict[str, Any]:
    paths: Dict[str, Any] = {}
    for path in ("hit_exact", "hit_semantic", "miss", "failover", "bypass"):
        subset = [s for s in samples if s.path == path]
        if not subset:
            continue
        paths[path] = {
            "n": len(subset),
            "client_ms": summarize([s.client_ms for s in subset if s.client_ms is not None]),
            "client_ttfb_ms": summarize([s.ttfb_ms for s in subset if s.ttfb_ms is not None]),
            "server_ms": summarize([s.telemetry.get("latency_ms") for s in subset if s.telemetry.get("latency_ms") is not None]),
            "server_ttfb_ms": summarize([s.telemetry.get("ttfb_ms") for s in subset if s.telemetry.get("ttfb_ms") is not None]),
            "streamed_share": round(sum(1 for s in subset if s.streamed) / len(subset), 2),
        }
    errors = [s for s in samples if s.path == "error"]
    return {
        "n": len(samples),
        "errors": len(errors),
        "paths": paths,
        "note": (
            "client_ms is wall time on the eval machine (includes network); server_ms is the backend's "
            "own measurement from the done event. Non-streamed samples have no client_ttfb_ms."
        ),
    }


def run(client: EvalClient, pooled: List[Sample], repeats: int = 10, log: Callable[[str], None] = print) -> Dict[str, Any]:
    started = time.perf_counter()
    nonce = random.randint(1000, 9999)
    # Deliberately unlike every other eval prompt so the seed is stored under its own key and the
    # repeats measure the exact-hit path rather than a semantic hit on someone else's answer.
    prompt = f"Reply with exactly three words describing the colour of a {nonce}-year-old bronze statue."
    own: List[Sample] = [client.complete(prompt, stream=True, max_tokens=40, eval="latency", role="seed")]
    log(f"  seed {own[0].path} {own[0].client_ms} ms")
    for i in range(repeats):
        s = client.complete(prompt, stream=True, max_tokens=40, eval="latency", role="repeat")
        own.append(s)
        log(f"  repeat {i + 1:>2}/{repeats} {s.path:<10} {s.client_ms or 0:>6.0f} ms ttfb={s.ttfb_ms}")
    samples = pooled + own
    return {"status": "ok", "duration_s": round(time.perf_counter() - started, 1), **score(samples), "_samples": own}
