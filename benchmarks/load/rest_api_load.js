import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';
import { htmlReport } from 'https://raw.githubusercontent.com/benc-uk/k6-reporter/main/dist/bundle.js';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.2/index.js';

// Custom metrics
const errorRate = new Rate('errors');
const cacheHitRate = new Rate('cache_hits');
const apiLatency = new Trend('api_latency', true);
const costPerRequest = new Trend('cost_per_request');
const tokenCount = new Counter('tokens_processed');

// Configuration
const BASE_URL = __ENV.API_URL || 'http://localhost:8000';
const API_KEY = __ENV.API_KEY || 'test-tenant-key-123';
const TIMESTAMP = new Date().toISOString().replace(/[:.]/g, '-');

// Test scenarios
export const options = {
  scenarios: {
    smoke: {
      executor: 'constant-vus',
      vus: 1,
      duration: '30s',
      startTime: '0s',
      tags: { scenario: 'smoke' },
    },
    load: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '5m', target: 50 },  // Ramp up to 50 VUs
        { duration: '5m', target: 50 },  // Stay at 50 VUs
        { duration: '2m', target: 0 },   // Ramp down
      ],
      startTime: '31s',
      tags: { scenario: 'load' },
    },
    stress: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 50 },   // Warm up
        { duration: '5m', target: 200 },  // Ramp to stress level
        { duration: '3m', target: 200 },  // Sustain stress
        { duration: '2m', target: 0 },    // Cool down
      ],
      startTime: '12m32s',
      tags: { scenario: 'stress' },
    },
  },
  thresholds: {
    // Health endpoint thresholds
    'http_req_duration{endpoint:/health}': [
      'p(95)<300',  // Dev environment threshold
      'p(99)<500',
    ],
    // Chat endpoint thresholds
    'http_req_duration{endpoint:/v1/chat}': [
      'p(95)<300',  // Dev environment threshold
      'p(99)<500',
    ],
    // Embeddings endpoint thresholds
    'http_req_duration{endpoint:/v1/embeddings}': [
      'p(95)<400',
      'p(99)<600',
    ],
    // Overall thresholds
    checks: ['rate>0.995'],  // 99.5% pass rate
    http_req_failed: ['rate<0.005'],  // < 0.5% error rate
    errors: ['rate<0.005'],
    cache_hits: ['rate>0.25'],  // Target 25%+ cache hit rate
  },
};

// Test data
const chatPrompts = [
  'What is machine learning?',
  'Explain neural networks in simple terms',
  'How does gradient descent work?',
  'What are transformers in AI?',
  'Describe the attention mechanism',
  'What is transfer learning?',
  'How do GANs work?',
  'Explain BERT architecture',
  'What is reinforcement learning?',
  'How does GPT work?',
];

const embeddingTexts = [
  'Machine learning enables computers to learn from data',
  'Neural networks are inspired by biological neurons',
  'Deep learning uses multiple layers of processing',
  'Natural language processing understands human language',
  'Computer vision analyzes and interprets images',
];

// Helper functions
function makeAuthHeaders() {
  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${API_KEY}`,
    'X-Tenant-ID': 'test-tenant-001',
    'X-Request-ID': `k6-${__VU}-${__ITER}-${Date.now()}`,
  };
}

function extractMetrics(response) {
  const headers = response.headers;
  
  // Extract cache hit from headers
  if (headers['X-Cache-Hit']) {
    cacheHitRate.add(headers['X-Cache-Hit'] === 'true' ? 1 : 0);
  }
  
  // Extract cost metrics
  if (headers['X-Token-Count']) {
    tokenCount.add(parseInt(headers['X-Token-Count']) || 0);
  }
  
  if (headers['X-Cost-USD']) {
    costPerRequest.add(parseFloat(headers['X-Cost-USD']) || 0);
  }
  
  // Extract latency
  if (headers['X-Processing-Time-Ms']) {
    apiLatency.add(parseFloat(headers['X-Processing-Time-Ms']) || 0);
  }
}

// Main test execution
export default function () {
  const scenario = __ENV.K6_SCENARIO || 'default';
  
  group('Health Check', () => {
    const healthRes = http.get(`${BASE_URL}/health`, {
      tags: { endpoint: '/health', scenario },
    });
    
    check(healthRes, {
      'health status is 200': (r) => r.status === 200,
      'health response has status': (r) => {
        try {
          const body = JSON.parse(r.body);
          return body.status === 'healthy';
        } catch {
          return false;
        }
      },
      'health latency < 100ms': (r) => r.timings.duration < 100,
    }) || errorRate.add(1);
    
    sleep(0.1);
  });
  
  group('Chat Completion', () => {
    const prompt = chatPrompts[Math.floor(Math.random() * chatPrompts.length)];
    const chatPayload = JSON.stringify({
      model: 'gpt-3.5-turbo',
      messages: [
        { role: 'user', content: prompt }
      ],
      stream: false,
      temperature: 0.7,
      max_tokens: 150,
    });
    
    const chatRes = http.post(
      `${BASE_URL}/v1/chat`,
      chatPayload,
      {
        headers: makeAuthHeaders(),
        tags: { endpoint: '/v1/chat', scenario },
        timeout: '30s',
      }
    );
    
    const chatChecks = check(chatRes, {
      'chat status is 200': (r) => r.status === 200,
      'chat response has content': (r) => {
        try {
          const body = JSON.parse(r.body);
          return body.choices && body.choices[0].message.content.length > 0;
        } catch {
          return false;
        }
      },
      'chat response has model': (r) => {
        try {
          const body = JSON.parse(r.body);
          return body.model !== undefined;
        } catch {
          return false;
        }
      },
      'chat latency < 500ms': (r) => r.timings.duration < 500,
    });
    
    if (!chatChecks) {
      errorRate.add(1);
      console.error(`Chat failed: ${chatRes.status} - ${chatRes.body}`);
    } else {
      errorRate.add(0);
      extractMetrics(chatRes);
    }
    
    sleep(Math.random() * 2 + 1); // Random sleep 1-3s
  });
  
  group('Embeddings', () => {
    const text = embeddingTexts[Math.floor(Math.random() * embeddingTexts.length)];
    const embeddingPayload = JSON.stringify({
      model: 'text-embedding-ada-002',
      input: text,
    });
    
    const embeddingRes = http.post(
      `${BASE_URL}/v1/embeddings`,
      embeddingPayload,
      {
        headers: makeAuthHeaders(),
        tags: { endpoint: '/v1/embeddings', scenario },
        timeout: '10s',
      }
    );
    
    const embeddingChecks = check(embeddingRes, {
      'embedding status is 200': (r) => r.status === 200,
      'embedding response has data': (r) => {
        try {
          const body = JSON.parse(r.body);
          return body.data && body.data[0].embedding.length > 0;
        } catch {
          return false;
        }
      },
      'embedding dimension correct': (r) => {
        try {
          const body = JSON.parse(r.body);
          return body.data[0].embedding.length === 1536; // Ada-002 dimension
        } catch {
          return false;
        }
      },
    });
    
    if (!embeddingChecks) {
      errorRate.add(1);
    } else {
      errorRate.add(0);
      extractMetrics(embeddingRes);
    }
    
    sleep(Math.random() + 0.5); // Random sleep 0.5-1.5s
  });
  
  group('Metrics Scrape', () => {
    const metricsRes = http.get(`${BASE_URL}/metrics`, {
      tags: { endpoint: '/metrics', scenario },
      timeout: '5s',
    });
    
    if (metricsRes.status === 200) {
      // Parse Prometheus metrics for cache hit rate
      const lines = metricsRes.body.split('\n');
      lines.forEach(line => {
        if (line.includes('cache_hit_total')) {
          const match = line.match(/cache_hit_total{[^}]*} (\d+)/);
          if (match) {
            const hits = parseInt(match[1]);
            // Store for analysis
          }
        }
      });
    }
  });
}

// Custom report generation
export function handleSummary(data) {
  const timestamp = TIMESTAMP;
  
  // Calculate aggregate metrics
  const aggregateMetrics = {
    timestamp: new Date().toISOString(),
    environment: {
      base_url: BASE_URL,
      vus_max: data.metrics.vus_max?.values?.value || 0,
      duration: data.state?.testRunDurationMs || 0,
      iterations: data.metrics.iterations?.values?.count || 0,
    },
    latency: {
      p50_ms: Math.round(data.metrics.http_req_duration?.values?.['p(50)'] || 0),
      p95_ms: Math.round(data.metrics.http_req_duration?.values?.['p(95)'] || 0),
      p99_ms: Math.round(data.metrics.http_req_duration?.values?.['p(99)'] || 0),
    },
    reliability: {
      error_rate: data.metrics.http_req_failed?.values?.rate || 0,
      check_pass_rate: data.metrics.checks?.values?.rate || 0,
    },
    efficiency: {
      cache_hit_rate: data.metrics.cache_hits?.values?.rate || 0,
      avg_cost_per_request: data.metrics.cost_per_request?.values?.avg || 0,
      total_tokens: data.metrics.tokens_processed?.values?.count || 0,
    },
    endpoints: {
      health: {
        p95_ms: Math.round(data.metrics['http_req_duration{endpoint:/health}']?.values?.['p(95)'] || 0),
        count: data.metrics['http_reqs{endpoint:/health}']?.values?.count || 0,
      },
      chat: {
        p95_ms: Math.round(data.metrics['http_req_duration{endpoint:/v1/chat}']?.values?.['p(95)'] || 0),
        count: data.metrics['http_reqs{endpoint:/v1/chat}']?.values?.count || 0,
      },
      embeddings: {
        p95_ms: Math.round(data.metrics['http_req_duration{endpoint:/v1/embeddings}']?.values?.['p(95)'] || 0),
        count: data.metrics['http_reqs{endpoint:/v1/embeddings}']?.values?.count || 0,
      },
    },
  };
  
  // Generate outputs
  return {
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
    'benchmarks/results/rest_api_' + timestamp + '.json': JSON.stringify(aggregateMetrics, null, 2),
    'benchmarks/results/rest_api_' + timestamp + '.html': htmlReport(data),
    'benchmarks/results/rest_api_latest.json': JSON.stringify(aggregateMetrics, null, 2),
    'benchmarks/results/rest_api_latest.html': htmlReport(data),
  };
}