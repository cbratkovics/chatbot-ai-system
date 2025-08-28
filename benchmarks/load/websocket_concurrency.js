import ws from 'k6/ws';
import { check, sleep } from 'k6';
import { Counter, Trend, Rate, Gauge } from 'k6/metrics';
import { htmlReport } from 'https://raw.githubusercontent.com/benc-uk/k6-reporter/main/dist/bundle.js';
import { textSummary } from 'https://jslib.k6.io/k6-summary/0.0.2/index.js';
import exec from 'k6/execution';

// Custom metrics
const wsConnectTime = new Trend('ws_connect_time', true);
const wsMessageLatency = new Trend('ws_message_latency', true);
const wsMessagesReceived = new Counter('ws_messages_received');
const wsMessagesSent = new Counter('ws_messages_sent');
const wsConnectionsActive = new Gauge('ws_connections_active');
const wsConnectionsFailed = new Counter('ws_connections_failed');
const wsUnexpectedClose = new Counter('ws_unexpected_close');
const wsErrorRate = new Rate('ws_errors');
const wsThroughput = new Trend('ws_throughput_bytes');

// Configuration
const WS_URL = __ENV.WS_URL || 'ws://localhost:8000/ws';
const API_KEY = __ENV.API_KEY || 'test-tenant-key-123';
const TIMESTAMP = new Date().toISOString().replace(/[:.]/g, '-');

// Test scenarios
export const options = {
  scenarios: {
    // Quick connectivity test
    smoke: {
      executor: 'constant-vus',
      vus: 5,
      duration: '30s',
      tags: { scenario: 'smoke' },
    },
    // Concurrent connection test
    concurrency: {
      executor: 'constant-arrival-rate',
      rate: 120,  // 120 connections total
      duration: '30s',
      preAllocatedVUs: 150,
      maxVUs: 200,
      startTime: '31s',
      tags: { scenario: 'concurrency' },
    },
    // Sustained load test
    soak: {
      executor: 'constant-vus',
      vus: 120,
      duration: '10m',
      startTime: '1m32s',
      tags: { scenario: 'soak' },
    },
  },
  thresholds: {
    ws_connect_time: ['p(95)<1000', 'p(99)<2000'],  // Connection time
    ws_message_latency: ['p(50)<100', 'p(95)<150', 'p(99)<200'],  // Message RTT
    ws_errors: ['rate<0.01'],  // < 1% error rate
    ws_connections_active: ['value>=100'],  // At least 100 concurrent
    checks: ['rate>0.99'],  // 99% check pass rate
  },
};

// Test messages
const testMessages = [
  { type: 'ping', payload: { timestamp: Date.now() } },
  { type: 'chat', payload: { message: 'Hello, how are you?', model: 'gpt-3.5-turbo' } },
  { type: 'stream_start', payload: { query: 'Explain WebSockets', stream: true } },
  { type: 'status', payload: { action: 'get_status' } },
  { type: 'echo', payload: { data: 'x'.repeat(1024) } },  // 1KB message
];

// Connection state tracking
const connectionMetrics = new Map();

// Helper function to generate conversation ID
function generateConversationId() {
  return `k6-test-${exec.vu.idInTest}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
}

// Main test function
export default function () {
  const conversationId = generateConversationId();
  const url = `${WS_URL}/${conversationId}`;
  const params = {
    headers: {
      'Authorization': `Bearer ${API_KEY}`,
      'X-Tenant-ID': 'test-tenant-001',
      'X-Request-ID': `ws-${exec.vu.idInTest}-${exec.scenario.iterationInTest}`,
    },
    tags: {
      conversation_id: conversationId,
      vu: exec.vu.idInTest,
      scenario: exec.scenario.name,
    },
  };
  
  const connectionStart = Date.now();
  let messageCount = 0;
  let bytesReceived = 0;
  let lastPingTime = Date.now();
  let connectionEstablished = false;
  
  // Establish WebSocket connection
  const response = ws.connect(url, params, function (socket) {
    const connectDuration = Date.now() - connectionStart;
    wsConnectTime.add(connectDuration);
    wsConnectionsActive.add(1);
    connectionEstablished = true;
    
    // Connection established check
    check(response, {
      'ws connection successful': (r) => r && r.status === 101,
      'ws connect time < 1s': () => connectDuration < 1000,
    }) || wsErrorRate.add(1);
    
    // Set up message handlers
    socket.on('open', () => {
      console.log(`WS connected: ${conversationId} (VU: ${exec.vu.idInTest})`);
      
      // Send initial authentication/setup message
      const authMessage = JSON.stringify({
        type: 'auth',
        payload: {
          token: API_KEY,
          tenant_id: 'test-tenant-001',
        },
      });
      socket.send(authMessage);
      wsMessagesSent.add(1);
    });
    
    socket.on('message', (data) => {
      const receiveTime = Date.now();
      messageCount++;
      wsMessagesReceived.add(1);
      
      try {
        const message = typeof data === 'string' ? JSON.parse(data) : data;
        bytesReceived += JSON.stringify(message).length;
        wsThroughput.add(bytesReceived);
        
        // Calculate latency for ping/pong messages
        if (message.type === 'pong' && message.payload?.timestamp) {
          const latency = receiveTime - message.payload.timestamp;
          wsMessageLatency.add(latency);
          
          check(null, {
            'message latency < 150ms': () => latency < 150,
            'message latency < 200ms': () => latency < 200,
          });
        }
        
        // Handle different message types
        switch (message.type) {
          case 'auth_success':
            console.log(`Auth successful for ${conversationId}`);
            break;
          case 'error':
            console.error(`WS error: ${message.payload?.message}`);
            wsErrorRate.add(1);
            break;
          case 'stream_chunk':
            // Handle streaming data
            break;
          default:
            // Process other message types
            break;
        }
      } catch (e) {
        console.error(`Failed to parse message: ${e.message}`);
        wsErrorRate.add(1);
      }
    });
    
    socket.on('close', (code) => {
      wsConnectionsActive.add(-1);
      
      if (code !== 1000 && code !== 1001) {  // Abnormal closure
        wsUnexpectedClose.add(1);
        console.error(`Unexpected close for ${conversationId}: code ${code}`);
      }
      
      // Log connection statistics
      const duration = Date.now() - connectionStart;
      console.log(`Connection closed: ${conversationId}, duration: ${duration}ms, messages: ${messageCount}`);
    });
    
    socket.on('error', (e) => {
      console.error(`WS error for ${conversationId}: ${e}`);
      wsErrorRate.add(1);
      wsConnectionsFailed.add(1);
    });
    
    // Connection test sequence
    socket.setTimeout(() => {
      // Send periodic messages during connection lifetime
      const messageInterval = setInterval(() => {
        if (socket.state === 1) {  // OPEN state
          // Select random message type
          const testMessage = testMessages[Math.floor(Math.random() * testMessages.length)];
          
          // Add timestamp for latency measurement
          if (testMessage.type === 'ping') {
            testMessage.payload.timestamp = Date.now();
            lastPingTime = Date.now();
          }
          
          const messageStr = JSON.stringify(testMessage);
          socket.send(messageStr);
          wsMessagesSent.add(1);
          
          // Performance checks
          check(null, {
            'can send message': () => true,
            'connection still active': () => socket.state === 1,
          });
        } else {
          clearInterval(messageInterval);
        }
      }, 1000 + Math.random() * 2000);  // Send message every 1-3 seconds
      
      // Cleanup on socket close
      socket.on('close', () => {
        clearInterval(messageInterval);
      });
      
    }, 100);
    
    // Maintain connection for scenario duration
    const scenarioDuration = exec.scenario.name === 'soak' ? 600 : 30;  // seconds
    socket.setInterval(() => {
      // Heartbeat to keep connection alive
      if (socket.state === 1) {
        socket.ping();
      }
    }, 30000);  // 30 second heartbeat
    
    // Hold connection open
    sleep(scenarioDuration);
    
    // Graceful close
    if (socket.state === 1) {
      socket.close(1000, 'Test completed');
    }
  });
  
  // Check if connection failed to establish
  if (!connectionEstablished) {
    wsConnectionsFailed.add(1);
    wsErrorRate.add(1);
  }
  
  // Small delay between connection attempts
  sleep(0.1);
}

// Generate summary report
export function handleSummary(data) {
  const timestamp = TIMESTAMP;
  
  // Calculate WebSocket-specific metrics
  const wsMetrics = {
    timestamp: new Date().toISOString(),
    environment: {
      ws_url: WS_URL,
      max_vus: data.metrics.vus_max?.values?.value || 0,
      duration_ms: data.state?.testRunDurationMs || 0,
      total_iterations: data.metrics.iterations?.values?.count || 0,
    },
    concurrency: {
      max_connections: data.metrics.ws_connections_active?.values?.max || 0,
      avg_connections: Math.round(data.metrics.ws_connections_active?.values?.avg || 0),
      failed_connections: data.metrics.ws_connections_failed?.values?.count || 0,
      unexpected_closures: data.metrics.ws_unexpected_close?.values?.count || 0,
    },
    latency: {
      connect_time: {
        p50: Math.round(data.metrics.ws_connect_time?.values?.['p(50)'] || 0),
        p95: Math.round(data.metrics.ws_connect_time?.values?.['p(95)'] || 0),
        p99: Math.round(data.metrics.ws_connect_time?.values?.['p(99)'] || 0),
      },
      message_rtt: {
        p50: Math.round(data.metrics.ws_message_latency?.values?.['p(50)'] || 0),
        p95: Math.round(data.metrics.ws_message_latency?.values?.['p(95)'] || 0),
        p99: Math.round(data.metrics.ws_message_latency?.values?.['p(99)'] || 0),
      },
    },
    throughput: {
      messages_sent: data.metrics.ws_messages_sent?.values?.count || 0,
      messages_received: data.metrics.ws_messages_received?.values?.count || 0,
      total_bytes: data.metrics.ws_throughput?.values?.max || 0,
      avg_message_rate: Math.round(
        (data.metrics.ws_messages_received?.values?.count || 0) / 
        ((data.state?.testRunDurationMs || 1) / 1000)
      ),
    },
    reliability: {
      error_rate: data.metrics.ws_errors?.values?.rate || 0,
      check_pass_rate: data.metrics.checks?.values?.rate || 0,
    },
    scenarios: {},
  };
  
  // Add scenario-specific metrics
  ['smoke', 'concurrency', 'soak'].forEach(scenario => {
    const scenarioData = data.metrics[`ws_connections_active{scenario:${scenario}}`];
    if (scenarioData) {
      wsMetrics.scenarios[scenario] = {
        max_connections: scenarioData.values?.max || 0,
        avg_connections: Math.round(scenarioData.values?.avg || 0),
      };
    }
  });
  
  // Generate CSV data for analysis
  const csvHeader = 'timestamp,scenario,connections,p50_latency,p95_latency,p99_latency,error_rate\n';
  const csvRow = `${timestamp},${exec.scenario.name || 'all'},${wsMetrics.concurrency.max_connections},` +
    `${wsMetrics.latency.message_rtt.p50},${wsMetrics.latency.message_rtt.p95},` +
    `${wsMetrics.latency.message_rtt.p99},${wsMetrics.reliability.error_rate}\n`;
  
  return {
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
    'benchmarks/results/ws_' + timestamp + '.json': JSON.stringify(wsMetrics, null, 2),
    'benchmarks/results/ws_' + timestamp + '.html': htmlReport(data),
    'benchmarks/results/ws_' + timestamp + '.csv': csvHeader + csvRow,
    'benchmarks/results/ws_latest.json': JSON.stringify(wsMetrics, null, 2),
    'benchmarks/results/ws_latest.html': htmlReport(data),
    'benchmarks/results/ws_latest.csv': csvHeader + csvRow,
  };
}