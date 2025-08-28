'use client';

import { motion } from 'framer-motion';
import { Copy, Check, User, Bot, Sparkles } from 'lucide-react';
import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ChatMessage as ChatMessageType } from '@/lib/store';

interface ChatMessageProps {
  message: ChatMessageType;
  isStreaming?: boolean;
}

export function ChatMessage({ message, isStreaming }: ChatMessageProps) {
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCode(id);
    setTimeout(() => setCopiedCode(null), 2000);
  };

  const isUser = message.role === 'user';

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={cn(
        'flex gap-3 p-4 rounded-lg',
        isUser ? 'bg-muted/50' : 'bg-background'
      )}
    >
      <div className="flex-shrink-0">
        {isUser ? (
          <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center">
            <User className="w-4 h-4 text-primary-foreground" />
          </div>
        ) : (
          <div className="w-8 h-8 rounded-full bg-blue-500 flex items-center justify-center">
            <Bot className="w-4 h-4 text-white" />
          </div>
        )}
      </div>

      <div className="flex-1 space-y-2 overflow-hidden">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm">
            {isUser ? 'You' : 'Assistant'}
          </span>
          {message.model && (
            <span className="text-xs text-muted-foreground">
              {message.model}
            </span>
          )}
          {isStreaming && (
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
            >
              <Sparkles className="w-3 h-3 text-blue-500" />
            </motion.div>
          )}
        </div>

        <div className="prose prose-sm dark:prose-invert max-w-none">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              code({ inline, className, children, ...props }: any) {
                const match = /language-(\w+)/.exec(className || '');
                const codeId = `code-${Math.random().toString(36).substr(2, 9)}`;

                return !inline && match ? (
                  <div className="relative group">
                    <div className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => copyToClipboard(String(children).replace(/\n$/, ''), codeId)}
                        className="h-8 px-2"
                      >
                        {copiedCode === codeId ? (
                          <Check className="w-4 h-4" />
                        ) : (
                          <Copy className="w-4 h-4" />
                        )}
                      </Button>
                    </div>
                    <SyntaxHighlighter
                      style={vscDarkPlus}
                      language={match[1]}
                      PreTag="div"
                      className="!mt-0"
                      {...props}
                    >
                      {String(children).replace(/\n$/, '')}
                    </SyntaxHighlighter>
                  </div>
                ) : (
                  <code className={className} {...props}>
                    {children}
                  </code>
                );
              },
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>

        {message.functionCalls && message.functionCalls.length > 0 && (
          <div className="mt-3 space-y-2">
            {message.functionCalls.map((call, index) => (
              <FunctionCallCard key={index} functionCall={call} />
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}

function FunctionCallCard({ functionCall }: { functionCall: any }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.2 }}
      className="border rounded-lg p-3 bg-blue-50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-800"
    >
      <div className="flex items-center gap-2 mb-2">
        <Sparkles className="w-4 h-4 text-blue-500" />
        <span className="font-medium text-sm">Function Call: {functionCall.name}</span>
      </div>
      {functionCall.arguments && (
        <pre className="text-xs bg-background/50 p-2 rounded overflow-x-auto">
          {JSON.stringify(functionCall.arguments, null, 2)}
        </pre>
      )}
      {functionCall.result && (
        <div className="mt-2">
          <span className="text-xs text-muted-foreground">Result:</span>
          <pre className="text-xs bg-background/50 p-2 rounded mt-1 overflow-x-auto">
            {JSON.stringify(functionCall.result, null, 2)}
          </pre>
        </div>
      )}
    </motion.div>
  );
}