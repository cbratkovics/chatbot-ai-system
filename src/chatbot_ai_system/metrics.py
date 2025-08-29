from fastapi import APIRouter, Response
from prometheus_client import Counter, Histogram, generate_latest

router = APIRouter(tags=["metrics"])

# Metrics
request_count = Counter("http_requests_total", "Total HTTP requests")
request_duration = Histogram("http_request_duration_seconds", "HTTP request latency")


@router.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type="text/plain")
