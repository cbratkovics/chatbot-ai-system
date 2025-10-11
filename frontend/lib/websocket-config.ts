/**
 * WebSocket Configuration
 * Backend exposes: /ws (echo) and /ws/chat (full chat)
 * Always use NEXT_PUBLIC_WS_URL env var directly - it points to /ws/chat
 */

import { config } from './config';

export const WS_URL = config.NEXT_PUBLIC_WS_URL;

if (!WS_URL) {
  throw new Error('NEXT_PUBLIC_WS_URL environment variable is required');
}

if (!WS_URL.includes('/ws/chat')) {
  console.warn(
    `WebSocket URL should point to /ws/chat endpoint. Current: ${WS_URL}`
  );
}

// For debugging in development
if (process.env.NODE_ENV === 'development') {
  console.log('WebSocket Configuration:', {
    url: WS_URL,
    protocol: WS_URL.startsWith('wss://') ? 'secure' : 'insecure',
    endpoint: new URL(WS_URL).pathname
  });
}

export default WS_URL;
