'use client';

import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Loader2, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';
import { v4 as uuidv4 } from 'uuid';

import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { ModelSelector } from './ModelSelector';
import { Button } from '@/components/ui/button';
import { useWebSocket, WebSocketMessage } from '@/hooks/useWebSocket';
import { useChatStore } from '@/lib/store';
import { api } from '@/lib/api';

export function ChatInterface() {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [streamingMessageId, setStreamingMessageId] = useState<string | null>(null);

  const {
    currentSession,
    messages,
    models,
    selectedModel,
    isLoading,
    error,
    setCurrentSession,
    setMessages,
    addMessage,
    updateMessage,
    setModels,
    setSelectedModel,
    setIsLoading,
    setError,
    clearMessages,
  } = useChatStore();

  const { isConnected, sendMessage: sendWebSocketMessage } = useWebSocket(
    currentSession?.session_id || null,
    {
      onMessage: (message: WebSocketMessage) => {
        if (!streamingMessageId) return;

        switch (message.type) {
          case 'token':
            updateMessage(streamingMessageId, {
              content: messages.find(m => m.id === streamingMessageId)?.content + message.content,
              isStreaming: true,
            });
            break;

          case 'complete':
            updateMessage(streamingMessageId, {
              isStreaming: false,
            });
            setStreamingMessageId(null);
            setIsLoading(false);
            break;

          case 'error':
            toast.error(message.error || 'An error occurred');
            updateMessage(streamingMessageId, {
              isStreaming: false,
            });
            setStreamingMessageId(null);
            setIsLoading(false);
            break;

          case 'function_call':
            updateMessage(streamingMessageId, {
              functionCalls: [
                ...(messages.find(m => m.id === streamingMessageId)?.functionCalls || []),
                {
                  name: message.function_name!,
                  arguments: message.function_args,
                },
              ],
            });
            break;

          case 'function_result':
            const msg = messages.find(m => m.id === streamingMessageId);
            if (msg && msg.functionCalls) {
              const lastCall = msg.functionCalls[msg.functionCalls.length - 1];
              if (lastCall) {
                lastCall.result = message.result;
                updateMessage(streamingMessageId, {
                  functionCalls: [...msg.functionCalls],
                });
              }
            }
            break;
        }
      },
      onError: () => {
        toast.error('WebSocket connection error');
        setIsLoading(false);
      },
    }
  );

  useEffect(() => {
    loadModels();
    createNewSession();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const loadModels = async () => {
    try {
      const modelList = await api.getModels();
      setModels(modelList);
    } catch (error) {
      console.error('Failed to load models:', error);
      toast.error('Failed to load models');
    }
  };

  const createNewSession = async () => {
    try {
      const session = await api.createSession();
      setCurrentSession(session);
      clearMessages();
    } catch (error) {
      console.error('Failed to create session:', error);
      toast.error('Failed to create session');
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSendMessage = async (content: string) => {
    if (!currentSession || !isConnected) {
      toast.error('Not connected to chat service');
      return;
    }

    const userMessage = {
      id: uuidv4(),
      session_id: currentSession.session_id,
      role: 'user' as const,
      content,
      created_at: new Date().toISOString(),
    };

    addMessage(userMessage);
    setIsLoading(true);

    const assistantMessageId = uuidv4();
    const assistantMessage = {
      id: assistantMessageId,
      session_id: currentSession.session_id,
      role: 'assistant' as const,
      content: '',
      created_at: new Date().toISOString(),
      model: selectedModel,
      isStreaming: true,
    };

    addMessage(assistantMessage);
    setStreamingMessageId(assistantMessageId);

    try {
      sendWebSocketMessage({
        message: content,
        model: selectedModel,
        stream: true,
      });
    } catch (error) {
      console.error('Failed to send message:', error);
      toast.error('Failed to send message');
      setIsLoading(false);
      updateMessage(assistantMessageId, {
        content: 'Failed to send message',
        isStreaming: false,
      });
    }
  };

  return (
    <div className="flex flex-col h-screen bg-background">
      <header className="border-b px-4 py-3 flex items-center justify-between">
        <h1 className="text-xl font-semibold">AI Chat</h1>
        <div className="flex items-center gap-3">
          <ModelSelector
            models={models}
            selectedModel={selectedModel}
            onSelectModel={setSelectedModel}
          />
          <Button variant="outline" onClick={createNewSession}>
            New Chat
          </Button>
        </div>
      </header>

      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto">
          <AnimatePresence>
            {messages.length === 0 ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center justify-center h-full p-8 text-center"
              >
                <h2 className="text-2xl font-semibold mb-2">
                  Welcome to AI Chat
                </h2>
                <p className="text-muted-foreground mb-4">
                  Start a conversation with our AI assistant
                </p>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  {isConnected ? (
                    <>
                      <div className="w-2 h-2 bg-green-500 rounded-full" />
                      Connected
                    </>
                  ) : (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Connecting...
                    </>
                  )}
                </div>
              </motion.div>
            ) : (
              <div className="py-4 space-y-4">
                {messages.map((message) => (
                  <ChatMessage
                    key={message.id}
                    message={message}
                    isStreaming={message.isStreaming}
                  />
                ))}
              </div>
            )}
          </AnimatePresence>
          <div ref={messagesEndRef} />
        </div>
      </main>

      {error && (
        <div className="px-4 py-2 bg-destructive/10 text-destructive flex items-center gap-2">
          <AlertCircle className="w-4 h-4" />
          <span className="text-sm">{error}</span>
        </div>
      )}

      <ChatInput
        onSendMessage={handleSendMessage}
        isLoading={isLoading}
        placeholder={isConnected ? "Type a message..." : "Connecting..."}
      />
    </div>
  );
}