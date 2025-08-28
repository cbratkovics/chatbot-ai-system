import ws from 'k6/ws';
import { check, sleep } from 'k6';
import { Trend, Rate, Counter, Gauge } from 'k6/metrics';
import { randomString, randomItem } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

// Custom metrics
const connectionTime = new Trend('ws_connection_time', true);
const messageLatency = new Trend('ws_message_latency', true);
const messagesReceived = new Counter('ws_messages_received');
const messagesSent = new Counter('ws_messages_sent');
const errorRate = new Rate('ws_errors');
const activeConnections = new Gauge('ws_active_connections');
const streamingLatency = new Trend('ws_streaming_latency', true);
const reconnectionTime = new Trend('ws_reconnection_time', true);

// Test configuration
export const options = {
  scenarios: {
    // Scenario 1: Gradual ramp-up to test connection handling
    connection_rampup: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 50 },  // Ramp to 50 users
        { duration: '3m', target: 100 }, // Ramp to 100 users
        { duration: '5m', target: 100 }, // Stay at 100 users
        { duration: '2m', target: 0 },   // Ramp down
      ],
      startTime: '0s',
    },
    // Scenario 2: Spike test for resilience
    spike_test: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 10 },  // Warm up
        { duration: '10s', target: 200 }, // Spike to 200 users
        { duration: '1m', target: 200 },  // Hold spike
        { duration: '30s', target: 10 },  // Back to normal
      ],
      startTime: '15m',
    },
    // Scenario 3: Sustained load for streaming
    streaming_load: {
      executor: 'constant-vus',
      vus: 50,
      duration: '10m',
      startTime: '20m',
    },
  },
  thresholds: {
    'ws_connection_time': ['p(95)<1000', 'p(99)<2000'], // Connection within 1-2 seconds
    'ws_message_latency': ['p(95)<200', 'p(99)<500'],   // Message latency targets
    'ws_streaming_latency': ['p(95)<50', 'p(99)<100'],  // Streaming chunks latency
    'ws_errors': ['rate<0.01'],                         // Less than 1% error rate
    'ws_reconnection_time': ['p(95)<3000'],             // Reconnect within 3 seconds
  },
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(50)', 'p(95)', 'p(99)'],
};

// Configuration
const WS_URL = __ENV.WS_URL || 'ws://localhost:8000/ws';
const AUTH_TOKEN = __ENV.AUTH_TOKEN || 'test-jwt-token';
const TENANT_ID = __ENV.TENANT_ID || 'test-tenant';

// Test data
const testPrompts = [
  'What is the weather today?',
  'Can you help me write a Python function?',
  'Explain quantum computing in simple terms',
  'What are the best practices for REST API design?',
  'How do I optimize database queries?',
  'Tell me about machine learning algorithms',
  'What is the difference between TCP and UDP?',
  'How do I implement authentication in a web app?',
  'Explain Docker containers',
  'What are microservices?',
];

const models = ['gpt-4', 'claude-3-opus', 'llama-3-70b'];

export default function () {
  const userId = `user_${__VU}_${randomString(8)}`;
  const sessionId = `session_${randomString(16)}`;
  const startTime = Date.now();
  
  // Test WebSocket connection with authentication
  const params = {
    headers: {
      'Authorization': `Bearer ${AUTH_TOKEN}`,
      'X-Tenant-ID': TENANT_ID,
      'X-User-ID': userId,
      'X-Session-ID': sessionId,
    },
    tags: { type: 'websocket', scenario: __ENV.scenario },
  };

  const response = ws.connect(WS_URL, params, function (socket) {
    const connectTime = Date.now() - startTime;
    connectionTime.add(connectTime);
    activeConnections.add(1);
    
    // Connection established handler
    socket.on('open', () => {
      console.log(`User ${userId}: Connected in ${connectTime}ms`);
      
      // Send initial configuration
      socket.send(JSON.stringify({
        type: 'config',
        data: {
          model: randomItem(models),
          temperature: 0.7,
          maxTokens: 1000,
          streaming: true,
        }
      }));
      
      // Simulate conversation
      let messageCount = 0;
      const maxMessages = 10;
      
      socket.setInterval(() => {
        if (messageCount < maxMessages) {
          const prompt = randomItem(testPrompts);
          const messageId = `msg_${randomString(16)}`;
          const sentTime = Date.now();
          
          // Send chat message
          socket.send(JSON.stringify({
            type: 'chat',
            id: messageId,
            data: {
              message: prompt,
              context: messageCount > 0 ? 'continuation' : 'new',
              timestamp: sentTime,
            }
          }));
          
          messagesSent.add(1);
          messageCount++;
          
          // Store sent time for latency calculation
          socket.messageTimestamps = socket.messageTimestamps || {};
          socket.messageTimestamps[messageId] = sentTime;
        }
      }, 3000); // Send message every 3 seconds
    });

    // Handle incoming messages
    socket.on('message', (data) => {
      messagesReceived.add(1);
      
      try {
        const message = JSON.parse(data);
        const receivedTime = Date.now();
        
        switch (message.type) {
          case 'response':
            // Calculate message round-trip latency
            if (socket.messageTimestamps && socket.messageTimestamps[message.id]) {
              const latency = receivedTime - socket.messageTimestamps[message.id];
              messageLatency.add(latency);
              delete socket.messageTimestamps[message.id];
            }
            break;
            
          case 'stream_start':
            // Track streaming start
            socket.streamStart = socket.streamStart || {};
            socket.streamStart[message.id] = receivedTime;
            break;
            
          case 'stream_chunk':
            // Track streaming chunks
            if (socket.streamStart && socket.streamStart[message.id]) {
              const chunkLatency = receivedTime - socket.streamStart[message.id];
              streamingLatency.add(chunkLatency);
              socket.streamStart[message.id] = receivedTime; // Update for next chunk
            }
            break;
            
          case 'stream_end':
            // Clean up streaming tracking
            if (socket.streamStart && socket.streamStart[message.id]) {
              delete socket.streamStart[message.id];
            }
            break;
            
          case 'error':
            errorRate.add(1);
            console.error(`Error for user ${userId}: ${message.error}`);
            break;
            
          case 'pong':
            // Heartbeat response
            break;
            
          default:
            console.log(`Unknown message type: ${message.type}`);
        }
      } catch (e) {
        errorRate.add(1);
        console.error(`Failed to parse message: ${e}`);
      }
    });

    // Test heartbeat mechanism
    socket.setInterval(() => {
      socket.send(JSON.stringify({ type: 'ping', timestamp: Date.now() }));
    }, 30000); // Send ping every 30 seconds

    // Handle connection errors
    socket.on('error', (e) => {
      errorRate.add(1);
      console.error(`WebSocket error for user ${userId}: ${e}`);
    });

    // Handle connection close
    socket.on('close', () => {
      activeConnections.add(-1);
      console.log(`User ${userId}: Connection closed`);
    });

    // Test reconnection logic
    socket.setTimeout(() => {
      if (Math.random() < 0.1) { // 10% chance to test reconnection
        console.log(`User ${userId}: Testing reconnection`);
        socket.close();
        
        // Attempt reconnection
        const reconnectStart = Date.now();
        sleep(1);
        
        ws.connect(WS_URL, params, function(newSocket) {
          const reconnectDuration = Date.now() - reconnectStart;
          reconnectionTime.add(reconnectDuration);
          console.log(`User ${userId}: Reconnected in ${reconnectDuration}ms`);
          
          // Continue with new socket
          newSocket.setTimeout(() => {
            newSocket.close();
          }, 10000);
        });
      }
    }, 30000); // Test reconnection after 30 seconds

    // Keep connection open for test duration
    socket.setTimeout(() => {
      socket.close();
    }, 60000); // Close after 60 seconds
  });

  // Check connection was successful
  check(response, {
    'WebSocket connection established': (r) => r && r.status === 101,
  });
  
  // Add some think time between user connections
  sleep(Math.random() * 2);
}

// Handle test summary
export function handleSummary(data) {
  const summary = {
    timestamp: new Date().toISOString(),
    test: 'websocket_load_test',
    metrics: {
      connection: {
        p50: data.metrics.ws_connection_time ? data.metrics.ws_connection_time.values['p(50)'] : 0,
        p95: data.metrics.ws_connection_time ? data.metrics.ws_connection_time.values['p(95)'] : 0,
        p99: data.metrics.ws_connection_time ? data.metrics.ws_connection_time.values['p(99)'] : 0,
      },
      latency: {
        p50: data.metrics.ws_message_latency ? data.metrics.ws_message_latency.values['p(50)'] : 0,
        p95: data.metrics.ws_message_latency ? data.metrics.ws_message_latency.values['p(95)'] : 0,
        p99: data.metrics.ws_message_latency ? data.metrics.ws_message_latency.values['p(99)'] : 0,
      },
      streaming: {
        p50: data.metrics.ws_streaming_latency ? data.metrics.ws_streaming_latency.values['p(50)'] : 0,
        p95: data.metrics.ws_streaming_latency ? data.metrics.ws_streaming_latency.values['p(95)'] : 0,
        p99: data.metrics.ws_streaming_latency ? data.metrics.ws_streaming_latency.values['p(99)'] : 0,
      },
      reconnection: {
        p95: data.metrics.ws_reconnection_time ? data.metrics.ws_reconnection_time.values['p(95)'] : 0,
      },
      throughput: {
        messages_sent: data.metrics.ws_messages_sent ? data.metrics.ws_messages_sent.values.count : 0,
        messages_received: data.metrics.ws_messages_received ? data.metrics.ws_messages_received.values.count : 0,
      },
      errors: {
        rate: data.metrics.ws_errors ? data.metrics.ws_errors.values.rate : 0,
      },
      max_concurrent_users: data.metrics.vus_max ? data.metrics.vus_max.values.value : 0,
    },
    thresholds: data.thresholds,
  };

  return {
    'benchmarks/results/websocket_test.json': JSON.stringify(summary, null, 2),
    'stdout': textSummary(data, { indent: ' ', enableColors: true }),
  };
}

// Helper function for text summary
function textSummary(data, options) {
  const indent = options.indent || '';
  let output = '\n=== WebSocket Load Test Results ===\n\n';
  
  // Connection metrics
  if (data.metrics.ws_connection_time) {
    output += `${indent}Connection Time:\n`;
    output += `${indent}  P50: ${data.metrics.ws_connection_time.values['p(50)'].toFixed(2)}ms\n`;
    output += `${indent}  P95: ${data.metrics.ws_connection_time.values['p(95)'].toFixed(2)}ms\n`;
    output += `${indent}  P99: ${data.metrics.ws_connection_time.values['p(99)'].toFixed(2)}ms\n\n`;
  }
  
  // Message latency
  if (data.metrics.ws_message_latency) {
    output += `${indent}Message Latency:\n`;
    output += `${indent}  P50: ${data.metrics.ws_message_latency.values['p(50)'].toFixed(2)}ms\n`;
    output += `${indent}  P95: ${data.metrics.ws_message_latency.values['p(95)'].toFixed(2)}ms\n`;
    output += `${indent}  P99: ${data.metrics.ws_message_latency.values['p(99)'].toFixed(2)}ms\n\n`;
  }
  
  // Streaming performance
  if (data.metrics.ws_streaming_latency) {
    output += `${indent}Streaming Latency:\n`;
    output += `${indent}  P50: ${data.metrics.ws_streaming_latency.values['p(50)'].toFixed(2)}ms\n`;
    output += `${indent}  P95: ${data.metrics.ws_streaming_latency.values['p(95)'].toFixed(2)}ms\n`;
    output += `${indent}  P99: ${data.metrics.ws_streaming_latency.values['p(99)'].toFixed(2)}ms\n\n`;
  }
  
  // Throughput
  if (data.metrics.ws_messages_sent && data.metrics.ws_messages_received) {
    output += `${indent}Throughput:\n`;
    output += `${indent}  Messages Sent: ${data.metrics.ws_messages_sent.values.count}\n`;
    output += `${indent}  Messages Received: ${data.metrics.ws_messages_received.values.count}\n\n`;
  }
  
  // Error rate
  if (data.metrics.ws_errors) {
    output += `${indent}Error Rate: ${(data.metrics.ws_errors.values.rate * 100).toFixed(2)}%\n\n`;
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