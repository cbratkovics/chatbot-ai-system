// Centralized API types for chat requests and responses

export type ChatRole = "system" | "user" | "assistant";

export type ChatMessage = {
  role: ChatRole;
  content: string;
};

// Pick ONE naming convention for token limit and stick with it across the app.
// If the backend expects snake_case, keep max_tokens here and convert in the client if needed.
export interface ChatRequest {
  model: string;
  messages: ChatMessage[];
  stream?: boolean;
  temperature?: number;
  // Use exactly one of these across the app; keep both optional to ease migration:
  max_tokens?: number; // snake_case (common for OpenAI-style servers)
  maxTokens?: number;  // camelCase (if your TS code prefers this)
}

export interface ChatStreamRequest extends ChatRequest {
  stream: true;
}

export interface ChatResponse {
  id?: string;
  created?: number;
  model: string;
  choices?: Array<{ message: ChatMessage; finish_reason?: string }>;
  response?: string; // For compatibility with existing response format
  requestId?: string;
  timestamp?: string;
  cached?: boolean;
  cacheKey?: string;
  similarityScore?: number;
  usage?: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
}
