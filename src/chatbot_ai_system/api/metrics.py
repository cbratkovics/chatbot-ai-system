"""Prometheus exposition for the demo path.

``/metrics`` serves the default ``prometheus_client`` registry. Three families matter for
the demo and the Grafana dashboards under ``infrastructure/monitoring``:

- ``http_requests_total`` / ``http_request_duration_seconds`` from ``MetricsMiddleware``
- ``cache_hits_total`` / ``cache_misses_total`` (declared in ``cache/redis_cache.py``)
- ``chat_cache_lookups_total{result}`` for the exact/semantic breakdown

Counters live in the worker process: on a single free-tier worker they reset on every
deploy, exactly like the in-process cache (ADR 0001).
"""

from fastapi import Response
from prometheus_client import CONTENT_TYPE_LATEST, REGISTRY, Counter, generate_latest

from ..cache.redis_cache import cache_hits, cache_misses

CACHE_LOOKUPS = Counter(
    "chat_cache_lookups_total",
    "Chat cache lookups by outcome",
    ["result"],  # exact_hit | semantic_hit | miss | bypass | semantic_unavailable
)


def record_cache_outcome(status: str, match: str = "", semantic: str = "") -> None:
    """One increment per chat request, after the lookup has settled."""
    if status == "hit":
        cache_hits.inc()
        CACHE_LOOKUPS.labels(result=f"{match or 'exact'}_hit").inc()
        return
    if status == "bypass":
        CACHE_LOOKUPS.labels(result="bypass").inc()
        return
    cache_misses.inc()
    CACHE_LOOKUPS.labels(
        result="semantic_unavailable" if semantic == "unavailable" else "miss"
    ).inc()


def metrics_response() -> Response:
    return Response(content=generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
