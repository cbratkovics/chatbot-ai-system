// Type definitions for the chat application

export type Role = 'user' | 'assistant' | 'system';
export type MessageStatus = 'sending' | 'sent' | 'error' | 'streaming';
export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

export interface Message {
  id: string;
  role: Role;
  content: string;
  timestamp: Date;
  status?: MessageStatus;
  model?: string;
  cached?: boolean;
  error?: string;
  tokens?: number;
  isStreaming?: boolean;
  streamingContent?: string;
}

export interface ChatRequest {
  message: string;
  model: string;
  stream?: boolean;
  temperature?: number;
  maxTokens?: number;
  systemPrompt?: string;
  conversationHistory?: Array<{
    role: Role;
    content: string;
  }>;
}

export interface ChatResponse {
  response: string;
  model: string;
  requestId: string;
  timestamp: string;
  cached: boolean;
  cacheKey?: string;
  similarityScore?: number;
  usage?: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
}

export interface StreamChunk {
  chunk: string;
  index: number;
  finished: boolean;
  tokensPerSecond?: number;
}

export interface WebSocketMessage {
  type: 'chat' | 'stream' | 'complete' | 'error' | 'ping' | 'pong' | 'connection' | 'status';
  id: string;
  data?: any;
  timestamp?: string;
}

export interface Model {
  id: string;
  name: string;
  provider: 'openai' | 'anthropic';
  contextLength: number;
  description?: string;
  capabilities?: string[];
  available: boolean;
  costPerToken?: {
    input: number;
    output: number;
  };
}

export interface UserPreferences {
  theme: 'light' | 'dark' | 'system';
  model: string;
  temperature: number;
  maxTokens: number;
  enableStreaming: boolean;
  enableCache: boolean;
  fontSize: 'small' | 'medium' | 'large';
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
  model?: string;
}