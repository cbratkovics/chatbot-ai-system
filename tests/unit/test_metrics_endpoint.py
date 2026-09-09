"""/metrics is Prometheus exposition and the counters move with real requests."""

from fastapi.testclient import TestClient
from prometheus_client.parser import text_string_to_metric_families

BODY = {"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "count me"}]}


def sample(text: str, family: str, **labels) -> float:
    for fam in text_string_to_metric_families(text):
        if fam.name == family:
            for s in fam.samples:
                if s.name == f"{family}_total" and all(s.labels.get(k) == v for k, v in labels.items()):
                    return s.value
    return 0.0


def test_metrics_is_prometheus_text(client: TestClient):
    res = client.get("/metrics")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/plain")
    assert "# TYPE http_requests_total counter" in res.text
    assert "# TYPE http_request_duration_seconds histogram" in res.text
    assert "# TYPE cache_hits_total counter" in res.text


def test_counters_follow_real_requests(client: TestClient, fake_chat_provider):
    before = client.get("/metrics").text
    client.post("/api/v1/chat/completions", json=BODY)  # miss
    client.post("/api/v1/chat/completions", json=BODY)  # exact hit
    after = client.get("/metrics").text

    assert sample(after, "cache_misses") - sample(before, "cache_misses") == 1
    assert sample(after, "cache_hits") - sample(before, "cache_hits") == 1
    assert sample(after, "chat_cache_lookups", result="exact_hit") - sample(before, "chat_cache_lookups", result="exact_hit") == 1
    delta_requests = sample(after, "http_requests", method="POST", endpoint="/api/v1/chat/completions", status="200") - sample(
        before, "http_requests", method="POST", endpoint="/api/v1/chat/completions", status="200"
    )
    assert delta_requests == 2
