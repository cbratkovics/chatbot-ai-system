import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { Message, Model, Conversation } from '@/types';

export interface ChatMessage extends Omit<Message, 'id'> {
  id: string;
  isStreaming?: boolean;
  functionCalls?: {
    name: string;
    arguments: Record<string, unknown>;
    result?: unknown;
  }[];
}

interface ChatStore {
  // Session state
  currentSession: Conversation | null;
  sessions: Conversation[];

  // Message state
  messages: ChatMessage[];
  streamingMessage: string;

  // Model state
  models: Model[];
  selectedModel: string;
  
  // UI state
  isLoading: boolean;
  error: string | null;
  
  // Actions
  setCurrentSession: (session: Conversation | null) => void;
  addSession: (session: Conversation) => void;
  setMessages: (messages: ChatMessage[]) => void;
  addMessage: (message: ChatMessage) => void;
  updateMessage: (id: string, updates: Partial<ChatMessage>) => void;
  appendToStreamingMessage: (content: string) => void;
  setStreamingMessage: (content: string) => void;
  setModels: (models: Model[]) => void;
  setSelectedModel: (model: string) => void;
  setIsLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatStore>()(
  persist(
    (set) => ({
      // Initial state
      currentSession: null,
      sessions: [],
      messages: [],
      streamingMessage: '',
      models: [],
      selectedModel: 'gpt-4o-mini',
      isLoading: false,
      error: null,

      // Actions
      setCurrentSession: (session) => set({ currentSession: session }),
      
      addSession: (session) =>
        set((state) => ({ sessions: [session, ...state.sessions] })),
      
      setMessages: (messages) => set({ messages }),
      
      addMessage: (message) =>
        set((state) => ({ messages: [...state.messages, message] })),
      
      updateMessage: (id, updates) =>
        set((state) => ({
          messages: state.messages.map((msg) =>
            msg.id === id ? { ...msg, ...updates } : msg
          ),
        })),
      
      appendToStreamingMessage: (content) =>
        set((state) => ({ streamingMessage: state.streamingMessage + content })),
      
      setStreamingMessage: (content) => set({ streamingMessage: content }),
      
      setModels: (models) => set({ models }),
      
      setSelectedModel: (model) => set({ selectedModel: model }),
      
      setIsLoading: (loading) => set({ isLoading: loading }),
      
      setError: (error) => set({ error }),
      
      clearMessages: () => set({ messages: [], streamingMessage: '' }),
    }),
    {
      name: 'chat-store',
      partialize: (state) => ({
        sessions: state.sessions,
        selectedModel: state.selectedModel,
      }),
    }
  )
);