# Architecture Decision Records

Short records of the decisions that shape the demo. Format: context, decision, consequences.

| # | Decision |
|---|---|
| [0001](0001-optional-redis-with-memory-fallback.md) | Redis is optional; an in-process LRU cache is the fallback |
| [0002](0002-vector-search-behind-a-flag.md) | Vector search (Pinecone) stays behind `ENABLE_VECTOR_SEARCH` |
| [0003](0003-provider-failover-policy.md) | Provider failover policy: which errors trigger it, what gets recorded |
| [0004](0004-demo-guardrails.md) | In-process demo guardrails instead of a database-backed quota system |
| [0005](0005-sse-streaming-over-websocket.md) | Server-Sent Events, not WebSocket, for the demo's streaming path |
| [0007](0007-semantic-cache-on-the-demo-path.md) | Embedding-based semantic cache on the demo path (supersedes the exact-match-only part of 0001) |
