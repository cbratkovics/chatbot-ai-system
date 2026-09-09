"""Cache paraphrase eval: does the semantic cache serve the right answer, and only then?

Procedure, all against a live backend:

1. ``DELETE /chat/cache`` so the run starts from an empty cache and index.
2. Seed every pair's ``a`` prompt (one provider call each). Its response ``cache_key`` is the
   entry the pair's ``b`` prompt should retrieve.
3. Send every ``b`` prompt. The telemetry says whether it hit, which entry it matched
   (``cache.matched_key``), the nearest indexed prompt even on a miss (``cache.nearest_key``)
   and that candidate's cosine similarity.
4. Score at the backend's configured threshold: a hit is only a true positive when it
   retrieved the pair's own seed. Then re-score offline across a threshold sweep using the
   recorded nearest-candidate similarity.

Labels: ``paraphrase`` and ``normalisation`` pairs should hit; ``intent`` (same words, different
ask), ``negation`` and ``entity`` swaps should miss. The traps are the honest part: embedding
similarity is known to be weak on negation, and the confusion matrix says how weak.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .client import EvalClient, Sample
from .stats import best_threshold, confusion, frange, prf, sweep

DATASET = Path(__file__).resolve().parent / "data" / "cache_pairs.jsonl"
SEED_MAX_TOKENS = 60  # keeps seeding cheap; the cache stores whatever the provider answered


def load_pairs(path: Path = DATASET) -> List[Dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def dataset_digest(path: Path = DATASET) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def score_pairs(records: List[Dict[str, Any]], threshold: Optional[float], sweep_range=(0.70, 0.99, 0.01)) -> Dict[str, Any]:
    """Pure scoring over recorded pair outcomes (unit-tested with fixture data)."""
    outcomes = [
        {
            "expected_hit": r["expected_hit"],
            "predicted_hit": r["predicted_hit"],
            "correct_entry": r["correct_entry"],
        }
        for r in records
    ]
    counts = confusion(outcomes)
    by_kind: Dict[str, Dict[str, Any]] = {}
    for kind in sorted({r["kind"] for r in records}):
        subset = [o for o, r in zip(outcomes, records) if r["kind"] == kind]
        c = confusion(subset)
        by_kind[kind] = {"n": len(subset), **c, **prf(c)}
    rows = sweep(
        [
            {"expected_hit": r["expected_hit"], "similarity": r["similarity"], "nearest_is_own": r["nearest_is_own"]}
            for r in records
        ],
        frange(*sweep_range),
    )
    return {
        "n_pairs": len(records),
        "threshold": threshold,
        **counts,
        **prf(counts),
        "by_kind": by_kind,
        "sweep": rows,
        "best_threshold_by_f1": best_threshold(rows),
        "sweep_note": (
            "Re-scored offline from each probe's nearest-candidate similarity as recorded at the run "
            "threshold. At another threshold the set of stored probes would differ slightly, so the "
            "sweep is an estimate; the row at the run threshold is exact."
        ),
    }


def pick_examples(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """2 true hits, 2 correct misses, 1 trap (a slipped-through negation/entity swap if any)."""
    def take(pred: Callable[[Dict[str, Any]], bool], n: int) -> List[Dict[str, Any]]:
        return [r for r in records if pred(r)][:n]

    hits = take(lambda r: r["expected_hit"] and r["predicted_hit"] and r["correct_entry"], 2)
    misses = take(lambda r: not r["expected_hit"] and not r["predicted_hit"] and r["kind"] == "intent", 2)
    trap = take(lambda r: r["kind"] in ("negation", "entity") and r["predicted_hit"], 1) or take(
        lambda r: r["kind"] in ("negation", "entity"), 1
    )
    keys = ("id", "kind", "label", "a", "b", "similarity", "predicted_hit", "correct_entry", "outcome")
    return [{k: r.get(k) for k in keys} for r in hits + misses + trap]


def outcome_label(r: Dict[str, Any]) -> str:
    if r["predicted_hit"] and r["expected_hit"] and r["correct_entry"]:
        return "true_positive"
    if r["predicted_hit"]:
        return "false_positive"
    return "false_negative" if r["expected_hit"] else "true_negative"


def run(client: EvalClient, log: Callable[[str], None] = print, pairs: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    pairs = pairs or load_pairs()
    health = client.health()
    semantic = health.get("semantic_cache") or {}
    threshold = semantic.get("threshold")
    if not semantic.get("enabled") or semantic.get("backend") is None:
        return {"status": "skipped", "reason": f"semantic cache unavailable on this backend: {semantic}", "n_pairs": len(pairs)}

    started = time.perf_counter()
    client.clear_cache()
    log(f"cache cleared; seeding {len(pairs)} prompts")
    seeds: Dict[str, Sample] = {}
    samples: List[Sample] = []
    for i, p in enumerate(pairs, 1):
        s = client.complete(p["a"], max_tokens=SEED_MAX_TOKENS, eval="cache_paraphrase", role="seed", pair=p["id"])
        seeds[p["id"]] = s
        samples.append(s)
        log(f"  seed {i:>2}/{len(pairs)} {s.path:<12} {s.client_ms or 0:>6.0f} ms  {p['a'][:60]}")

    log("probing paraphrases")
    records: List[Dict[str, Any]] = []
    for i, p in enumerate(pairs, 1):
        seed = seeds[p["id"]]
        s = client.complete(p["b"], max_tokens=SEED_MAX_TOKENS, eval="cache_paraphrase", role="probe", pair=p["id"])
        samples.append(s)
        cache = s.telemetry.get("cache") or {}
        predicted = cache.get("status") == "hit"
        matched = cache.get("matched_key")
        nearest = cache.get("nearest_key") or matched
        # A seed can itself hit an earlier seed (near-duplicate prompts across pairs); its answer
        # then lives under that entry's key, which is what the probe should retrieve.
        seed_cache = seed.telemetry.get("cache") or {}
        own = seed_cache.get("matched_key") if seed_cache.get("status") == "hit" else seed.cache_key
        rec = {
            "id": p["id"],
            "kind": p["kind"],
            "label": p["label"],
            "a": p["a"],
            "b": p["b"],
            "expected_hit": p["label"] == "hit",
            "predicted_hit": predicted,
            "match": cache.get("match"),
            "similarity": cache.get("similarity"),
            "correct_entry": (matched == own) if predicted else True,
            "nearest_is_own": (nearest == own) if nearest else False,
            "seed_ok": seed.ok,
            "probe_ok": s.ok,
            "client_ms": s.client_ms,
        }
        rec["outcome"] = outcome_label(rec)
        records.append(rec)
        log(f"  probe {i:>2}/{len(pairs)} {rec['outcome']:<15} sim={rec['similarity'] if rec['similarity'] is not None else '-':<7} {p['kind']:<13} {p['b'][:50]}")

    scored = score_pairs(records, threshold)
    return {
        "status": "ok",
        "dataset": str(DATASET.relative_to(DATASET.parents[2])),
        "dataset_sha256_16": dataset_digest(),
        "embedding_model": semantic.get("embedding_model"),
        "seed_failures": sum(1 for s in seeds.values() if not s.ok),
        "seed_hits": sum(1 for s in seeds.values() if s.path.startswith("hit")),
        "probe_failures": sum(1 for r in records if not r["probe_ok"]),
        "duration_s": round(time.perf_counter() - started, 1),
        **scored,
        "examples": pick_examples(records),
        "records": records,
        "_samples": samples,
    }
