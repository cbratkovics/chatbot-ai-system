"""Markdown rendering of the eval artifact (``latest.md`` and the console summary)."""

from __future__ import annotations

from typing import Any, Dict, Optional


def pct(x: Optional[float]) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def ms(x: Optional[float]) -> str:
    return "n/a" if x is None else f"{x:.0f} ms"


def num(x: Optional[float], digits: int = 3) -> str:
    return "n/a" if x is None else f"{x:.{digits}f}"


def render_markdown(a: Dict[str, Any], brief: bool = False) -> str:
    run = a["run"]
    env = run.get("environment", {})
    lines = [
        "# System evals: last benchmark run",
        "",
        f"- **Run:** {run['timestamp']} · commit `{run.get('commit') or 'unknown'}`{' (dirty tree)' if run.get('commit_dirty') else ''} · {run.get('requests')} requests in {run.get('duration_s')} s"
        + (f" · **{run['failed_requests']} failed (status {', '.join(run.get('failed_status_codes') or [])})**" if run.get('failed_requests') else " · 0 failed"),
        f"- **Target:** `{run['base_url']}` · cache `{env.get('cache')}` · semantic `{(env.get('semantic_cache') or {}).get('backend')}` ({(env.get('semantic_cache') or {}).get('embedding_model')}) · fallbacks `{env.get('fallback_chain')}`",
        f"- **Cost of this run:** ${a.get('cost', {}).get('estimated_usd_spent')} spent, ${a.get('cost', {}).get('avoided_usd')} avoided (list prices from telemetry)",
        "",
        "Every number below was observed from real requests made by `python -m evals.run`. Regenerate with `make evals`.",
        "",
    ]
    c = a.get("cache_paraphrase")
    if c:
        lines += ["## Cache paraphrase eval", ""]
        if c.get("status") != "ok":
            lines += [f"Skipped: {c.get('reason')}", ""]
        else:
            lines += [
                f"{c['n_pairs']} labelled pairs (`{c.get('dataset')}`), embeddings `{c.get('embedding_model')}`, scored at threshold **{c['threshold']}**."
                + (f" {c['seed_hits']} seed prompts already hit an earlier seed; their probes are scored against that entry." if c.get('seed_hits') else ""),
                "",
                "| Precision | Recall | F1 | TP | FP | FN | TN |",
                "|---|---|---|---|---|---|---|",
                f"| {pct(c['precision'])} | {pct(c['recall'])} | {num(c['f1'])} | {c['tp']} | {c['fp']} | {c['fn']} | {c['tn']} |",
                "",
                "By kind:",
                "",
                "| Kind | n | TP | FP | FN | TN | Precision | Recall |",
                "|---|---|---|---|---|---|---|---|",
            ]
            for kind, k in c["by_kind"].items():
                lines.append(f"| {kind} | {k['n']} | {k['tp']} | {k['fp']} | {k['fn']} | {k['tn']} | {pct(k['precision'])} | {pct(k['recall'])} |")
            lines += ["", f"Threshold sweep (best F1 at **{c.get('best_threshold_by_f1')}**):", "", "| Threshold | Precision | Recall | F1 | FP | FN |", "|---|---|---|---|---|---|"]
            rows = c["sweep"] if not brief else [r for r in c["sweep"] if round(r["threshold"] * 100) % 5 == 0 or r["threshold"] == c.get("best_threshold_by_f1")]
            for r in rows:
                lines.append(f"| {r['threshold']:.2f} | {pct(r['precision'])} | {pct(r['recall'])} | {num(r['f1'])} | {r['fp']} | {r['fn']} |")
            lines += ["", f"_{c.get('sweep_note')}_", "", "Examples:", "", "| Pair | Kind | Similarity | Outcome |", "|---|---|---|---|"]
            for e in c.get("examples", []):
                lines.append(f"| “{e['a']}” → “{e['b']}” | {e['kind']} | {num(e.get('similarity'), 3) if e.get('similarity') is not None else 'no candidate'} | {e['outcome']} |")
            lines.append("")
    f = a.get("failover")
    if f:
        lines += ["## Failover eval", ""]
        if f.get("status") != "ok":
            lines += [f"Skipped: {f.get('reason')}", ""]
        else:
            lat = f["latency_ms"]
            lines += [
                f"{f['passed']}/{f['n']} runs passed every check (**{pct(f['success_rate'])}**). Fallback answered by `{f.get('fallback_provider')} · {f.get('fallback_model')}`.",
                "",
                "| Check | Passed | Failed |",
                "|---|---|---|",
            ]
            for name, k in f["checks"].items():
                lines.append(f"| {name} | {k['passed']} | {k['failed']} |")
            lines += [
                "",
                "| Latency (client-observed) | Failover p50 | Baseline p50 | Added |",
                "|---|---|---|---|",
                f"| time to first token | {ms(lat['failover']['ttfb']['p50'])} | {ms(lat['baseline']['ttfb']['p50'])} | {ms(lat['added_ttfb_p50'])} |",
                f"| total | {ms(lat['failover']['total']['p50'])} | {ms(lat['baseline']['total']['p50'])} | {ms(lat['added_total_p50'])} |",
                "",
                f"_{lat['note']}_",
                "",
            ]
    s = a.get("sse_contract")
    if s:
        lines += ["## SSE contract eval", ""]
        if s.get("status") != "ok":
            lines += [f"Skipped: {s.get('reason')}", ""]
        else:
            lines += [f"{s['passed']}/{s['n']} streams passed every check (**{pct(s['pass_rate'])}**) across paths {s['paths']}.", "", "| Check | Passed | Failed |", "|---|---|---|"]
            for name, k in s["checks"].items():
                lines.append(f"| {name} | {k['passed']} | {k['failed']} |")
            lines += ["", f"Event shapes seen: {', '.join('`' + e + '`' for e in s['event_shapes'])}", ""]
    lt = a.get("latency")
    if lt and lt.get("status") == "ok":
        lines += ["## Latency by path", "", "| Path | n | client p50 | client p95 | client p99 | client TTFB p50 | server p50 |", "|---|---|---|---|---|---|---|"]
        for path, p in lt["paths"].items():
            lines.append(f"| {path} | {p['n']} | {ms(p['client_ms']['p50'])} | {ms(p['client_ms']['p95'])} | {ms(p['client_ms']['p99'])} | {ms(p['client_ttfb_ms']['p50'])} | {ms(p['server_ms']['p50'])} |")
        lines += ["", f"_{lt['note']}_", ""]
    return "\n".join(lines)
