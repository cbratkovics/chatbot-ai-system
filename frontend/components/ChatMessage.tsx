"use client";

import React, { memo } from 'react';
import { Message } from '@/types';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface ChatMessageProps {
  message: Message;
  onEdit?: (messageId: string, newContent: string) => void;
  onDelete?: (messageId: string) => void;
  onRetry?: (messageId: string) => void;
  onCopy?: (content: string) => void;
}

export const ChatMessage = memo(function ChatMessage({
  message,
  onEdit,
  onDelete,
  onRetry,
  onCopy,
}: ChatMessageProps) {
  const [isEditing, setIsEditing] = React.useState(false);
  const [editContent, setEditContent] = React.useState(message.content);

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    onCopy?.(message.content);
  };

  const handleEdit = () => {
    if (isEditing && editContent !== message.content) {
      onEdit?.(message.id, editContent);
    }
    setIsEditing(!isEditing);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && e.ctrlKey) {
      handleEdit();
    }
  };

  const displayContent = message.isStreaming ? message.streamingContent : message.content;
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={`flex gap-3 max-w-[85%] ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
        <div className="flex-shrink-0 pt-1">
          <div
            className={`w-8 h-8 rounded-full flex items-center justify-center font-semibold text-sm ${
              isUser
                ? 'bg-gradient-to-br from-blue-500 to-blue-600 text-white shadow-lg'
                : 'bg-gradient-to-br from-purple-500 to-pink-500 text-white shadow-lg'
            }`}
          >
            {isUser ? 'U' : 'AI'}
          </div>
        </div>

        <div className="flex-1 min-w-0">
          <div className={`flex items-center gap-2 mb-1.5 ${isUser ? 'justify-end' : 'justify-start'}`}>
            <span className="text-xs font-medium text-gray-400">
              {isUser ? 'You' : 'Assistant'}
            </span>
            {message.model && (
              <span className="text-xs text-gray-500 bg-white/5 px-2 py-0.5 rounded-full">
                {message.model}
              </span>
            )}
            {message.cached && (
              <span className="text-xs bg-yellow-500/20 text-yellow-300 px-2 py-0.5 rounded-full border border-yellow-500/30">
                Cached
              </span>
            )}
            {message.isStreaming && (
              <span className="text-xs bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded-full border border-blue-500/30 animate-pulse">
                Typing...
              </span>
            )}
            {message.status === 'error' && (
              <span className="text-xs bg-red-500/20 text-red-300 px-2 py-0.5 rounded-full border border-red-500/30">
                Error
              </span>
            )}
          </div>

          {isEditing ? (
            <div className="space-y-2">
              <textarea
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                onKeyDown={handleKeyDown}
                className="w-full p-3 glass-panel rounded-xl text-gray-100 resize-none focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                rows={4}
                autoFocus
              />
              <div className="flex gap-2">
                <button
                  onClick={handleEdit}
                  className="px-4 py-1.5 bg-blue-500 hover:bg-blue-600 text-white text-sm rounded-lg transition-colors"
                >
                  Save
                </button>
                <button
                  onClick={() => {
                    setIsEditing(false);
                    setEditContent(message.content);
                  }}
                  className="px-4 py-1.5 bg-white/10 hover:bg-white/20 text-gray-300 text-sm rounded-lg transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className={isUser ? 'user-message' : 'assistant-message'}>
                {message.status === 'error' && message.error ? (
                  <div className="flex items-start gap-2 text-red-300">
                    <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span>{message.error}</span>
                  </div>
                ) : (
                  <div className={`prose ${isUser ? 'prose-invert' : 'prose-invert'} max-w-none prose-sm`}>
                    <ReactMarkdown
                      components={{
                        code({ inline, className, children, ...props }: {
                          inline?: boolean;
                          className?: string;
                          children?: React.ReactNode;
                          node?: any;
                          [key: string]: any;
                        }) {
                          const match = /language-(\w+)/.exec(className || '');
                          return !inline && match ? (
                            <SyntaxHighlighter
                              style={vscDarkPlus}
                              language={match[1]}
                              PreTag="div"
                              customStyle={{
                                borderRadius: '0.5rem',
                                fontSize: '0.875rem',
                                margin: '0.5rem 0',
                              }}
                              {...props}
                            >
                              {String(children).replace(/\n$/, '')}
                            </SyntaxHighlighter>
                          ) : (
                            <code className={`${className} bg-white/10 px-1.5 py-0.5 rounded text-blue-300`} {...props}>
                              {children}
                            </code>
                          );
                        },
                      }}
                    >
                      {displayContent || ''}
                    </ReactMarkdown>
                  </div>
                )}
              </div>

              <div className={`flex items-center gap-1 mt-2 ${isUser ? 'justify-end' : 'justify-start'}`}>
                {isUser && onEdit && (
                  <button
                    onClick={handleEdit}
                    className="p-1.5 hover:bg-white/10 rounded-lg transition-colors text-gray-400 hover:text-gray-200"
                    title="Edit message"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                    </svg>
                  </button>
                )}

                <button
                  onClick={handleCopy}
                  className="p-1.5 hover:bg-white/10 rounded-lg transition-colors text-gray-400 hover:text-gray-200"
                  title="Copy message"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                </button>

                {message.status === 'error' && onRetry && (
                  <button
                    onClick={() => onRetry(message.id)}
                    className="p-1.5 hover:bg-white/10 rounded-lg transition-colors text-gray-400 hover:text-gray-200"
                    title="Retry message"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                  </button>
                )}

                {onDelete && (
                  <button
                    onClick={() => onDelete(message.id)}
                    className="p-1.5 hover:bg-red-500/20 rounded-lg transition-colors text-gray-400 hover:text-red-400"
                    title="Delete message"
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                )}

                {message.tokens && (
                  <span className="text-xs text-gray-500 ml-2">
                    {message.tokens} tokens
                  </span>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
});
