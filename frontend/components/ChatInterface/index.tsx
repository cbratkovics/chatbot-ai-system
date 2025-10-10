'use client';

import React, { useEffect, useRef, useState } from 'react';
import { API_CONFIG } from '@/lib/config';

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
    <div className="flex h-dvh w-full items-stretch bg-background text-foreground">
      <div className="mx-auto flex w-full max-w-5xl flex-col">
        <header className="sticky top-0 z-10 border-b border-border bg-background/80 backdrop-blur">
          <div className="flex items-center justify-between px-4 py-3">
            <div className="text-sm font-medium">AI Chat System</div>
            <div className="flex items-center gap-3">
              <select
                className="rounded-md border border-input bg-transparent px-2 py-1 text-sm outline-none"
                value={model}
                onChange={(e) => setModel(e.target.value)}
              >
                {models.map((m, i) => (
                  <option key={i} value={modelId(m)}>{modelLabel(m)}</option>
                ))}
              </select>
              <div className="text-xs text-muted-foreground">
                {API_CONFIG.baseURL.replace(/^https?:\/\//,'')}
              </div>
            </div>
          </div>
          {error && <div className="bg-destructive/10 px-4 py-2 text-sm text-destructive">{error}</div>}
        </header>

        <main className="flex-1 space-y-4 overflow-y-auto px-4 py-6">
          {messages.length === 0 && (
            <div className="mx-auto max-w-2xl rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
              Start a conversation. Choose a model and ask anything.
            </div>
          )}
          {messages.map((m, idx) => (
            <div key={idx} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[85%] rounded-2xl px-4 py-2 text-sm leading-relaxed ${m.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-muted'}`}>
                {m.content}
              </div>
            </div>
          ))}
          <div ref={endRef} />
        </main>

        <footer className="border-t border-border bg-background p-4">
          <div className="mx-auto flex max-w-3xl gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
              rows={1}
              placeholder="Type your message..."
              className="min-h-12 flex-1 resize-none rounded-lg border border-input bg-background px-3 py-2 text-sm shadow-sm outline-none placeholder:text-muted-foreground focus:ring-2 focus:ring-ring"
            />
            <button
              onClick={send}
              disabled={pending}
              className="inline-flex h-10 shrink-0 items-center justify-center rounded-lg bg-primary px-4 text-sm font-medium text-primary-foreground shadow transition-opacity disabled:opacity-50"
            >
              Send
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
