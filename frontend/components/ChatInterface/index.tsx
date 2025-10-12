'use client';

import React, { useEffect, useRef, useState } from 'react';
import { API_CONFIG } from '../../lib/config';

type Role = 'user' | 'assistant' | 'system';
type Msg = { role: Role; content: string };
type Model = { id?: string; name?: string; provider?: string } | string;

function modelId(m: Model) { return typeof m === 'string' ? m : m.id ?? m.name ?? ''; }
function modelLabel(m: Model) { return typeof m === 'string' ? m : m.name ?? m.id ?? ''; }

export function ChatInterface() {
  const [models, setModels] = useState<Model[]>([]);
  const [model, setModel] = useState<string>('');
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  useEffect(() => {
    (async () => {
      try {
        setError(null);
        const res = await fetch(`${API_CONFIG.baseURL}/chat/models`, { headers: { Accept: 'application/json' } });
        if (!res.ok) throw new Error(`GET /chat/models ${res.status}`);
        const data = await res.json();
        const list: Model[] = Array.isArray(data) ? data : (data.models ?? data.data ?? []);
        setModels(list);
        if (!model && list.length) setModel(modelId(list[0]));
      } catch {
        setError('Failed to load models');
      }
    })();
  }, []);

  async function send() {
    const content = input.trim();
    if (!content) return;

    const draft = [...messages, { role: 'user', content } as Msg];
    setMessages(draft);
    setInput('');
    setPending(true);
    setError(null);

    try {
      const res = await fetch(`${API_CONFIG.baseURL}/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: model || (models[0] ? modelId(models[0]) : ''), messages: draft, stream: false }),
      });
      if (!res.ok) throw new Error(`POST /chat/completions ${res.status}`);
      const data = await res.json();
      const assistant =
        data?.message?.content ??
        data?.choices?.[0]?.message?.content ??
        data?.content ?? '';
      setMessages([...draft, { role: 'assistant', content: String(assistant || '') }]);
    } catch {
      setError('Request failed');
      setMessages([...draft, { role: 'assistant', content: 'Request failed. Check API URL and keys.' }]);
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="flex h-screen w-full items-center justify-center bg-gradient-to-br from-gray-900 via-gray-800 to-gray-900">
      {/* Main Container - Compact for Screenshots */}
      <div className="flex h-[85vh] w-full max-w-5xl flex-col rounded-2xl border border-border bg-background/95 shadow-2xl backdrop-blur">

        {/* Compact Header with Model Selector and Feature Pills */}
        <header className="flex items-center justify-between gap-3 border-b border-border bg-card/50 px-4 py-3 backdrop-blur">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2">
              <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
                <svg className="h-5 w-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
              </div>
              <h1 className="text-lg font-semibold text-foreground">AI Chat System</h1>
            </div>

            {/* Feature Pills */}
            <div className="hidden md:flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-500/30 bg-blue-500/10 px-2.5 py-1 text-xs font-medium text-blue-400">
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                Streaming
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-purple-500/30 bg-purple-500/10 px-2.5 py-1 text-xs font-medium text-purple-400">
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                </svg>
                Cache
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-green-500/30 bg-green-500/10 px-2.5 py-1 text-xs font-medium text-green-400">
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
                Multi-Model
              </span>
            </div>
          </div>

          {/* Model Selector */}
          <div className="flex items-center gap-2">
            <label className="text-xs font-medium text-muted-foreground">Model:</label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="rounded-lg border border-input bg-background px-3 py-1.5 text-sm text-foreground shadow-sm outline-none focus:ring-2 focus:ring-ring"
            >
              {models.map((m) => (
                <option key={modelId(m)} value={modelId(m)}>
                  {modelLabel(m)}
                </option>
              ))}
            </select>
          </div>
        </header>

        {/* Messages Area - Constrained Height */}
        <main className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-[300px] max-h-[50vh] relative">
          {/* Subtle Background Pattern */}
          <div className="absolute inset-0 opacity-30 pointer-events-none"
            style={{
              backgroundImage: 'radial-gradient(circle at 20% 80%, rgba(59, 130, 246, 0.1) 0%, transparent 50%), radial-gradient(circle at 80% 20%, rgba(168, 85, 247, 0.1) 0%, transparent 50%)'
            }}
          />

          {error && (
            <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
              {error}
            </div>
          )}

          {!messages.length && (
            <div className="flex h-full items-center justify-center relative">
              <div className="max-w-md text-center space-y-4">
                <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500/20 to-purple-600/20 border border-blue-500/30">
                  <svg className="h-8 w-8 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                  </svg>
                </div>
                <div>
                  <h2 className="text-lg font-semibold text-foreground mb-2">Start a conversation</h2>
                  <p className="text-sm text-muted-foreground">
                    Choose a model and ask anything. Features streaming responses, semantic caching, and automatic failover.
                  </p>
                </div>
              </div>
            </div>
          )}

          {messages.map((m, idx) => (
            <div key={idx} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'} animate-slide-in`}>
              <div className={`group relative max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${m.role === 'user'
                ? 'bg-gradient-to-br from-blue-600 to-blue-700 text-white shadow-lg shadow-blue-900/50'
                : 'bg-card border border-border shadow-lg'
                }`}>
                {m.role === 'assistant' && (
                  <div className="absolute -left-3 top-3 h-6 w-6 rounded-full bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center text-white text-xs font-bold shadow-lg">
                    AI
                  </div>
                )}
                <div className="relative z-10">{m.content}</div>
              </div>
            </div>
          ))}

          <div ref={endRef} />
        </main>

        {/* Compact Input Area */}
        <footer className="border-t border-border bg-card/50 px-4 py-3 backdrop-blur">
          <div className="flex gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              rows={1}
              placeholder="Type your message... (Enter to send, Shift+Enter for new line)"
              disabled={pending}
              className="flex-1 resize-none rounded-lg border border-input bg-background px-3 py-2.5 text-sm shadow-sm outline-none placeholder:text-muted-foreground focus:ring-2 focus:ring-ring disabled:opacity-50 min-h-[44px] max-h-[120px]"
            />
            <button
              onClick={send}
              disabled={pending || !input.trim()}
              className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-blue-600 to-blue-700 px-5 text-sm font-medium text-white shadow-lg shadow-blue-900/50 transition-all hover:from-blue-700 hover:to-blue-800 disabled:opacity-50 disabled:cursor-not-allowed active:scale-95"
            >
              {pending ? (
                <>
                  <svg className="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Sending
                </>
              ) : (
                <>
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                  Send
                </>
              )}
            </button>
          </div>

          {/* Status Bar */}
          <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-green-500 animate-pulse" />
                Connected
              </span>
              <span>{messages.length} messages</span>
            </div>
            <span className="opacity-70">© AI Chat System</span>
          </div>
        </footer>
      </div>
    </div>
  );
}
