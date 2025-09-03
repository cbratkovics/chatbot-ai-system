// WebSocket React hook for managing WebSocket connections

import { useEffect, useRef, useState, useCallback } from 'react';
import { WebSocketClient, WebSocketOptions } from '@/lib/websocket';
import { WebSocketMessage, ConnectionStatus } from '@/types';

interface UseWebSocketOptions extends Partial<WebSocketOptions> {
  autoConnect?: boolean;
  token?: string;
  onMessage?: (message: WebSocketMessage) => void;
  onStatusChange?: (status: ConnectionStatus) => void;
  onError?: (error: Error) => void;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const {
    autoConnect = true,
    token,
    onMessage,
    onStatusChange,
    onError,
    ...wsOptions
  } = options;

  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [isConnected, setIsConnected] = useState(false);
  const clientRef = useRef<WebSocketClient | null>(null);

  // Initialize WebSocket client
  useEffect(() => {
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws/chat';
    
    const client = new WebSocketClient({
      url: wsUrl,
      reconnectInterval: Number(process.env.NEXT_PUBLIC_WS_RECONNECT_INTERVAL) || 5000,
      maxReconnectAttempts: Number(process.env.NEXT_PUBLIC_WS_MAX_RECONNECT_ATTEMPTS) || 5,
      heartbeatInterval: Number(process.env.NEXT_PUBLIC_WS_HEARTBEAT_INTERVAL) || 30000,
      enableLogging: process.env.NODE_ENV === 'development',
      ...wsOptions,
    });

    // Set up event listeners
    client.on('connected', () => {
      setIsConnected(true);
      setStatus('connected');
    });

    client.on('disconnected', () => {
      setIsConnected(false);
      setStatus('disconnected');
    });

    client.on('statusChange', (newStatus: ConnectionStatus) => {
      setStatus(newStatus);
      onStatusChange?.(newStatus);
    });

    client.on('message', (message: WebSocketMessage) => {
      onMessage?.(message);
    });

    client.on('stream', (message: WebSocketMessage) => {
      onMessage?.(message);
    });

    client.on('complete', (message: WebSocketMessage) => {
      onMessage?.(message);
    });

    client.on('error', (error: Error) => {
      console.error('WebSocket error:', error);
      onError?.(error);
    });

    client.on('messageError', (message: WebSocketMessage) => {
      console.error('Message error:', message);
      if (message.data?.error) {
        onError?.(new Error(message.data.error));
      }
    });

    clientRef.current = client;

    // Auto-connect if enabled
    if (autoConnect) {
      client.connect(token);
    }

    // Cleanup
    return () => {
      client.disconnect();
      client.removeAllListeners();
    };
  }, []);

  // Connect function
  const connect = useCallback((authToken?: string) => {
    if (clientRef.current) {
      clientRef.current.connect(authToken || token);
    }
  }, [token]);

  // Disconnect function
  const disconnect = useCallback(() => {
    if (clientRef.current) {
      clientRef.current.disconnect();
    }
  }, []);

  // Send message function
  const sendMessage = useCallback((message: WebSocketMessage) => {
    if (clientRef.current) {
      clientRef.current.send(message);
    }
  }, []);

  // Send chat message function
  const sendChat = useCallback(
    (
      id: string,
      message: string,
      model: string,
      options?: {
        stream?: boolean;
        temperature?: number;
        maxTokens?: number;
        systemPrompt?: string;
        conversationHistory?: Array<{ role: string; content: string }>;
      }
    ) => {
      if (clientRef.current) {
        clientRef.current.sendChat(id, message, model, options);
      }
    },
    []
  );

  // Cancel stream function
  const cancelStream = useCallback((messageId: string) => {
    if (clientRef.current) {
      clientRef.current.cancelStream(messageId);
    }
  }, []);

  return {
    status,
    isConnected,
    connect,
    disconnect,
    sendMessage,
    sendChat,
    cancelStream,
    client: clientRef.current,
  };
}