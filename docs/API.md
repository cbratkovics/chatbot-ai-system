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

- **Default**: 100 requests per minute per IP
- **Burst**: 20 requests
- **WebSocket**: 5 connections per minute

Rate limit headers:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 99
X-RateLimit-Reset: 2024-01-01T00:01:00Z
```

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
  "service": "ai-chatbot-system",
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

## WebSocket API

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

Returns Prometheus-formatted metrics:
```
# HELP chatbot_requests_total Total number of requests
# TYPE chatbot_requests_total counter
chatbot_requests_total{method="GET",endpoint="/health",status="200"} 1234
```

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
