import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Trend, Rate, Counter, Gauge } from 'k6/metrics';
import { randomString, randomItem, randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';
import encoding from 'k6/encoding';

// Custom metrics
const apiLatency = new Trend('api_latency', true);
const authLatency = new Trend('auth_latency', true);
const chatLatency = new Trend('chat_latency', true);
const cacheHitRate = new Rate('cache_hit_rate');
const rateLimitHits = new Counter('rate_limit_hits');
const circuitBreakerTrips = new Counter('circuit_breaker_trips');
const modelSwitches = new Counter('model_switches');
const tenantIsolationErrors = new Counter('tenant_isolation_errors');
const errorRate = new Rate('api_errors');

// Test configuration
export const options = {
  scenarios: {
    // Scenario 1: Normal load pattern
    normal_load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 50 },   // Ramp to 50 users
        { duration: '5m', target: 100 },  // Ramp to 100 users
        { duration: '10m', target: 100 }, // Stay at 100 users
        { duration: '2m', target: 0 },    // Ramp down
      ],
      startTime: '0s',
    },
    // Scenario 2: Cache effectiveness test
    cache_test: {
      executor: 'constant-vus',
      vus: 20,
      duration: '5m',
      startTime: '20m',
      env: { TEST_CACHE: 'true' },
    },
    // Scenario 3: Rate limiting test
    rate_limit_test: {
      executor: 'constant-arrival-rate',
      rate: 200,  // 200 requests per second
      timeUnit: '1s',
      duration: '2m',
      preAllocatedVUs: 50,
      maxVUs: 100,
      startTime: '26m',
    },
    // Scenario 4: Multi-tenant isolation test
    tenant_isolation: {
      executor: 'per-vu-iterations',
      vus: 10,
      iterations: 100,
      startTime: '29m',
      env: { TEST_ISOLATION: 'true' },
    },
  },
  thresholds: {
    'api_latency': ['p(95)<200', 'p(99)<500'],
    'auth_latency': ['p(95)<100', 'p(99)<200'],
    'chat_latency': ['p(95)<300', 'p(99)<1000'],
    'cache_hit_rate': ['rate>0.3'],  // 30% cache hit rate
    'api_errors': ['rate<0.01'],      // Less than 1% error rate
    'http_req_duration': ['p(95)<200'],
    'http_req_failed': ['rate<0.01'],
  },
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(50)', 'p(95)', 'p(99)'],
};

// Configuration
const BASE_URL = __ENV.API_URL || 'http://localhost:8000';
const VECTOR_SEARCH_URL = __ENV.VECTOR_URL || 'http://localhost:8001';

// Test data
const tenants = ['tenant-1', 'tenant-2', 'tenant-3', 'tenant-4', 'tenant-5'];
const models = ['gpt-4', 'gpt-3.5-turbo', 'claude-3-opus', 'claude-3-sonnet', 'llama-3-70b'];

const testPrompts = [
  'What is machine learning?',
  'How do I implement a REST API?',
  'Explain Docker containers',
  'What are microservices?',
  'How does OAuth 2.0 work?',
  'What is the CAP theorem?',
  'Explain database indexing',
  'What is a load balancer?',
  'How do WebSockets work?',
  'What is continuous integration?',
];

// Simulate realistic conversation contexts
const conversationContexts = [
  { topic: 'technical', depth: 'beginner' },
  { topic: 'technical', depth: 'advanced' },
  { topic: 'architecture', depth: 'system-design' },
  { topic: 'debugging', depth: 'troubleshooting' },
  { topic: 'best-practices', depth: 'optimization' },
];

// Helper function to generate auth token
function authenticate(tenantId, userId) {
  const startTime = Date.now();
  
  const payload = JSON.stringify({
    username: `user_${userId}`,
    password: 'test_password',
    tenant_id: tenantId,
  });
  
  const params = {
    headers: {
      'Content-Type': 'application/json',
      'X-Tenant-ID': tenantId,
    },
    tags: { name: 'auth', tenant: tenantId },
  };
  
  const response = http.post(`${BASE_URL}/api/v1/auth/login`, payload, params);
  authLatency.add(Date.now() - startTime);
  
  check(response, {
    'auth successful': (r) => r.status === 200,
    'auth returns token': (r) => r.json('access_token') !== undefined,
  });
  
  if (response.status !== 200) {
    errorRate.add(1);
    return null;
  }
  
  return response.json('access_token');
}

// Helper function to create headers with auth
function getAuthHeaders(token, tenantId) {
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`,
    'X-Tenant-ID': tenantId,
    'X-Request-ID': randomString(16),
  };
}

export default function () {
  const tenantId = randomItem(tenants);
  const userId = `${__VU}_${randomString(8)}`;
  const sessionId = randomString(16);
  
  // Authenticate
  const token = authenticate(tenantId, userId);
  if (!token) {
    console.error(`Authentication failed for user ${userId}`);
    return;
  }
  
  // Test different API endpoints
  group('API Operations', () => {
    
    // 1. Create conversation
    group('Create Conversation', () => {
      const startTime = Date.now();
      const context = randomItem(conversationContexts);
      
      const payload = JSON.stringify({
        title: `Conversation ${randomString(8)}`,
        model: randomItem(models),
        context: context,
        metadata: {
          user_id: userId,
          session_id: sessionId,
          timestamp: new Date().toISOString(),
        },
      });
      
      const response = http.post(
        `${BASE_URL}/api/v1/conversations`,
        payload,
        {
          headers: getAuthHeaders(token, tenantId),
          tags: { name: 'create_conversation' },
        }
      );
      
      apiLatency.add(Date.now() - startTime);
      
      check(response, {
        'conversation created': (r) => r.status === 201,
        'returns conversation id': (r) => r.json('id') !== undefined,
      });
      
      if (response.status === 201) {
        const conversationId = response.json('id');
        
        // 2. Send chat messages
        group('Chat Messages', () => {
          const numMessages = randomIntBetween(3, 10);
          let previousMessageId = null;
          
          for (let i = 0; i < numMessages; i++) {
            const prompt = __ENV.TEST_CACHE === 'true' && i % 3 === 0 
              ? testPrompts[0]  // Repeat same prompt to test cache
              : randomItem(testPrompts);
            
            const chatStartTime = Date.now();
            
            const chatPayload = JSON.stringify({
              conversation_id: conversationId,
              message: prompt,
              parent_message_id: previousMessageId,
              model: i % 5 === 0 ? randomItem(models) : undefined, // Sometimes switch models
              parameters: {
                temperature: 0.7,
                max_tokens: 500,
                stream: false,
              },
            });
            
            const chatResponse = http.post(
              `${BASE_URL}/api/v1/chat/completions`,
              chatPayload,
              {
                headers: getAuthHeaders(token, tenantId),
                tags: { name: 'chat_completion' },
                timeout: '30s',
              }
            );
            
            chatLatency.add(Date.now() - chatStartTime);
            
            // Check for cache hit
            if (chatResponse.headers['X-Cache-Hit'] === 'true') {
              cacheHitRate.add(1);
            } else {
              cacheHitRate.add(0);
            }
            
            // Check for rate limiting
            if (chatResponse.status === 429) {
              rateLimitHits.add(1);
            }
            
            // Check for circuit breaker
            if (chatResponse.headers['X-Circuit-Breaker'] === 'open') {
              circuitBreakerTrips.add(1);
            }
            
            // Check for model switch
            if (chatResponse.headers['X-Model-Switch'] === 'true') {
              modelSwitches.add(1);
            }
            
            check(chatResponse, {
              'chat response successful': (r) => r.status === 200,
              'returns message': (r) => r.json('message') !== undefined,
              'includes model used': (r) => r.json('model') !== undefined,
              'includes usage stats': (r) => r.json('usage') !== undefined,
            });
            
            if (chatResponse.status === 200) {
              previousMessageId = chatResponse.json('id');
            } else {
              errorRate.add(1);
            }
            
            sleep(randomIntBetween(1, 3)); // Simulate thinking time
          }
        });
        
        // 3. Test semantic search
        group('Semantic Search', () => {
          const searchQuery = randomItem(testPrompts);
          
          const searchResponse = http.post(
            `${BASE_URL}/api/v1/search/semantic`,
            JSON.stringify({
              query: searchQuery,
              conversation_id: conversationId,
              limit: 5,
              threshold: 0.7,
            }),
            {
              headers: getAuthHeaders(token, tenantId),
              tags: { name: 'semantic_search' },
            }
          );
          
          check(searchResponse, {
            'search successful': (r) => r.status === 200,
            'returns results': (r) => r.json('results') !== undefined,
          });
        });
        
        // 4. Get conversation history
        group('Get History', () => {
          const historyResponse = http.get(
            `${BASE_URL}/api/v1/conversations/${conversationId}/messages`,
            {
              headers: getAuthHeaders(token, tenantId),
              tags: { name: 'get_history' },
            }
          );
          
          check(historyResponse, {
            'history retrieved': (r) => r.status === 200,
            'returns messages array': (r) => Array.isArray(r.json('messages')),
          });
        });
        
        // 5. Test tenant isolation (if enabled)
        if (__ENV.TEST_ISOLATION === 'true') {
          group('Tenant Isolation', () => {
            // Try to access another tenant's data
            const otherTenant = tenants.find(t => t !== tenantId);
            const isolationResponse = http.get(
              `${BASE_URL}/api/v1/conversations/${conversationId}`,
              {
                headers: getAuthHeaders(token, otherTenant),
                tags: { name: 'tenant_isolation_test' },
              }
            );
            
            check(isolationResponse, {
              'tenant isolation enforced': (r) => r.status === 403 || r.status === 404,
            });
            
            if (isolationResponse.status !== 403 && isolationResponse.status !== 404) {
              tenantIsolationErrors.add(1);
              console.error(`Tenant isolation breach: ${tenantId} accessed ${otherTenant} data`);
            }
          });
        }
        
        // 6. Get usage statistics
        group('Usage Stats', () => {
          const usageResponse = http.get(
            `${BASE_URL}/api/v1/usage/stats`,
            {
              headers: getAuthHeaders(token, tenantId),
              tags: { name: 'usage_stats' },
            }
          );
          
          check(usageResponse, {
            'usage stats retrieved': (r) => r.status === 200,
            'includes token count': (r) => r.json('total_tokens') !== undefined,
            'includes request count': (r) => r.json('total_requests') !== undefined,
            'includes cost estimate': (r) => r.json('estimated_cost') !== undefined,
          });
        });
        
        // 7. Test model health check
        group('Model Health', () => {
          const healthResponse = http.get(
            `${BASE_URL}/api/v1/models/health`,
            {
              headers: getAuthHeaders(token, tenantId),
              tags: { name: 'model_health' },
            }
          );
          
          check(healthResponse, {
            'health check successful': (r) => r.status === 200,
            'all models reported': (r) => {
              const health = r.json();
              return models.every(model => health[model] !== undefined);
            },
          });
        });
      }
    });
  });
  
  // Add realistic think time
  sleep(randomIntBetween(2, 5));
}

// Handle test summary
export function handleSummary(data) {
  const summary = {
    timestamp: new Date().toISOString(),
    test: 'api_load_test',
    metrics: {
      api_latency: {
        p50: data.metrics.api_latency ? data.metrics.api_latency.values['p(50)'] : 0,
        p95: data.metrics.api_latency ? data.metrics.api_latency.values['p(95)'] : 0,
        p99: data.metrics.api_latency ? data.metrics.api_latency.values['p(99)'] : 0,
      },
      chat_latency: {
        p50: data.metrics.chat_latency ? data.metrics.chat_latency.values['p(50)'] : 0,
        p95: data.metrics.chat_latency ? data.metrics.chat_latency.values['p(95)'] : 0,
        p99: data.metrics.chat_latency ? data.metrics.chat_latency.values['p(99)'] : 0,
      },
      cache: {
        hit_rate: data.metrics.cache_hit_rate ? data.metrics.cache_hit_rate.values.rate : 0,
      },
      rate_limiting: {
        hits: data.metrics.rate_limit_hits ? data.metrics.rate_limit_hits.values.count : 0,
      },
      circuit_breaker: {
        trips: data.metrics.circuit_breaker_trips ? data.metrics.circuit_breaker_trips.values.count : 0,
      },
      model_switching: {
        count: data.metrics.model_switches ? data.metrics.model_switches.values.count : 0,
      },
      tenant_isolation: {
        errors: data.metrics.tenant_isolation_errors ? data.metrics.tenant_isolation_errors.values.count : 0,
      },
      errors: {
        rate: data.metrics.api_errors ? data.metrics.api_errors.values.rate : 0,
      },
      throughput: {
        requests: data.metrics.http_reqs ? data.metrics.http_reqs.values.count : 0,
        rps: data.metrics.http_reqs ? data.metrics.http_reqs.values.rate : 0,
      },
      max_concurrent_users: data.metrics.vus_max ? data.metrics.vus_max.values.value : 0,
    },
    thresholds: data.thresholds,
  };

  return {
    'benchmarks/results/api_test.json': JSON.stringify(summary, null, 2),
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
  };
}

// Helper function for text summary
function textSummary(data, options) {
  const indent = options.indent || '';
  let output = '\n=== API Load Test Results ===\n\n';
  
  // API latency
  if (data.metrics.api_latency) {
    output += `${indent}API Latency:\n`;
    output += `${indent}  P50: ${data.metrics.api_latency.values['p(50)'].toFixed(2)}ms\n`;
    output += `${indent}  P95: ${data.metrics.api_latency.values['p(95)'].toFixed(2)}ms\n`;
    output += `${indent}  P99: ${data.metrics.api_latency.values['p(99)'].toFixed(2)}ms\n\n`;
  }
  
  // Chat latency
  if (data.metrics.chat_latency) {
    output += `${indent}Chat Completion Latency:\n`;
    output += `${indent}  P50: ${data.metrics.chat_latency.values['p(50)'].toFixed(2)}ms\n`;
    output += `${indent}  P95: ${data.metrics.chat_latency.values['p(95)'].toFixed(2)}ms\n`;
    output += `${indent}  P99: ${data.metrics.chat_latency.values['p(99)'].toFixed(2)}ms\n\n`;
  }
  
  // Cache performance
  if (data.metrics.cache_hit_rate) {
    output += `${indent}Cache Performance:\n`;
    output += `${indent}  Hit Rate: ${(data.metrics.cache_hit_rate.values.rate * 100).toFixed(2)}%\n\n`;
  }
  
  // Rate limiting
  if (data.metrics.rate_limit_hits) {
    output += `${indent}Rate Limiting:\n`;
    output += `${indent}  Hits: ${data.metrics.rate_limit_hits.values.count}\n\n`;
  }
  
  // Circuit breaker
  if (data.metrics.circuit_breaker_trips) {
    output += `${indent}Circuit Breaker:\n`;
    output += `${indent}  Trips: ${data.metrics.circuit_breaker_trips.values.count}\n\n`;
  }
  
  // Throughput
  if (data.metrics.http_reqs) {
    output += `${indent}Throughput:\n`;
    output += `${indent}  Total Requests: ${data.metrics.http_reqs.values.count}\n`;
    output += `${indent}  Requests/sec: ${data.metrics.http_reqs.values.rate.toFixed(2)}\n\n`;
  }
  
  // Error rate
  if (data.metrics.api_errors) {
    output += `${indent}Error Rate: ${(data.metrics.api_errors.values.rate * 100).toFixed(2)}%\n\n`;
  }
  
  // Max concurrent users
  if (data.metrics.vus_max) {
    output += `${indent}Max Concurrent Users: ${data.metrics.vus_max.values.value}\n\n`;
  }
  
  // Threshold results
  output += `${indent}Threshold Results:\n`;
  for (const [key, value] of Object.entries(data.thresholds || {})) {
    const status = value.ok ? 'PASS' : 'FAIL';
    output += `${indent}  ${key}: ${status}\n`;
  }
  
  return output;
}