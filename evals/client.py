"""HTTP client for the evals: one request in, one ``Sample`` out, with client-side timings.

Shares the wire format with ``scripts/bench_demo.py`` (plain JSON for seeding) and adds an SSE
reader that records the event order and time-to-first-delta the contract eval needs.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import httpx

SIMULATE_HEADER = "X-Demo-Simulate-Failure"


@dataclass
class Sample:
    """One observed request."""

    prompt: str
    status_code: Optional[int] = None
    client_ms: Optional[float] = None
    ttfb_ms: Optional[float] = None  # client-observed time to first delta (stream only)
    streamed: bool = False
    content_type: str = ""
    content_encoding: str = ""
    events: List[Tuple[str, Any]] = field(default_factory=list)
    telemetry: Dict[str, Any] = field(default_factory=dict)
    content: str = ""
    cache_key: Optional[str] = None
    error: Optional[str] = None
    tags: Dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status_code == 200 and self.error is None and bool(self.telemetry)

    @property
    def cache_status(self) -> Optional[str]:
        return (self.telemetry.get("cache") or {}).get("status")

    @property
    def path(self) -> str:
        """hit_exact | hit_semantic | failover | miss | bypass | error."""
        if not self.ok:
            return "error"
        t = self.telemetry
        cache = t.get("cache") or {}
        if cache.get("status") == "hit":
            return "hit_semantic" if cache.get("match") == "semantic" else "hit_exact"
        if t.get("failover"):
            return "failover"
        return "bypass" if cache.get("status") == "bypass" else "miss"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt": self.prompt,
            "status_code": self.status_code,
            "client_ms": self.client_ms,
            "ttfb_ms": self.ttfb_ms,
            "path": self.path,
            "cache": self.telemetry.get("cache"),
            "provider": self.telemetry.get("provider"),
            "model": self.telemetry.get("model"),
            "server_latency_ms": self.telemetry.get("latency_ms"),
            "server_ttfb_ms": self.telemetry.get("ttfb_ms"),
            "cost_usd": self.telemetry.get("cost_usd"),
            "cost_avoided_usd": self.telemetry.get("cost_avoided_usd"),
            "failover": self.telemetry.get("failover"),
            "attempts": self.telemetry.get("attempts"),
            "error": self.error,
            **self.tags,
        }


def parse_sse(text: str) -> List[Tuple[str, Any]]:
    """[(event, data)] for each blank-line separated block; data parsed as JSON when possible."""
    events: List[Tuple[str, Any]] = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        event, data = None, ""
        for line in block.split("\n"):
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data += line[5:].strip()
        if event:
            try:
                events.append((event, json.loads(data) if data else None))
            except json.JSONDecodeError:
                events.append((event, data))
    return events


class EvalClient:
    def __init__(self, base_url: str, model: str = "default", timeout: float = 90.0) -> None:
        self.base = base_url.rstrip("/")
        self.model = model
        self._client = httpx.Client(timeout=timeout)
        self.requests = 0

    def close(self) -> None:
        self._client.close()

    # -- probes -------------------------------------------------------------
    def health(self) -> Dict[str, Any]:
        res = self._client.get(f"{self.base}/api/v1/chat/health")
        res.raise_for_status()
        return res.json()

    def clear_cache(self) -> Dict[str, Any]:
        res = self._client.delete(f"{self.base}/api/v1/chat/cache")
        res.raise_for_status()
        return res.json()

    # -- one request ----------------------------------------------------------
    def complete(
        self,
        prompt: str,
        *,
        stream: bool = False,
        simulate: bool = False,
        bypass: bool = False,
        max_tokens: Optional[int] = None,
        tenant: Optional[str] = None,
        **tags: Any,
    ) -> Sample:
        body: Dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": stream,
        }
        if max_tokens:
            body["max_tokens"] = max_tokens
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream, application/json" if stream else "application/json"}
        if simulate:
            headers[SIMULATE_HEADER] = "1"
        if bypass:
            headers["Cache-Control"] = "no-cache"
        if tenant:
            headers["X-Tenant-ID"] = tenant
        sample = Sample(prompt=prompt, streamed=stream, tags=tags)
        self.requests += 1
        started = time.perf_counter()
        try:
            if stream:
                self._stream(body, headers, sample, started)
            else:
                res = self._client.post(f"{self.base}/api/v1/chat/completions", json=body, headers=headers)
                sample.client_ms = round((time.perf_counter() - started) * 1000, 1)
                sample.status_code = res.status_code
                sample.content_type = res.headers.get("content-type", "")
                data = res.json()
                if res.status_code == 200:
                    sample.telemetry = data.get("telemetry") or {}
                    sample.content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
                    sample.cache_key = data.get("cache_key")
                else:
                    sample.error = json.dumps(data.get("error") or data)[:300]
        except Exception as exc:  # noqa: BLE001 - record and keep going
            sample.client_ms = round((time.perf_counter() - started) * 1000, 1)
            sample.error = f"{type(exc).__name__}: {exc}"[:300]
        return sample

    def _stream(self, body: Dict[str, Any], headers: Dict[str, str], sample: Sample, started: float) -> None:
        with self._client.stream("POST", f"{self.base}/api/v1/chat/completions", json=body, headers=headers) as res:
            sample.status_code = res.status_code
            sample.content_type = res.headers.get("content-type", "")
            sample.content_encoding = res.headers.get("content-encoding", "")
            buffer = b""
            chunks: List[bytes] = []
            for chunk in res.iter_raw():
                if not chunk:
                    continue
                chunks.append(chunk)
                buffer += chunk
                if sample.ttfb_ms is None and b"event: delta" in buffer:
                    sample.ttfb_ms = round((time.perf_counter() - started) * 1000, 1)
            sample.client_ms = round((time.perf_counter() - started) * 1000, 1)
            text = buffer.decode("utf-8", errors="replace")
        if not sample.content_type.startswith("text/event-stream"):
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = {}
            sample.error = json.dumps(data.get("error") or data)[:300]
            return
        sample.events = parse_sse(text)
        for event, data in sample.events:
            if event == "delta" and isinstance(data, dict):
                sample.content += str(data.get("content", ""))
            elif event == "done" and isinstance(data, dict):
                sample.telemetry = data
            elif event == "error":
                sample.error = json.dumps(data)[:300]
        for event, data in sample.events:
            if event == "meta" and isinstance(data, dict):
                sample.cache_key = (data.get("cache") or {}).get("key")
                break
