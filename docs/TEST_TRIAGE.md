# Integration Test Triage

Date: 2026-09-08. Follow-up to the Phase 1 quarantine of `tests/integration`, which was wrong:
most of the 79 failures were stale fixtures, drifted payloads, or live-service dependencies,
not tests for endpoints that never existed. This document is the evidence.

## Result

| Stage | failed | passed | skipped | xfailed |
|---|---|---|---|---|
| Baseline (caches cleared, `--ignore` removed) | **79** | 48 | 11 | 0 |
| After Bin A (live markers) | 67 | 48 | 23 | 0 |
| After Bin D (fixtures) | 55 | 60 | 23 | 0 |
| After Bin C (drift) | 25 | 89 | 23 | 3 |
| After Bin B (deletions) + last protocol fixes | **0** | **95** | **23** | **3** |
| After Phase 2 (SSE streaming landed; its strict xfail became a real test) | 0 | 96 | 23 | 2 |

Full suite `poetry run pytest tests/`: **303 passed, 48 skipped, 3 xfailed, 0 failed** (27 s).
`ruff check .` clean. `mypy src/` clean. Integration runtime fell from 5 min 14 s to 10 s because
the live-server tests no longer wait out connection timeouts.

Skips are all explicit: 12 `live` tests (10 need `TEST_BASE_URL`, 1 `TEST_REDIS_URL`,
1 `TEST_DATABASE_URL`), plus 11 pre-existing `pytest.mark.skip` markers in
`test_websocket.py` / `test_api.py` that predate this work and were not touched.

The xfails are `strict=True`: they encode known gaps and fail loudly the day the gap closes. The
SSE-streaming xfail did exactly that in Phase 2 and was promoted to a real test; two remain
(`refresh_token` dropped by `AuthResponse`, inverted least-loaded routing).

## Method

1. Removed `--ignore=tests/integration`, deleted every `__pycache__` and `.pytest_cache`.
   Seven tests still resolved `~/Desktop/chatbot-ai-system/` after that: hardcoded in
   `test_production_readiness.py`, now `Path(__file__).resolve().parents[2]`.
2. Ran `poetry run pytest tests/integration -q --tb=line -o addopts=""` for a clean baseline.
3. Sorted every failure into exactly one bin, fixed in order A, D, C, B, re-ran after each.
4. Deletion (Bin B) required `git log -S` evidence that the API never existed, not just that it
   is missing now. Anything fixable in ~15 lines was treated as C or D.

## Bins

| Bin | Signature | Action |
|---|---|---|
| **A** | needs a live server / Redis / Postgres | keep; `@pytest.mark.live("<ENV_VAR>")`, auto-skipped by `conftest.pytest_runtest_setup` unless the env var is set; marker registered in `pyproject.toml`; nothing starts a server inside the run |
| **B** | asserts an API that never existed in git history | delete; record name + missing API below |
| **C** | drift between test and current code | fix the test; escalate if the code looks wrong |
| **D** | broken fixture / mock | fix the shared fixture in `tests/conftest.py` |

Counts: A = 12, B = 19, C = 33, D = 15 (a few rows are C+D; counted once under the dominant fix).

## Triage table (one row per baseline failure)

### tests/integration/test_api_endpoints.py (20)

| test | error | bin | action |
|---|---|---|---|
| `TestChatEndpoints::test_chat_completion_endpoint` | `401 == 200` | D | new `fake_chat_provider` fixture routes `api.chat.make_provider` to a canned provider; app is healthy with no keys and no Redis |
| `TestChatEndpoints::test_streaming_chat_endpoint` | content-type is JSON | C | `xfail(strict=True)`: SSE on `/chat/completions` is Phase 2 |
| `TestChatEndpoints::test_chat_history_endpoint` | `404 == 200` | B | **deleted**. `GET /api/v1/chat/history` never existed (`git log -S` on `api/`: only unrelated `performance_history` strings) |
| `TestChatEndpoints::test_delete_chat_endpoint` | `404 == 204` | B | **deleted**. `DELETE /api/v1/chat/{chat_id}` never existed (0 commits) |
| `TestChatEndpoints::test_model_switching_endpoint` | `422 == 200` | C | body was `{model, message}` with retired ids; now `{model, messages}` with one catalogue model per provider |
| `TestWebSocketEndpoints::test_websocket_connection` | `'connection' == 'pong'` | C | protocol: manager sends `connection`, endpoint sends `connected`, heartbeat `ping` can arrive any time; helper drains them, then ping→pong |
| `TestWebSocketEndpoints::test_websocket_streaming` | hung 300 s waiting for `done` | C+D | terminal type is `complete` (or `error`); `status` precedes `stream` chunks; fake streaming provider; this test alone cost 5 minutes per run |
| `TestWebSocketEndpoints::test_websocket_error_handling` | `'connection' == 'error'` | C | drain greetings first |
| `TestAuthenticationEndpoints::test_login_endpoint` | `refresh_token` missing | C | assert `access_token`/`token_type`; new strict-xfail `test_login_returns_refresh_token` records the gap (escalation 1) |
| `TestAuthenticationEndpoints::test_refresh_token_endpoint` | `401 == 200` | C | `/auth/refresh` reads the Bearer token, not a JSON body; login first |
| `TestAuthenticationEndpoints::test_api_key_generation` | `'id'` missing | C | assert `key`/`name` (escalation 10) |
| `TestTenantEndpoints::test_create_tenant` | `307 == 201` | C | route is `/api/v1/tenants/` with query params, not JSON |
| `TestTenantEndpoints::test_get_tenant` | `404 == 200` | C | stub only knows `tenant-1`/`tenant-2` (escalation 9); added `test_get_unknown_tenant_is_404` |
| `TestTenantEndpoints::test_update_tenant` | `404 == 200` | C | same; query params |
| `TestTenantEndpoints::test_tenant_usage` | `404 == 200` | B | **deleted**. `GET /tenants/{id}/usage` never existed (the two `-S"/usage"` hits are `finops/billing.py` and `usage=` kwargs) |
| `TestHealthEndpoints::test_health_check` | `503 == 200` | D | root cause was mine: Phase 1 lifespan shutdown disconnected the memory cache but left it as the module singleton, so every `/health` after a `TestClient(app)` context reported `memory: unhealthy`. Fixed in `server/main.py` (`chat_api.cache = None` after disconnect) |
| `TestHealthEndpoints::test_readiness_check` | `404 == 200` | C | `/ready` → `/api/v1/health/ready`; shape is `status`/`components` (escalation 3) |
| `TestHealthEndpoints::test_metrics_endpoint` | `'prometheus' in 'application/json'` | C | assert JSON fields (escalation 4) |
| `TestCacheEndpoints::test_cache_stats` | `'memory_usage_mb'` missing | C | assert `hits`/`misses`/`hit_rate` (escalation 5) |
| `TestCacheEndpoints::test_cache_warmup` | `404 == 200` | C | route is `POST /api/v1/cache/warm` taking `list[str]`, response key `warmed` |

### tests/integration/test_cache_integration.py (8)

| test | error | bin | action |
|---|---|---|---|
| `test_semantic_cache_hit` | `KeyError: 'cached'` | C | `SemanticCache.get` returns the stored value; assert the round-trip (escalation 7) |
| `test_cache_ttl_expiration` | value did not expire | D | `mock_redis.setex`/`expire`/`get` now honour TTL |
| `test_cache_invalidation_on_update` | not invalidated | D | `mock_redis.scan_iter` yields fnmatch keys; `delete(*keys)` |
| `test_cache_performance_metrics` | `0 == 0.7` | D+C | `return_value` is ignored while `side_effect` is set; assert the manager's own `_hits`/`_misses` (escalation 6) |
| `test_distributed_cache_consistency` | `redis.asyncio` has no `create_redis_pool` | A | `live("TEST_REDIS_URL")`; `redis.asyncio.from_url`; cleans up its key |
| `test_cache_eviction_policy` | `max_size_mb` kwarg | B | **deleted**. `core.cache.CacheManager` never had `max_size_mb` / `get_memory_usage` (checked at 6acce57, ba003a0, and pre-restructure `api/cache/cache_manager.py`; the `-S` hits are `redis_cache.py` stats and `SemanticCache.max_size_mb`) |
| `test_cache_compression` | `compression` kwarg | B | **deleted**. never a `CacheManager` parameter (same evidence) |
| `test_cache_batch_operations` | no `get_batch` | C+D | `set_batch` + per-key `get`; pipeline mock now applies queued writes on `execute()` |

### tests/integration/test_database_operations.py (8)

| test | error | bin | action |
|---|---|---|---|
| `test_database_connection_pool` | `get_async_engine() got 'url'` | A+C | `live("TEST_DATABASE_URL")`; `create_async_engine(url)` + `text("SELECT 1")` |
| `test_concurrent_database_writes` | `'message' invalid for Conversation` | C | `Chat` is an alias of `Conversation`: `title`, UUID ids |
| `test_database_query_optimization` | `User.chats` | C+D | relationship is `User.conversations`; awaited `execute()` returns a sync Result mock |
| `test_database_backup_restore` | `OSError` on a MagicMock path | C | helpers take a **URL** not a session; real SQLite file round-trip in `tmp_path` |
| `test_database_indexing_performance` | `MagicMock can't be awaited` | D | `mock_database.execute = AsyncMock(return_value=MagicMock())` |
| `test_database_partitioning` | same | D | same, plus `scalar.return_value` |
| `test_database_connection_retry` | patches non-existent `database.create_async_engine`; `create_database_connection(max_retries=3)` | B | **deleted**. no retry signature ever existed (`-S` on the retry signature: 0 commits) |
| `test_database_read_replica` | `async_generator can't be awaited` | B | **deleted**. read-replica routing never existed (`-S"replica"`: 0 commits); `get_read_replica_session` is a documented alias of the main session |

### tests/integration/test_model_switching.py (6)

| test | error | bin | action |
|---|---|---|---|
| `test_openai_to_anthropic_switch` | OpenAI 401 with test key, then `AsyncAnthropic has no 'messages'` | D | new `fake_core_clients` fixture replaces `_init_client` on both core providers (escalation 8) |
| `test_model_performance_comparison` | same | D | same |
| `test_concurrent_model_requests` | same | D | same |
| `test_model_context_preservation` | same | D | same; fake echoes user messages so "Alice" survives |
| `test_model_cost_optimization` | same | D | same |
| `test_model_capability_routing` | model not in expected set | C | `ModelFactory` only consults `capability_required` inside cost optimisation with a ≥100-char message (escalation 12); test now sets that up |

### tests/integration/test_production_readiness.py (8)

| test | error | bin | action |
|---|---|---|---|
| `test_health_endpoint` | `503 == 200` | D | same lifespan bug as above |
| `test_docker_files_exist` | `assert False` (old absolute path) | C | `REPO_ROOT = Path(__file__).resolve().parents[2]` |
| `test_docker_compose_files_exist` | same | C | same |
| `test_env_example_exists` | same | C | same |
| `test_ci_workflow_exists` | same | C | same |
| `test_pyproject_toml_is_valid` | same | C | same |
| `test_readme_exists` | same | C | same |
| `TestSystemPerformance::test_health_check_response_time` | `503 == 200` | D | same lifespan bug |

### tests/integration/test_provider_failover.py (7)

| test | error | bin | action |
|---|---|---|---|
| `test_automatic_failover_on_provider_error` | `ValidationError` for `CompletionRequest` | C | `CompletionRequest.messages` is `List[Message]`; tests passed `ChatMessage` |
| `test_circuit_breaker_activation` | same | C | same |
| `test_rate_limit_handling` | same, then expected a same-provider retry | C | orchestrator fails over to the next provider on 429 instead of retrying the limited one; assert that |
| `test_load_balancing_strategies` | same | C | same |
| `test_all_providers_down_error` | message text drift | C | assert `error_code == "no_providers"` |
| `test_model_specific_routing` | same | C | same |
| `test_concurrent_request_handling` | only `provider_a` used under `LEAST_LOADED` | C | `xfail(strict=True)`: the strategy is inverted (escalation 2); mocks now hold a semaphore permit so load is observable once fixed |

### tests/integration/test_rate_limiting.py (12) — file deleted

All twelve tests drove `core.tenancy.rate_limiter.RateLimiter` through `check_limit`,
`set_limit`, `get_remaining`, `get_headers`, `add_exemption`, `configure_token_bucket`,
`consume_tokens`, `get_remaining_tokens`, `set_sliding_window`, `get_degraded_response`,
`get_analytics`, `get_client_stats`. `git log -S"def <name>" -- src` returns **0 commits for
every one of them**; the single string hit for `get_remaining` is `scripts/migrate_to_poetry.py`.
The class's real API (`allow_request`, `allow_request_with_grace`, `reset_quota`,
`get_rate_limit_headers`, and the `TokenBucket`/`SlidingWindow`/`Distributed`/`Tenant`/`Adaptive`
subclasses) is covered by the 13 passing tests in `tests/unit/test_rate_limiter.py`.

Deleted: `test_basic_rate_limiting`, `test_rate_limit_window_reset`, `test_per_tenant_rate_limits`,
`test_rate_limit_headers`, `test_distributed_rate_limiting`, `test_rate_limit_by_endpoint`,
`test_rate_limit_burst_handling`, `test_rate_limit_exemptions`,
`test_rate_limit_with_cost_based_limiting`, `test_rate_limit_sliding_window`,
`test_rate_limit_graceful_degradation`, `test_rate_limit_analytics`.

### tests/integration/test_websocket_flow.py (10)

| test | error | bin | action |
|---|---|---|---|
| all 10 (`test_websocket_connection_lifecycle` … `test_websocket_broadcast`) | `Connect call failed ('::1', 8000)` | A | module-level `pytestmark = pytest.mark.live("TEST_BASE_URL")`; URI derived from the env var |

## Step 4: test runs no longer write committed artifacts

`tests/test_provider_failover.py` wrote `benchmarks/results/failover_timing_<ts>.json` and
overwrote `failover_timing_latest.json` on every run. It now writes to
`benchmarks/results/tmp/` (gitignored) unless `BENCHMARK_RESULTS_DIR` points elsewhere.
`failover_timing_latest.json` was restored to its HEAD content (`git show HEAD:… >`), and
`git status` no longer lists it. Committed result files must come from an explicit benchmark
script (Phase 2's `scripts/bench_demo.py`).

## Escalations: places where the code, not the test, looks wrong

Described only. None of these were changed.

1. **`AuthResponse` drops `refresh_token`.** `api/auth.py` builds one for username/password
   logins and even comments "Include refresh_token for compatibility with tests", but
   `response_model=AuthResponse` has no such field, so it is stripped. Fix: add
   `refresh_token: Optional[str] = None` to `api/models.py:AuthResponse`. Strict xfail in place.
2. **Least-loaded routing is inverted.** `providers/orchestrator.py:_least_loaded_selection`
   returns `min(providers, key=p._semaphore._value)`. A semaphore's `_value` is the number of
   *free* permits, so this picks the busiest provider. Fix: `max(...)`. Strict xfail in place.
3. **`/ready` moved.** The root readiness probe existed for 5 commits and now lives only at
   `/api/v1/health/ready`. Render and Kubernetes conventions expect root-level probes; consider
   restoring a root alias. Test updated to the new path.
4. **`/metrics` is JSON.** `prometheus-client` is a dependency and `monitoring/metrics.py`
   exists, yet `/metrics` returns `{uptime_seconds, environment, version}`. Either expose the
   Prometheus registry or rename the route.
5. **`/api/v1/cache/stats` returns hardcoded numbers** (`hits: 1234`, `hit_rate: 0.685`,
   `evictions: 23`). This is fabricated data on a public endpoint. It should read
   `api.chat.cache.get_stats()`; `/api/v1/chat/cache/stats` already does.
6. **`core/cache/CacheManager.get_statistics` ignores its own counters.** It increments
   `_hits`/`_misses` but computes `hit_rate` from Redis `INFO` keys `hits`/`misses`, which real
   Redis does not emit (it uses `keyspace_hits`/`keyspace_misses`). Hit rate is therefore always 0.
7. **`core/cache/SemanticCache` is a stub in `src/`.** Embeddings are `np.random.rand`, and
   "semantic" matching is a hardcoded list of four weather questions. Label it as a sketch or
   remove it (Phase 2 hygiene item).
8. **`core/models/anthropic_provider.py` cannot work with the pinned SDK.** It calls
   `client.messages.create`, but `anthropic==0.8.1` has no `messages` resource. The second
   provider stack under `core/models/` is broken against installed dependencies and is not used
   by the app; the app uses `providers/`.
9. **Tenants API is a stub.** Only `tenant-1` and `tenant-2` resolve; `POST /tenants/` returns a
   random id that then 404s on GET/PUT; `POST /api/v1/tenants` (no slash) answers 307.
10. **API keys have no id.** `POST /auth/api-keys` returns `{key, name, created_at}`, yet
    `DELETE /auth/api-keys/{key_id}` exists with nothing to reference.
11. **WebSocket greets twice.** `WebSocketManager.connect` sends `{"type": "connection"}` and the
    endpoint then sends `{"type": "connected"}`. One should go.
12. **Capability routing is hidden behind cost optimisation.** `ModelFactory` only honours
    `capability_required` inside `_select_cost_optimized_model`, which runs only with
    `cost_optimization=True`, `optimize_cost=True`, and a message of 100+ characters.

Fixed during this phase because it was my own Phase 1 bug: `server/main.py` lifespan shutdown
now clears the cache singleton after disconnecting it.

## Reproduce

```bash
poetry run pytest tests/integration -q -o addopts=""            # 95 passed, 23 skipped, 3 xfailed
poetry run pytest tests/ -q                                       # 303 passed, 48 skipped, 3 xfailed
TEST_BASE_URL=http://localhost:8000 poetry run pytest tests/integration/test_websocket_flow.py
TEST_REDIS_URL=redis://localhost:6379/0 poetry run pytest tests/integration/test_cache_integration.py -k distributed
```
