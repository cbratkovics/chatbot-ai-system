"""Pure scoring functions behind evals/results/latest.json, checked against fixture data."""

import json
from pathlib import Path

import pytest

from evals import cache_paraphrase_eval, failover_eval, sse_contract_eval
from evals.client import Sample, parse_sse
from evals.stats import best_threshold, confusion, frange, percentile, prf, summarize, sweep

FIX = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "evals_samples.json").read_text())


# --------------------------------------------------------------------------- stats
def test_percentile_matches_bench_demo_definition():
    values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    assert percentile(values, 50) == 60  # half-up on 4.5, same as Math.round in sessionStats.ts
    assert percentile(values, 95) == 100
    assert percentile([5], 99) == 5
    assert percentile([], 50) is None


def test_summarize_rounds_and_handles_empty():
    assert summarize([])["n"] == 0 and summarize([])["p50"] is None
    s = summarize([100.26, 200.0, 300.0])
    assert s["n"] == 3 and s["p50"] == 200.0 and s["min"] == 100.3 and s["mean"] == 200.1


def test_confusion_counts_wrong_entry_hits_as_false_positives():
    counts = confusion(FIX["pair_records"])
    # par001, par002 TP; par003 FN; par004 predicted hit but wrong entry -> FP;
    # int002 and neg001 FP; int001, neg002, ent001, ent002 TN
    assert counts == {"tp": 2, "fp": 3, "fn": 1, "tn": 4}
    m = prf(counts)
    assert m["precision"] == pytest.approx(2 / 5, abs=1e-4)
    assert m["recall"] == pytest.approx(2 / 3, abs=1e-4)
    assert m["f1"] == pytest.approx(0.5, abs=1e-4)


def test_prf_with_no_predictions_is_none_not_zero_division():
    assert prf({"tp": 0, "fp": 0, "fn": 0, "tn": 3}) == {"precision": None, "recall": None, "f1": None}


def test_sweep_uses_recorded_similarity_and_prefers_higher_threshold_on_ties():
    rows = sweep(FIX["pair_records"], frange(0.80, 0.95, 0.05))
    assert [r["threshold"] for r in rows] == [0.8, 0.85, 0.9, 0.95]
    at_95 = rows[-1]
    assert at_95["tp"] == 1 and at_95["fp"] == 0  # only par001 (0.96) clears 0.95
    at_80 = rows[0]
    assert at_80["fp"] >= 3  # negation/intent traps and the wrong-entry hit all clear 0.80
    assert best_threshold(rows) in {r["threshold"] for r in rows}
    tied = [{"threshold": 0.8, "f1": 0.5}, {"threshold": 0.9, "f1": 0.5}, {"threshold": 0.85, "f1": 0.4}]
    assert best_threshold(tied) == 0.9
    assert best_threshold([]) is None


# --------------------------------------------------------------------------- cache eval scoring
def test_score_pairs_reports_by_kind_and_examples():
    records = [dict(r, a=f"a{r['id']}", b=f"b{r['id']}", outcome=cache_paraphrase_eval.outcome_label(r)) for r in FIX["pair_records"]]
    scored = cache_paraphrase_eval.score_pairs(records, threshold=0.85)
    assert scored["n_pairs"] == 10 and scored["threshold"] == 0.85
    assert scored["by_kind"]["negation"]["fp"] == 1 and scored["by_kind"]["paraphrase"]["fn"] == 1
    assert len(scored["sweep"]) == 30 and scored["sweep"][0]["threshold"] == 0.7
    examples = cache_paraphrase_eval.pick_examples(records)
    kinds = [e["outcome"] for e in examples]
    assert kinds[:2] == ["true_positive", "true_positive"]
    assert examples[-1]["kind"] in ("negation", "entity") and examples[-1]["predicted_hit"] is True


def test_dataset_is_well_formed_and_balanced():
    pairs = cache_paraphrase_eval.load_pairs()
    assert len(pairs) >= 60
    assert {p["label"] for p in pairs} == {"hit", "miss"}
    kinds = {p["kind"] for p in pairs}
    assert {"paraphrase", "intent", "negation", "entity"} <= kinds
    assert sum(p["label"] == "miss" for p in pairs) >= 30
    assert len({p["id"] for p in pairs}) == len(pairs)


# --------------------------------------------------------------------------- sse + failover checkers
def _sample(events, content_type="text/event-stream", encoding="", ttfb=12.0) -> Sample:
    s = Sample(prompt="p", status_code=200, streamed=True, content_type=content_type, content_encoding=encoding, ttfb_ms=ttfb)
    s.events = [tuple(e) for e in events]
    for e, d in s.events:
        if e == "delta":
            s.content += d["content"]
        if e == "done":
            s.telemetry = d
    return s


def test_sse_checker_accepts_the_contract_and_rejects_violations():
    good = sse_contract_eval.check_events(_sample(FIX["sse_good"]))
    assert all(good.values()), good
    err = sse_contract_eval.check_events(_sample(FIX["sse_error_only"]))
    assert err["exactly_one_terminal"] and err["terminal_is_last"] and err["first_event_is_meta"]
    bad = sse_contract_eval.check_events(_sample(FIX["sse_bad_order"]))
    assert not bad["first_event_is_meta"] and not bad["meta_before_any_delta"] and not bad["terminal_is_last"]
    gz = sse_contract_eval.check_events(_sample(FIX["sse_good"], encoding="gzip"))
    assert not gz["not_gzip_encoded"]


def test_sse_score_aggregates_pass_rate():
    res = sse_contract_eval.score([_sample(FIX["sse_good"]), _sample(FIX["sse_bad_order"])])
    assert res["n"] == 2 and res["passed"] == 1 and res["pass_rate"] == 0.5
    assert res["checks"]["first_event_is_meta"] == {"passed": 1, "failed": 1}
    assert len(res["failures"]) == 1


def test_failover_checker_and_score():
    ok = _sample([["meta", {}], ["delta", {"content": "x"}], ["done", FIX["failover_good"]]])
    no = _sample([["meta", {}], ["delta", {"content": "x"}], ["done", FIX["failover_no_failover"]]])
    assert all(failover_eval.check_sample(ok).values())
    checks = failover_eval.check_sample(no)
    assert not checks["fallback_answered"] and not checks["primary_recorded_failed"] and not checks["fallback_is_different_provider"]
    ok.client_ms, ok.ttfb_ms, no.client_ms, no.ttfb_ms = 900.0, 400.0, 700.0, 250.0
    res = failover_eval.score([ok], [no])
    assert res["success_rate"] == 1.0 and res["fallback_provider"] == "groq"
    assert res["latency_ms"]["added_ttfb_p50"] == 150.0 and res["latency_ms"]["added_total_p50"] == 200.0


def test_parse_sse_and_sample_path():
    text = 'event: meta\ndata: {"request_id": "r", "cache": {"status": "hit", "key": "k1"}}\n\nevent: delta\ndata: {"content": "hi"}\n\nevent: done\ndata: {"cache": {"status": "hit", "match": "semantic"}, "failover": false}\n\n'
    events = parse_sse(text)
    assert [e for e, _ in events] == ["meta", "delta", "done"]
    s = _sample(events)
    assert s.path == "hit_semantic"
    s.telemetry = {"cache": {"status": "miss"}, "failover": True}
    assert s.path == "failover"
    s.status_code = 500
    assert s.path == "error"
