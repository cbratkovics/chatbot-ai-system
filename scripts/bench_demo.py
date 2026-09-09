#!/usr/bin/env python3
"""Hit the live demo API with repeated prompts and report what the telemetry says.

Every number in the README's "Measured on the live demo" table must come from this script's
output file. It uses only the public JSON endpoint and the telemetry the API already returns.

    poetry run python scripts/bench_demo.py                       # 20 requests, default prompts
    poetry run python scripts/bench_demo.py --base-url http://localhost:8000 --runs 40 --rpm 60
    poetry run python scripts/bench_demo.py --simulate-failure    # needs DEMO_FAILURE_TOGGLE_ENABLED

Pacing: the demo guardrails allow 10 requests/min/IP, so the default --rpm is 9. Point it at
your own instance with the limits raised for a faster run.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import httpx

DEFAULT_BASE_URL = "https://chatbot-ai-system.onrender.com"
DEFAULT_PROMPTS = [
    "In one sentence, what does a semantic cache do?",
    "Name three failure modes of an LLM provider call.",
    "What is the difference between P50 and P95 latency?",
    "Explain circuit breakers to a junior engineer in two sentences.",
    "Why would a chatbot fail over to a second provider?",
]


def percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((pct / 100) * (len(ordered) - 1))))
    return ordered[index]


def run(args: argparse.Namespace) -> Dict[str, Any]:
    base = args.base_url.rstrip("/")
    url = f"{base}/api/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if args.simulate_failure:
        headers["X-Demo-Simulate-Failure"] = "1"
    interval = 60.0 / args.rpm if args.rpm > 0 else 0.0

    samples: List[Dict[str, Any]] = []
    with httpx.Client(timeout=args.timeout) as client:
        health = client.get(f"{base}/api/v1/chat/health").json()
        print(f"target: {base}")
        print(f"cache backend: {health.get('cache')} | default model: {health.get('default_model')} | "
              f"fallbacks: {health.get('fallback_chain')}")
        for i in range(args.runs):
            prompt = DEFAULT_PROMPTS[i % len(DEFAULT_PROMPTS)]
            body = {"model": args.model, "messages": [{"role": "user", "content": prompt}], "stream": False}
            started = time.perf_counter()
            try:
                res = client.post(url, json=body, headers=headers)
                client_ms = (time.perf_counter() - started) * 1000
                data = res.json()
            except Exception as exc:  # noqa: BLE001 - record and keep going
                samples.append({"i": i, "prompt": prompt, "status": None, "error": str(exc)})
                print(f"[{i + 1:>2}/{args.runs}] network error: {exc}")
                continue
            telemetry = data.get("telemetry") or {}
            sample = {
                "i": i,
                "prompt": prompt,
                "status": res.status_code,
                "client_ms": round(client_ms, 1),
                "server_ms": telemetry.get("latency_ms"),
                "provider": telemetry.get("provider"),
                "model": telemetry.get("model"),
                "cache": (telemetry.get("cache") or {}).get("status"),
                "failover": telemetry.get("failover", False),
                "simulated": telemetry.get("simulated_failure", False),
                "tokens": (telemetry.get("usage") or {}).get("total_tokens"),
                "cost_usd": telemetry.get("cost_usd"),
                "error": (data.get("error") or {}).get("code") if res.status_code >= 400 else None,
            }
            samples.append(sample)
            print(
                f"[{i + 1:>2}/{args.runs}] {res.status_code} {sample['cache'] or '-':<6} "
                f"{sample['provider'] or '-':<8} {round(client_ms):>6} ms"
                f"{'  FAILOVER' if sample['failover'] else ''}{'  ' + sample['error'] if sample['error'] else ''}"
            )
            if interval and i < args.runs - 1:
                time.sleep(interval)

    ok = [s for s in samples if s.get("status") == 200]
    hits = [s for s in ok if s["cache"] == "hit"]
    misses = [s for s in ok if s["cache"] in ("miss", "bypass")]
    client_all = [s["client_ms"] for s in ok]
    client_hit = [s["client_ms"] for s in hits]
    client_miss = [s["client_ms"] for s in misses]
    providers: Dict[str, int] = {}
    for s in ok:
        providers[s["provider"] or "unknown"] = providers.get(s["provider"] or "unknown", 0) + 1

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_url": base,
        "model_requested": args.model,
        "runs": args.runs,
        "distinct_prompts": len(DEFAULT_PROMPTS),
        "rpm": args.rpm,
        "simulate_failure": args.simulate_failure,
        "cache_backend": health.get("cache"),
        "requests_ok": len(ok),
        "requests_failed": len(samples) - len(ok),
        "cache_hit_rate": round(len(hits) / len(ok), 3) if ok else None,
        "latency_ms": {
            "all": {"p50": round(statistics.median(client_all), 1) if client_all else None, "p95": round(percentile(client_all, 95), 1) if client_all else None},
            "cache_hit": {"p50": round(statistics.median(client_hit), 1) if client_hit else None, "p95": round(percentile(client_hit, 95), 1) if client_hit else None},
            "cache_miss": {"p50": round(statistics.median(client_miss), 1) if client_miss else None, "p95": round(percentile(client_miss, 95), 1) if client_miss else None},
            "note": "client-observed wall time from this machine; server latency_ms is per sample",
        },
        "failover_count": sum(1 for s in ok if s["failover"]),
        "simulated_failover_count": sum(1 for s in ok if s["simulated"]),
        "providers": providers,
        "estimated_cost_usd": round(sum(s["cost_usd"] or 0 for s in ok), 6),
        "samples": samples,
    }
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--rpm", type=float, default=9.0, help="requests per minute (0 = no pacing)")
    parser.add_argument("--model", default="default")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--simulate-failure", action="store_true")
    parser.add_argument("--out", default="benchmarks/results/bench_demo_latest.json")
    args = parser.parse_args()

    summary = run(args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2))

    lat = summary["latency_ms"]
    print("\nSummary")
    print(f"  requests ok/failed : {summary['requests_ok']}/{summary['requests_failed']}")
    print(f"  cache hit rate     : {summary['cache_hit_rate']}")
    print(f"  latency all  p50/p95: {lat['all']['p50']} / {lat['all']['p95']} ms")
    print(f"  latency hit  p50/p95: {lat['cache_hit']['p50']} / {lat['cache_hit']['p95']} ms")
    print(f"  latency miss p50/p95: {lat['cache_miss']['p50']} / {lat['cache_miss']['p95']} ms")
    print(f"  failovers          : {summary['failover_count']} (simulated: {summary['simulated_failover_count']})")
    print(f"  providers          : {summary['providers']}")
    print(f"  est. cost          : ${summary['estimated_cost_usd']}")
    print(f"  written            : {out}")
    return 0 if summary["requests_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
