// HTTP API client for the chatbot backend

import { ChatRequest, ChatResponse, Model, Message, Conversation } from '@/types';
import { API_CONFIG } from './config';

// Re-export types for use by other modules
export type { Message, Model };
export type { Conversation as Session };

export class APIClient {
  private baseURL: string;
  private wsURL: string;
  private headers: HeadersInit;
  private timeout: number;
  private retries: number;

  constructor() {
    this.baseURL = API_CONFIG.baseURL;
    this.wsURL = API_CONFIG.wsURL;
    this.timeout = API_CONFIG.timeout;
    this.retries = API_CONFIG.retries;
    this.headers = {
      'Content-Type': 'application/json',
    };
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;
    
    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          ...this.headers,
          ...options.headers,
        },
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.error || `HTTP error! status: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error(`API request failed: ${endpoint}`, error);
      throw error;
    }
  }

  // Chat endpoints
  async chatCompletion(request: ChatRequest): Promise<ChatResponse> {
    // Transform frontend format to backend format
    const backendRequest = {
      messages: [
        // Add conversation history first if provided
        ...(request.conversationHistory || []).map(msg => ({
          role: msg.role,
          content: msg.content
        })),
        // Add the current message
        {
          role: 'user' as const,
          content: request.message
        }
      ],
      model: request.model,
      temperature: request.temperature,
      max_tokens: request.maxTokens,           // Convert camelCase to snake_case
      system_prompt: request.systemPrompt,     // Convert camelCase to snake_case
    };

    return this.request<ChatResponse>('/chat/completions', {
      method: 'POST',
      body: JSON.stringify(backendRequest),
    });
  }

  // Model endpoints
  async getModels(): Promise<Model[]> {
    const response = await this.request<{ models: Model[] }>('/chat/models');
    return response.models || [];
  }

  async getModel(modelId: string): Promise<Model> {
    return this.request<Model>(`/chat/models/${modelId}`);
  }

  // Health check
  async health(): Promise<{ status: string; timestamp: string }> {
    return this.request('/health');
  }

  // WebSocket creation
  createWebSocket(path: string): WebSocket {
    const wsUrl = `${this.wsURL}${path}`;
    return new WebSocket(wsUrl);
  }
}

// Export singleton instance
export const apiClient = new APIClient();