"""Pure scoring helpers shared by the evals, ``scripts/bench_demo.py`` and the tests."""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Sequence


def percentile(values: Sequence[float], pct: float) -> Optional[float]:
    """Nearest-rank percentile: index = round-half-up((pct/100) * (n-1)) into the sorted values.

    Half-up on purpose: JavaScript's ``Math.round`` rounds .5 up while Python's ``round`` is
    banker's rounding, and the frontend's ``percentile`` in ``sessionStats.ts`` must agree with
    this function so the rail, the README and the evals never disagree on a tie.
    """
    if not values:
        return None
    ordered = sorted(values)
    position = (pct / 100) * (len(ordered) - 1)
    index = min(len(ordered) - 1, max(0, math.floor(position + 0.5)))
    return ordered[index]


def summarize(values: Sequence[float], digits: int = 1) -> Dict[str, Any]:
    """n, p50, p95, p99, min, max, mean for a latency series (None when empty)."""
    vals = [v for v in values if v is not None]
    if not vals:
        return {"n": 0, "p50": None, "p95": None, "p99": None, "min": None, "max": None, "mean": None}
    return {
        "n": len(vals),
        "p50": round(percentile(vals, 50) or 0.0, digits),
        "p95": round(percentile(vals, 95) or 0.0, digits),
        "p99": round(percentile(vals, 99) or 0.0, digits),
        "min": round(min(vals), digits),
        "max": round(max(vals), digits),
        "mean": round(sum(vals) / len(vals), digits),
    }


def confusion(outcomes: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    """Count tp/fp/fn/tn from records carrying ``expected_hit`` and ``predicted_hit`` booleans.

    A predicted hit that retrieved the *wrong* entry (``correct_entry`` False) is a false
    positive even when the pair was labelled should-hit: the cache returned somebody else's answer.
    """
    counts = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
    for o in outcomes:
        expected, predicted = bool(o["expected_hit"]), bool(o["predicted_hit"])
        correct_entry = o.get("correct_entry", True)
        if predicted and expected and correct_entry:
            counts["tp"] += 1
        elif predicted:
            counts["fp"] += 1
        elif expected:
            counts["fn"] += 1
        else:
            counts["tn"] += 1
    return counts


def prf(counts: Dict[str, int]) -> Dict[str, Optional[float]]:
    tp, fp, fn = counts["tp"], counts["fp"], counts["fn"]
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (2 * precision * recall / (precision + recall)) if precision and recall else (0.0 if precision is not None or recall is not None else None)
    r = lambda x: None if x is None else round(x, 4)  # noqa: E731
    return {"precision": r(precision), "recall": r(recall), "f1": r(f1)}


def sweep(
    pairs: Iterable[Dict[str, Any]], thresholds: Sequence[float]
) -> List[Dict[str, Any]]:
    """Re-score the recorded pairs at each threshold.

    Each pair carries ``expected_hit``, the nearest candidate's ``similarity`` (None when the
    index had no candidate) and ``nearest_is_own`` (whether that candidate was the pair's own
    seed). Predicted hit at threshold t is ``similarity >= t``; it is a correct retrieval only
    when the nearest entry is the pair's own seed.
    """
    pairs = list(pairs)
    rows = []
    for t in thresholds:
        outcomes = []
        for p in pairs:
            sim = p.get("similarity")
            predicted = sim is not None and sim >= t
            outcomes.append(
                {
                    "expected_hit": p["expected_hit"],
                    "predicted_hit": predicted,
                    "correct_entry": p.get("nearest_is_own", True),
                }
            )
        counts = confusion(outcomes)
        rows.append({"threshold": round(t, 2), **counts, **prf(counts)})
    return rows


def best_threshold(rows: Sequence[Dict[str, Any]]) -> Optional[float]:
    """Highest F1; ties go to the *higher* threshold because a wrong cache hit costs more than a miss."""
    scored = [r for r in rows if r.get("f1") is not None]
    if not scored:
        return None
    top = max(r["f1"] for r in scored)
    return max(r["threshold"] for r in scored if r["f1"] == top)


def frange(start: float, stop: float, step: float) -> List[float]:
    out, x = [], start
    while x <= stop + 1e-9:
        out.append(round(x, 4))
        x += step
    return out
