"""Run every system eval against a live backend and write the committed artifact.

    python -m evals.run --base-url http://localhost:8000
    make evals

Writes ``evals/results/latest.json`` (schema-versioned, with run timestamp, commit SHA, base URL
and request counts), ``evals/results/latest.md`` (human summary) and a copy of the JSON to
``frontend/lib/evals/latest.json`` for the /evals page's build-time fallback.

The demo guardrails allow 10 requests/min/IP and the outer limiter 100/min; a full run is ~190
requests in ~2.5 minutes, so point this at a backend started with
``DEMO_GUARDRAILS_ENABLED=false RATE_LIMIT_ENABLED=false`` (the script warns otherwise, and a
run with any failed request is written to ``last-failed.json`` instead of ``latest.json``).
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from . import SCHEMA_VERSION, cache_paraphrase_eval, failover_eval, latency_eval, sse_contract_eval
from .client import EvalClient, Sample
from .report import render_markdown

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "evals" / "results"
FRONTEND_COPY = REPO_ROOT / "frontend" / "lib" / "evals" / "latest.json"


def git(*args: str) -> str:
    """Read-only git query; empty string when git is unavailable."""
    try:
        return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=10, check=False).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def strip_samples(section: Dict[str, Any]) -> List[Sample]:
    return section.pop("_samples", []) if isinstance(section, dict) else []


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--model", default="default")
    parser.add_argument("--failover-runs", type=int, default=10)
    parser.add_argument("--sse-runs", type=int, default=20)
    parser.add_argument("--latency-repeats", type=int, default=10)
    parser.add_argument("--only", choices=["cache", "failover", "sse", "latency"], action="append", help="run a subset (repeatable)")
    parser.add_argument("--out", default=str(RESULTS_DIR / "latest.json"))
    parser.add_argument("--no-frontend-copy", action="store_true")
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args(argv)

    client = EvalClient(args.base_url, model=args.model, timeout=args.timeout)
    started = time.perf_counter()
    stamp = datetime.now(timezone.utc)
    try:
        health = client.health()
    except Exception as exc:  # noqa: BLE001
        print(f"backend unreachable at {args.base_url}: {exc}", file=sys.stderr)
        return 2
    guard = health.get("guardrails") or {}
    if guard.get("enabled", True):
        print("WARNING: demo guardrails are enabled on this backend; a full run needs ~200 requests. "
              "Start it with DEMO_GUARDRAILS_ENABLED=false.", file=sys.stderr)
    limit = health.get("rate_limit") or {}
    if limit.get("enabled", True):
        print(f"WARNING: the outer per-IP limit ({limit.get('requests')} req / {limit.get('period_seconds')} s) is on; "
              "a full run exceeds it and would record 429s. Start the backend with RATE_LIMIT_ENABLED=false.", file=sys.stderr)
    print(f"target {args.base_url} | cache {health.get('cache')} | semantic {health.get('semantic_cache')} | fallbacks {health.get('fallback_chain')}")

    only = set(args.only or ["cache", "failover", "sse", "latency"])
    pooled: List[Sample] = []
    results: Dict[str, Any] = {}

    if "cache" in only:
        print("\n== cache_paraphrase_eval")
        results["cache_paraphrase"] = cache_paraphrase_eval.run(client)
        pooled += strip_samples(results["cache_paraphrase"])
    if "failover" in only:
        print("\n== failover_eval")
        results["failover"] = failover_eval.run(client, n=args.failover_runs)
        pooled += strip_samples(results["failover"])
    if "sse" in only:
        print("\n== sse_contract_eval")
        results["sse_contract"] = sse_contract_eval.run(client, n=args.sse_runs)
        pooled += strip_samples(results["sse_contract"])
    if "latency" in only:
        print("\n== latency_eval")
        results["latency"] = latency_eval.run(client, pooled, repeats=args.latency_repeats)
        pooled += strip_samples(results["latency"])

    ok = [s for s in pooled if s.ok]
    failed = [s for s in pooled if not s.ok]
    statuses = sorted({str(s.status_code) for s in failed})
    cost = {
        "requests": client.requests,
        "estimated_usd_spent": round(sum((s.telemetry.get("cost_usd") or 0) for s in ok), 6),
        "avoided_usd": round(sum((s.telemetry.get("cost_avoided_usd") or 0) for s in ok), 6),
        "note": "list-price estimates from the telemetry of every request this run made",
    }
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "run": {
            "timestamp": stamp.isoformat(timespec="seconds"),
            "commit": git("rev-parse", "--short", "HEAD") or None,
            "commit_dirty": bool(git("status", "--porcelain")),
            "base_url": args.base_url,
            "duration_s": round(time.perf_counter() - started, 1),
            "requests": client.requests,
            "failed_requests": len(failed),
            "failed_status_codes": statuses,
            "python": platform.python_version(),
            "environment": {
                "cache": health.get("cache"),
                "semantic_cache": health.get("semantic_cache"),
                "default_model": health.get("default_model"),
                "fallback_chain": health.get("fallback_chain"),
                "guardrails_enabled": guard.get("enabled"),
                "streaming": health.get("streaming"),
            },
        },
        **results,
        "cost": cost,
        "samples": [s.to_dict() for s in pooled],
    }
    client.close()

    out = Path(args.out)
    if failed:
        # Never let a broken run masquerade as the committed artifact.
        out = out.with_name("last-failed.json")
        args.no_frontend_copy = True
        print(f"\nERROR: {len(failed)} of {client.requests} requests failed (status {', '.join(statuses) or 'n/a'}); "
              f"writing {out.name} instead of latest.json", file=sys.stderr)
        for s in failed[:5]:
            print(f"  {s.status_code} {s.error} :: {s.prompt[:60]}", file=sys.stderr)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n")
    md = out.with_suffix(".md")
    md.write_text(render_markdown(artifact))
    written = [out, md]
    if not args.no_frontend_copy:
        FRONTEND_COPY.parent.mkdir(parents=True, exist_ok=True)
        slim = {k: v for k, v in artifact.items() if k != "samples"}
        FRONTEND_COPY.write_text(json.dumps(slim, indent=2, ensure_ascii=False) + "\n")
        written.append(FRONTEND_COPY)

    print("\n" + render_markdown(artifact, brief=True))
    print("written:", ", ".join(str(p.relative_to(REPO_ROOT)) for p in written))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
