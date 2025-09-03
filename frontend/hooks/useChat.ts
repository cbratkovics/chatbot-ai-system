// Chat management hook with state management

import { useState, useCallback, useRef, useEffect } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { useWebSocket } from './useWebSocket';
import { apiClient } from '@/lib/api';
import { Message, Model, WebSocketMessage, Role } from '@/types';

interface UseChatOptions {
  defaultModel?: string;
  enableStreaming?: boolean;
  maxMessages?: number;
  persistMessages?: boolean;
  storageKey?: string;
}

export function useChat(options: UseChatOptions = {}) {
  const {
    defaultModel = process.env.NEXT_PUBLIC_DEFAULT_MODEL || 'gpt-3.5-turbo',
    enableStreaming = process.env.NEXT_PUBLIC_ENABLE_STREAMING === 'true',
    maxMessages = 100,
    persistMessages = true,
    storageKey = 'chat-messages',
  } = options;

  // State
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentModel, setCurrentModel] = useState<string>(defaultModel);
  const [availableModels, setAvailableModels] = useState<Model[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const streamingMessageRef = useRef<Message | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // WebSocket hook for streaming
  const {
    status: wsStatus,
    isConnected,
    sendChat,
    cancelStream,
  } = useWebSocket({
    autoConnect: enableStreaming,
    onMessage: handleWebSocketMessage,
    onError: (err) => {
      console.error('WebSocket error:', err);
      setError(err.message);
    },
  });

  // Load messages from storage on mount
  useEffect(() => {
    if (persistMessages && typeof window !== 'undefined') {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        try {
          const parsed = JSON.parse(saved);
          setMessages(parsed.map((msg: any) => ({
            ...msg,
            timestamp: new Date(msg.timestamp),
          })));
        } catch (e) {
          console.error('Failed to load messages from storage:', e);
        }
      }
    }
  }, [persistMessages, storageKey]);

  // Save messages to storage when they change
  useEffect(() => {
    if (persistMessages && typeof window !== 'undefined') {
      localStorage.setItem(storageKey, JSON.stringify(messages));
    }
  }, [messages, persistMessages, storageKey]);

  // Load available models on mount
  useEffect(() => {
    loadModels();
  }, []);

  // Load available models
  async function loadModels() {
    try {
      const models = await apiClient.getModels();
      setAvailableModels(models);
    } catch (err) {
      console.error('Failed to load models:', err);
      setError('Failed to load available models');
    }
  }

  // Handle WebSocket messages
  function handleWebSocketMessage(message: WebSocketMessage) {
    switch (message.type) {
      case 'stream':
        handleStreamChunk(message);
        break;
      case 'complete':
        handleStreamComplete(message);
        break;
      case 'error':
        handleStreamError(message);
        break;
    }
  }

  // Handle streaming chunk
  function handleStreamChunk(message: WebSocketMessage) {
    const chunk = message.data?.chunk || '';
    
    if (streamingMessageRef.current) {
      // Update existing streaming message
      streamingMessageRef.current.streamingContent = 
        (streamingMessageRef.current.streamingContent || '') + chunk;
      
      setMessages(prev => prev.map(msg =>
        msg.id === streamingMessageRef.current?.id
          ? { ...streamingMessageRef.current! }
          : msg
      ));
    }
  }

  // Handle stream completion
  function handleStreamComplete(message: WebSocketMessage) {
    if (streamingMessageRef.current) {
      const finalMessage = {
        ...streamingMessageRef.current,
        content: streamingMessageRef.current.streamingContent || '',
        streamingContent: undefined,
        isStreaming: false,
        status: 'sent' as const,
        model: message.data?.model || currentModel,
        cached: message.data?.cached || false,
        tokens: message.data?.usage?.totalTokens,
      };

      setMessages(prev => prev.map(msg =>
        msg.id === streamingMessageRef.current?.id
          ? finalMessage
          : msg
      ));

      streamingMessageRef.current = null;
      setIsLoading(false);
    }
  }

  // Handle stream error
  function handleStreamError(message: WebSocketMessage) {
    const error = message.data?.error || 'Stream error occurred';
    
    if (streamingMessageRef.current) {
      setMessages(prev => prev.map(msg =>
        msg.id === streamingMessageRef.current?.id
          ? { ...msg, status: 'error' as const, error, isStreaming: false }
          : msg
      ));
      streamingMessageRef.current = null;
    }
    
    setError(error);
    setIsLoading(false);
  }

  // Send message
  const sendMessage = useCallback(async (
    content: string,
    options?: {
      model?: string;
      temperature?: number;
      maxTokens?: number;
      systemPrompt?: string;
    }
  ) => {
    // Clear error
    setError(null);
    
    // Create user message
    const userMessage: Message = {
      id: uuidv4(),
      role: 'user' as Role,
      content,
      timestamp: new Date(),
      status: 'sent',
    };

    // Add user message
    setMessages(prev => {
      const newMessages = [...prev, userMessage];
      // Limit messages
      if (newMessages.length > maxMessages) {
        return newMessages.slice(-maxMessages);
      }
      return newMessages;
    });

    // Create assistant message placeholder
    const assistantMessage: Message = {
      id: uuidv4(),
      role: 'assistant' as Role,
      content: '',
      timestamp: new Date(),
      status: 'streaming',
      isStreaming: true,
      streamingContent: '',
      model: options?.model || currentModel,
    };

    // Add assistant message
    setMessages(prev => [...prev, assistantMessage]);
    setIsLoading(true);

    const model = options?.model || currentModel;

    // Prepare conversation history (limit to last 10 messages for context)
    const conversationHistory = messages
      .slice(-10)
      .map(msg => ({
        role: msg.role,
        content: msg.content,
      }));

    try {
      if (enableStreaming && isConnected) {
        // Use WebSocket for streaming
        streamingMessageRef.current = assistantMessage;
        
        sendChat(
          assistantMessage.id,
          content,
          model,
          {
            stream: true,
            temperature: options?.temperature,
            maxTokens: options?.maxTokens,
            systemPrompt: options?.systemPrompt,
            conversationHistory,
          }
        );
      } else {
        // Use HTTP API for non-streaming
        const response = await apiClient.chatCompletion({
          message: content,
          model,
          stream: false,
          temperature: options?.temperature,
          maxTokens: options?.maxTokens,
          systemPrompt: options?.systemPrompt,
          conversationHistory,
        });

        // Update assistant message with response
        setMessages(prev => prev.map(msg =>
          msg.id === assistantMessage.id
            ? {
                ...msg,
                content: response.response,
                status: 'sent',
                isStreaming: false,
                cached: response.cached,
                model: response.model,
                tokens: response.usage?.totalTokens,
              }
            : msg
        ));

        setIsLoading(false);
      }
    } catch (err) {
      console.error('Failed to send message:', err);
      
      // Update message with error
      setMessages(prev => prev.map(msg =>
        msg.id === assistantMessage.id
          ? { ...msg, status: 'error', error: (err as Error).message, isStreaming: false }
          : msg
      ));
      
      setError((err as Error).message);
      setIsLoading(false);
      streamingMessageRef.current = null;
    }
  }, [messages, currentModel, enableStreaming, isConnected, sendChat, maxMessages]);

  // Cancel current stream
  const cancelCurrentStream = useCallback(() => {
    if (streamingMessageRef.current) {
      cancelStream(streamingMessageRef.current.id);
      
      // Mark message as cancelled
      setMessages(prev => prev.map(msg =>
        msg.id === streamingMessageRef.current?.id
          ? {
              ...msg,
              content: msg.streamingContent || '',
              streamingContent: undefined,
              isStreaming: false,
              status: 'sent',
              error: 'Stream cancelled',
            }
          : msg
      ));
      
      streamingMessageRef.current = null;
      setIsLoading(false);
    }

    // Cancel HTTP request if any
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, [cancelStream]);

  // Clear messages
  const clearMessages = useCallback(() => {
    setMessages([]);
    if (persistMessages && typeof window !== 'undefined') {
      localStorage.removeItem(storageKey);
    }
  }, [persistMessages, storageKey]);

  // Delete message
  const deleteMessage = useCallback((messageId: string) => {
    setMessages(prev => prev.filter(msg => msg.id !== messageId));
  }, []);

  // Edit message
  const editMessage = useCallback((messageId: string, newContent: string) => {
    setMessages(prev => prev.map(msg =>
      msg.id === messageId
        ? { ...msg, content: newContent, edited: true }
        : msg
    ));
  }, []);

  // Retry message
  const retryMessage = useCallback((messageId: string) => {
    const message = messages.find(msg => msg.id === messageId);
    if (message && message.role === 'user') {
      sendMessage(message.content);
    }
  }, [messages, sendMessage]);

  return {
    // State
    messages,
    currentModel,
    availableModels,
    isLoading,
    error,
    wsStatus,
    isConnected,
    
    // Actions
    sendMessage,
    cancelCurrentStream,
    clearMessages,
    deleteMessage,
    editMessage,
    retryMessage,
    setCurrentModel,
    loadModels,
  };
}