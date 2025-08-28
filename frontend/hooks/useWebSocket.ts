import { useEffect, useRef, useCallback, useState } from 'react';

export interface WebSocketMessage {
  type: 'message' | 'token' | 'error' | 'complete' | 'function_call' | 'function_result';
  content?: string;
  error?: string;
  function_name?: string;
  function_args?: any;
  result?: any;
}

interface UseWebSocketOptions {
  onMessage?: (message: WebSocketMessage) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  autoReconnect?: boolean;
  reconnectInterval?: number;
}

export const useWebSocket = (
  sessionId: string | null,
  options: UseWebSocketOptions = {}
) => {
  const {
    onMessage,
    onOpen,
    onClose,
    onError,
    autoReconnect = true,
    reconnectInterval = 3000,
  } = options;

  const ws = useRef<WebSocket | null>(null);
  const reconnectTimeout = useRef<NodeJS.Timeout | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);

  const connect = useCallback(() => {
    if (!sessionId || ws.current?.readyState === WebSocket.OPEN) return;

    setIsConnecting(true);
    const wsUrl = `${process.env.NEXT_PUBLIC_WS_URL}/api/v1/chat/stream/${sessionId}`;
    
    try {
      ws.current = new WebSocket(wsUrl);

      ws.current.onopen = () => {
        setIsConnected(true);
        setIsConnecting(false);
        onOpen?.();
      };

      ws.current.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          onMessage?.(message);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      ws.current.onclose = () => {
        setIsConnected(false);
        setIsConnecting(false);
        onClose?.();

        if (autoReconnect && sessionId) {
          reconnectTimeout.current = setTimeout(() => {
            connect();
          }, reconnectInterval);
        }
      };

      ws.current.onerror = (error) => {
        setIsConnecting(false);
        onError?.(error);
      };
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      setIsConnecting(false);
    }
  }, [sessionId, onMessage, onOpen, onClose, onError, autoReconnect, reconnectInterval]);

  const disconnect = useCallback(() => {
    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current);
      reconnectTimeout.current = null;
    }

    if (ws.current) {
      ws.current.close();
      ws.current = null;
    }

    setIsConnected(false);
    setIsConnecting(false);
  }, []);

  const sendMessage = useCallback((data: any) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(data));
    } else {
      console.error('WebSocket is not connected');
    }
  }, []);

  useEffect(() => {
    if (sessionId) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [sessionId, connect, disconnect]);

  return {
    isConnected,
    isConnecting,
    sendMessage,
    disconnect,
    reconnect: connect,
  };
};