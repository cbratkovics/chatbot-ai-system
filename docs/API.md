# API Documentation

## Base URL

```
Production: https://api.yourdomain.com/api/v1
Development: http://localhost:8000/api/v1
```

## Authentication

Currently, the API is open. Future versions will support:
- API Key authentication
- OAuth 2.0
- JWT tokens

## Rate Limiting

Two layers, both in-process (ADR 0004):

- **Outer limit, every route**: `RATE_LIMIT_REQUESTS` per `RATE_LIMIT_PERIOD` seconds per client IP
  (default 100 per 60 s; `/health` and `/metrics` exempt). Exceeding it returns `429` with the
  standard error envelope (`code: "rate_limited"`) and a `Retry-After` header.
- **Demo guardrails, chat route**: `DEMO_RATE_LIMIT_PER_MINUTE` (10) and `DEMO_RATE_LIMIT_PER_DAY`
  (40) per IP, a per-request token cap and a shared daily token budget; `429` codes
  `rate_limited`, `daily_limit_reached`, `demo_budget_exhausted`.

`GET /api/v1/chat/health` reports both (`rate_limit`, `guardrails`).

## Endpoints

### Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "service": "chatbot-ai-system",
  "timestamp": "2024-01-01T00:00:00Z",
  "environment": "production",
  "providers_configured": {
    "openai": true,
    "anthropic": true
  }
}
```

### Chat Completion

```http
POST /api/v1/chat/completion
```

**Request Body:**
```json
{
  "message": "Hello, how are you?",
  "model": "gpt-3.5-turbo",
  "temperature": 0.7,
  "max_tokens": 1000,
  "stream": false,
  "system_prompt": "You are a helpful assistant",
  "conversation_history": [
    {"role": "user", "content": "Previous message"},
    {"role": "assistant", "content": "Previous response"}
  ]
}
```

**Response:**
```json
{
  "response": "I'm doing well, thank you! How can I help you today?",
  "model": "gpt-3.5-turbo",
  "request_id": "req_abc123",
  "timestamp": "2024-01-01T00:00:00Z",
  "cached": false,
  "cache_key": "hash_xyz",
  "similarity_score": 0.95,
  "usage": {
    "prompt_tokens": 10,
    "completion_tokens": 15,
    "total_tokens": 25
  }
}
```

### Streaming Chat

```http
POST /api/v1/chat/stream
```

**Request:** Same as chat completion with `stream: true`

**Response:** Server-Sent Events (SSE)
```
data: {"chunk": "I'm", "index": 0}
data: {"chunk": " doing", "index": 1}
data: {"chunk": " well", "index": 2}
data: {"finished": true, "usage": {...}}
```

### List Models

```http
GET /api/v1/models
```

**Response:**
```json
[
  {
    "id": "gpt-4",
    "name": "GPT-4",
    "provider": "openai",
    "context_length": 8192,
    "description": "Most capable GPT-4 model",
    "capabilities": ["chat", "code", "analysis"],
    "available": true,
    "cost_per_token": {
      "input": 0.03,
      "output": 0.06
    }
  }
]
```

### Get Model Details

```http
GET /api/v1/models/{model_id}
```

**Response:** Single model object

### Cache Management

#### Get Cache Stats

```http
GET /api/v1/cache/stats
```

**Response:**
```json
{
  "hits": 1234,
  "misses": 567,
  "hit_rate": 0.685,
  "total_requests": 1801,
  "cache_size_bytes": 1048576,
  "cache_size_human": "1.0 MB",
  "entries": 250,
  "avg_response_time_ms": 45.2,
  "memory_usage_percent": 12.5,
  "evictions": 10,
  "last_eviction": "2024-01-01T00:00:00Z"
}
```

#### Warm Cache

```http
POST /api/v1/cache/warm
```

**Request:**
```json
{
  "patterns": ["greeting", "help", "about"],
  "models": ["gpt-3.5-turbo"],
  "limit": 10
}
```

#### Clear Cache

```http
DELETE /api/v1/cache/clear
```

**Query Parameters:**
- `pattern`: Optional pattern to clear specific entries

## WebSocket API (full deployment only)

The public demo does not use this endpoint and the demo frontend has no WebSocket client; the
demo streams over Server-Sent Events on `POST /api/v1/chat/completions` (ADR 0005). The endpoint
remains mounted for the full deployment and its own tests.

### Connection

```
ws://localhost:8000/ws/chat
wss://api.yourdomain.com/ws/chat
```

### Authentication

Include token in connection URL:
```
ws://localhost:8000/ws/chat?token=your_token
```

### Message Types

#### Chat Message

```json
{
  "type": "chat",
  "id": "msg_123",
  "data": {
    "message": "Hello",
    "model": "gpt-3.5-turbo",
    "stream": true,
    "temperature": 0.7,
    "max_tokens": 1000,
    "system_prompt": "You are helpful",
    "conversation_history": []
  }
}
```

#### Stream Response

```json
{
  "type": "stream",
  "id": "msg_123",
  "data": {
    "chunk": "Hello",
    "index": 0,
    "finished": false
  }
}
```

#### Complete Response

```json
{
  "type": "complete",
  "id": "msg_123",
  "data": {
    "response": "Full response text",
    "model": "gpt-3.5-turbo",
    "usage": {
      "prompt_tokens": 10,
      "completion_tokens": 20,
      "total_tokens": 30
    },
    "cached": false
  }
}
```

#### Error

```json
{
  "type": "error",
  "id": "msg_123",
  "data": {
    "error": "Error message",
    "code": "ERROR_CODE"
  }
}
```

#### Ping/Pong

```json
{
  "type": "ping",
  "id": "ping_123",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

#### Cancel Stream

```json
{
  "type": "cancel",
  "id": "msg_123"
}
```

## Error Codes

| Code | Description | HTTP Status |
|------|-------------|-------------|
| `INVALID_REQUEST` | Malformed request | 400 |
| `UNAUTHORIZED` | Authentication required | 401 |
| `FORBIDDEN` | Access denied | 403 |
| `NOT_FOUND` | Resource not found | 404 |
| `RATE_LIMITED` | Too many requests | 429 |
| `PROVIDER_ERROR` | AI provider error | 502 |
| `TIMEOUT` | Request timeout | 504 |
| `INTERNAL_ERROR` | Server error | 500 |

## Error Response Format

```json
{
  "error": "Error message",
  "code": "ERROR_CODE",
  "status_code": 400,
  "request_id": "req_abc123",
  "timestamp": "2024-01-01T00:00:00Z",
  "details": {
    "field": "Additional error context"
  }
}
```

## Request Headers

### Required Headers

```http
Content-Type: application/json
```

### Optional Headers

```http
X-Request-ID: custom-request-id
X-API-Key: your-api-key
Accept-Encoding: gzip
```

## Response Headers

```http
X-Request-ID: req_abc123
X-Process-Time: 0.123
X-Cache-Status: HIT|MISS|BYPASS
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 99
X-RateLimit-Reset: 2024-01-01T00:01:00Z
Content-Encoding: gzip
```

## Pagination

For endpoints that return lists:

```http
GET /api/v1/resource?page=1&limit=20&sort=created_at&order=desc
```

Response includes pagination metadata:
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 100,
    "pages": 5,
    "has_next": true,
    "has_prev": false
  }
}
```

## Metrics Endpoint

```http
GET /metrics
```

Prometheus exposition format (`text/plain; version=0.0.4`) from the default `prometheus_client`
registry. The families the demo populates:

| Family | Type | Labels | Source |
|---|---|---|---|
| `http_requests_total` | counter | `method`, `endpoint`, `status` | `MetricsMiddleware` |
| `http_request_duration_seconds` | histogram | `method`, `endpoint` | `MetricsMiddleware` |
| `cache_hits_total`, `cache_misses_total` | counter | | one increment per chat request, after the semantic lookup settles |
| `chat_cache_lookups_total` | counter | `result` = `exact_hit`, `semantic_hit`, `miss`, `bypass`, `semantic_unavailable` | `api/chat.py` |

```
# TYPE http_requests_total counter
http_requests_total{endpoint="/api/v1/chat/completions",method="POST",status="200"} 12.0
# TYPE cache_hits_total counter
cache_hits_total 4.0
```

**Caveat.** Counters live in the worker process. The demo runs one worker on Render's free
tier, so they are complete for that worker but reset to zero on every deploy and every
free-tier sleep/wake cycle, exactly like the in-process cache (ADR 0001). For durable series,
scrape them into Prometheus; the configs under `infrastructure/monitoring` do that for the
full stack. The `/evals` page shows this caveat as a footnote.

## Eval Results Endpoint

```http
GET /api/v1/evals/latest
```

Serves the committed artifact `evals/results/latest.json` written by `make evals`
(ADR 0006). Responses carry an `ETag` and `Cache-Control: public, max-age=300`; send
`If-None-Match` to get a `304`. When no artifact has been committed the response is a `404`
with the standard error envelope and `code: "evals_not_found"`, so a client can fall back to
its own build-time copy and label which source it is showing.

## SDK Examples

### Python

```python
import requests

class ChatbotClient:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()

    def chat(self, message, model="gpt-3.5-turbo"):
        response = self.session.post(
            f"{self.base_url}/api/v1/chat/completion",
            json={"message": message, "model": model}
        )
        response.raise_for_status()
        return response.json()

client = ChatbotClient()
response = client.chat("Hello!")
print(response["response"])
```

### JavaScript/TypeScript

```typescript
class ChatbotClient {
  constructor(private baseURL = "http://localhost:8000") {}

  async chat(message: string, model = "gpt-3.5-turbo") {
    const response = await fetch(`${this.baseURL}/api/v1/chat/completion`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, model })
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }
}

const client = new ChatbotClient();
const response = await client.chat("Hello!");
console.log(response.response);
```

### cURL

```bash
curl -X POST http://localhost:8000/api/v1/chat/completion \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello!",
    "model": "gpt-3.5-turbo"
  }'
```

## OpenAPI Specification

Full OpenAPI specification available at:
- Development: http://localhost:8000/openapi.json
- Interactive docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
