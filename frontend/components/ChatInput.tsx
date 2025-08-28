'use client';

import { useState, useRef, useEffect, KeyboardEvent } from 'react';
import { Send, Mic, MicOff, Paperclip } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

interface ChatInputProps {
  onSendMessage: (message: string) => void;
  isLoading: boolean;
  placeholder?: string;
  onVoiceInput?: (transcript: string) => void;
}

export function ChatInput({
  onSendMessage,
  isLoading,
  placeholder = 'Type a message...',
  onVoiceInput,
}: ChatInputProps) {
  const [message, setMessage] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        200
      )}px`;
    }
  }, [message]);

  const handleSend = () => {
    if (message.trim() && !isLoading) {
      onSendMessage(message.trim());
      setMessage('');
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const toggleVoiceRecording = () => {
    if (!('webkitSpeechRecognition' in window)) {
      alert('Speech recognition is not supported in your browser.');
      return;
    }

    if (isRecording) {
      recognitionRef.current?.stop();
      setIsRecording(false);
    } else {
      const recognition = new (window as any).webkitSpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onresult = (event: any) => {
        const transcript = Array.from(event.results)
          .map((result: any) => result[0])
          .map((result) => result.transcript)
          .join('');

        setMessage(transcript);
        onVoiceInput?.(transcript);
      };

      recognition.onerror = (event: any) => {
        console.error('Speech recognition error:', event.error);
        setIsRecording(false);
      };

      recognition.onend = () => {
        setIsRecording(false);
      };

      recognitionRef.current = recognition;
      recognition.start();
      setIsRecording(true);
    }
  };

  return (
    <div className="relative flex items-end gap-2 p-4 border-t bg-background">
      <div className="flex-1 relative">
        <textarea
          ref={textareaRef}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={isLoading}
          className={cn(
            'w-full resize-none rounded-lg border bg-muted/50 px-4 py-3 pr-12',
            'focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent',
            'placeholder:text-muted-foreground',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'min-h-[52px] max-h-[200px]'
          )}
          rows={1}
        />
        
        <AnimatePresence>
          {isRecording && (
            <motion.div
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              className="absolute top-2 right-2"
            >
              <div className="flex items-center gap-1">
                <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                <span className="text-xs text-red-500">Recording</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="flex gap-2">
        <Button
          size="icon"
          variant="ghost"
          onClick={toggleVoiceRecording}
          disabled={isLoading}
          className={cn(
            'h-10 w-10',
            isRecording && 'text-red-500 hover:text-red-600'
          )}
        >
          {isRecording ? (
            <MicOff className="h-5 w-5" />
          ) : (
            <Mic className="h-5 w-5" />
          )}
        </Button>

        <Button
          size="icon"
          onClick={handleSend}
          disabled={!message.trim() || isLoading}
          className="h-10 w-10"
        >
          <Send className="h-5 w-5" />
        </Button>
      </div>
    </div>
  );
}