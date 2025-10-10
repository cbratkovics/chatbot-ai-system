// HTTP API client for the chatbot backend

import { ChatRequest, ChatResponse, Model, Message, Conversation } from '@/types';

// Re-export types for use by other modules
export type { Message, Model };
export type { Conversation as Session };

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

export class APIClient {
  private baseURL: string;
  private headers: HeadersInit;

  constructor(baseURL?: string) {
    this.baseURL = baseURL || API_URL;
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
    return this.request<ChatResponse>('/completions', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  // Model endpoints
  async getModels(): Promise<Model[]> {
    const response = await this.request<{ models: Model[] }>('/models');
    return response.models || [];
  }

  async getModel(modelId: string): Promise<Model> {
    return this.request<Model>(`/models/${modelId}`);
  }

  // Health check
  async health(): Promise<{ status: string; timestamp: string }> {
    return this.request('/health');
  }
}

// Export singleton instance
export const apiClient = new APIClient();