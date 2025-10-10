// WebSocket client wrapper with reconnection and message buffering

import { WebSocketMessage, ConnectionStatus } from '@/types';

export interface WebSocketOptions {
  url: string;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  heartbeatInterval?: number;
  enableLogging?: boolean;
}

// Browser-compatible EventEmitter implementation
class EventEmitter {
  private events: Map<string, Array<(...args: any[]) => void>> = new Map();

  on(event: string, listener: (...args: any[]) => void): void {
    if (!this.events.has(event)) {
      this.events.set(event, []);
    }
    this.events.get(event)!.push(listener);
  }

  emit(event: string, ...args: any[]): void {
    const listeners = this.events.get(event);
    if (listeners) {
      listeners.forEach(listener => {
        try {
          listener(...args);
        } catch (error) {
          console.error(`Error in event listener for ${event}:`, error);
        }
      });
    }
  }

  removeAllListeners(event?: string): void {
    if (event) {
      this.events.delete(event);
    } else {
      this.events.clear();
    }
  }

  removeListener(event: string, listener: (...args: any[]) => void): void {
    const listeners = this.events.get(event);
    if (listeners) {
      const index = listeners.indexOf(listener);
      if (index !== -1) {
        listeners.splice(index, 1);
      }
    }
  }
}

export class WebSocketClient extends EventEmitter {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectInterval: number;
  private maxReconnectAttempts: number;
  private heartbeatInterval: number;
  private enableLogging: boolean;
  private reconnectAttempts = 0;
  private heartbeatTimer?: NodeJS.Timeout;
  private reconnectTimer?: NodeJS.Timeout;
  private messageQueue: WebSocketMessage[] = [];
  private connectionStatus: ConnectionStatus = 'disconnected';
  private isIntentionallyClosed = false;

  constructor(options: WebSocketOptions) {
    super();
    this.url = options.url;
    this.reconnectInterval = options.reconnectInterval || 5000;
    this.maxReconnectAttempts = options.maxReconnectAttempts || 5;
    this.heartbeatInterval = options.heartbeatInterval || 30000;
    this.enableLogging = options.enableLogging || false;
  }

  connect(token?: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.log('Already connected');
      return;
    }

    this.isIntentionallyClosed = false;
    this.setConnectionStatus('connecting');

    const wsUrl = token ? `${this.url}?token=${token}` : this.url;
    
    try {
      this.ws = new WebSocket(wsUrl);
      this.setupEventHandlers();
    } catch (error) {
      this.log('Connection error:', error);
      this.handleReconnect();
    }
  }

  private setupEventHandlers(): void {
    if (!this.ws) return;

    this.ws.onopen = () => {
      this.log('WebSocket connected');
      this.setConnectionStatus('connected');
      this.reconnectAttempts = 0;
      this.startHeartbeat();
      this.flushMessageQueue();
      this.emit('connected');
    };

    this.ws.onmessage = (event) => {
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        this.log('Received message:', message.type);
        this.handleMessage(message);
      } catch (error) {
        this.log('Failed to parse message:', error);
      }
    };

    this.ws.onerror = (error) => {
      this.log('WebSocket error:', error);
      this.setConnectionStatus('error');
      this.emit('error', error);
    };

    this.ws.onclose = (event) => {
      this.log('WebSocket closed:', event.code, event.reason);
      this.setConnectionStatus('disconnected');
      this.stopHeartbeat();
      this.emit('disconnected', event);
      
      if (!this.isIntentionallyClosed) {
        this.handleReconnect();
      }
    };
  }

  private handleMessage(message: WebSocketMessage): void {
    switch (message.type) {
      case 'ping':
        this.sendPong(message.id);
        break;
      case 'pong':
        this.log('Received pong');
        break;
      case 'stream':
        this.emit('stream', message);
        break;
      case 'complete':
        this.emit('complete', message);
        break;
      case 'error':
        this.emit('messageError', message);
        break;
      case 'connection':
        this.emit('connection', message);
        break;
      case 'status':
        this.emit('status', message);
        break;
      default:
        this.emit('message', message);
    }
  }

  send(message: WebSocketMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(message));
        this.log('Sent message:', message.type);
      } catch (error) {
        this.log('Failed to send message:', error);
        this.queueMessage(message);
      }
    } else {
      this.log('WebSocket not ready, queueing message');
      this.queueMessage(message);
    }
  }

  sendChat(
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
  ): void {
    const wsMessage: WebSocketMessage = {
      type: 'chat',
      id,
      data: {
        message,
        model,
        stream: options?.stream ?? true,
        temperature: options?.temperature,
        max_tokens: options?.maxTokens,
        system_prompt: options?.systemPrompt,
        conversation_history: options?.conversationHistory,
      },
    };

    this.send(wsMessage);
  }

  private sendPing(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      const message: WebSocketMessage = {
        type: 'ping',
        id: `ping-${Date.now()}`,
        timestamp: new Date().toISOString(),
      };
      this.send(message);
    }
  }

  private sendPong(pingId: string): void {
    const message: WebSocketMessage = {
      type: 'pong',
      id: pingId,
      timestamp: new Date().toISOString(),
    };
    this.send(message);
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      this.sendPing();
    }, this.heartbeatInterval);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = undefined;
    }
  }

  private handleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      this.log('Max reconnection attempts reached');
      this.emit('maxReconnectAttemptsReached');
      return;
    }

    this.reconnectAttempts++;
    this.log(`Reconnecting... (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

    this.reconnectTimer = setTimeout(() => {
      this.connect();
    }, this.reconnectInterval * Math.pow(1.5, this.reconnectAttempts - 1));
  }

  private queueMessage(message: WebSocketMessage): void {
    this.messageQueue.push(message);
    if (this.messageQueue.length > 100) {
      this.messageQueue.shift(); // Remove oldest message
    }
  }

  private flushMessageQueue(): void {
    while (this.messageQueue.length > 0) {
      const message = this.messageQueue.shift();
      if (message) {
        this.send(message);
      }
    }
  }

  private setConnectionStatus(status: ConnectionStatus): void {
    this.connectionStatus = status;
    this.emit('statusChange', status);
  }

  getConnectionStatus(): ConnectionStatus {
    return this.connectionStatus;
  }

  disconnect(): void {
    this.isIntentionallyClosed = true;
    
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = undefined;
    }

    this.stopHeartbeat();
    
    if (this.ws) {
      this.ws.close(1000, 'Client disconnecting');
      this.ws = null;
    }
    
    this.setConnectionStatus('disconnected');
  }

  private log(...args: unknown[]): void {
    if (this.enableLogging) {
      console.log('[WebSocket]', ...args);
    }
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  cancelStream(messageId: string): void {
    const message: WebSocketMessage = {
      type: 'cancel',
      id: messageId,
    };
    this.send(message);
  }
}