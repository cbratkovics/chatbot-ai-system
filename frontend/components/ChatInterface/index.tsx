'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { EvidenceRail } from '@/components/evidence/EvidenceRail';
import { GuidedDemo, type RunFn } from '@/components/evidence/GuidedDemo';
import { TelemetryChip } from '@/components/evidence/TelemetryChip';
import type { ChatHealth, ChatMsg, Highlight, HighlightKey, Telemetry } from '@/components/evidence/types';
import { useMediaQuery } from '@/components/evidence/useMediaQuery';
import { useSessionStats } from '@/components/evidence/useSessionStats';
import { API_CONFIG } from '@/lib/config';
import { asEnvelope, describeErrorBody, describeHttpError, describeNetworkError, sanitize } from '@/lib/errors';
import { fetchWithTimeout, readSse } from '@/lib/sse';
import { cn } from '@/lib/utils';

type Model = { id?: string; name?: string; provider?: string } | string;
type BackendState = 'checking' | 'waking' | 'ready' | 'down';

function modelId(m: Model) {
  return typeof m === 'string' ? m : m.id ?? m.name ?? '';
}
function modelLabel(m: Model) {
  if (typeof m === 'string') return m;
  const id = m.id ?? m.name ?? '';
  return m.provider ? `${id} (${m.provider})` : id;
}

/** First call to a sleeping Render free-tier instance can take 30-60 s; later calls are fast. */
const FIRST_CALL_TIMEOUT_MS = 60_000;
const WARM_CALL_TIMEOUT_MS = API_CONFIG.timeout ?? 30_000;
const WAKING_HINT_AFTER_MS = 3_000;
const SIMULATE_HEADER = 'X-Demo-Simulate-Failure';
const HIGHLIGHT_MS = 3_000;
const RAIL_PREF_KEY = 'evidence-rail-open';

let idCounter = 0;
const newId = () => `m${Date.now().toString(36)}-${(idCounter += 1)}`;

function isRecord(x: unknown): x is Record<string, unknown> {
  return typeof x === 'object' && x !== null;
}

/** Non-stream JSON body: OpenAI-shaped `choices[0].message.content` plus `telemetry`. */
function readJsonAnswer(data: unknown): { answer: string; telemetry?: Telemetry } {
  if (!isRecord(data)) return { answer: '' };
  const choices = Array.isArray(data.choices) ? data.choices : [];
  const first = isRecord(choices[0]) ? choices[0] : undefined;
  const message = first && isRecord(first.message) ? first.message : undefined;
  const answer = typeof message?.content === 'string' ? message.content : '';
  const telemetry = isRecord(data.telemetry) ? (data.telemetry as Telemetry) : undefined;
  return { answer, telemetry };
}

function readModels(data: unknown): Model[] {
  if (Array.isArray(data)) return data as Model[];
  if (!isRecord(data)) return [];
  const list = data.models ?? data.data;
  return Array.isArray(list) ? (list as Model[]) : [];
}

export function ChatInterface() {
  const [models, setModels] = useState<Model[]>([]);
  const [model, setModel] = useState<string>('');
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  /** Turns cleared with "New chat": no longer sent as context, still counted in the Evidence rail. */
  const [archived, setArchived] = useState<ChatMsg[]>([]);
  /** Send previous turns as context. Off (the default for this gateway demo) means every message
   *  is a standalone request, so a repeat or paraphrase can hit the cache: the cache key covers the
   *  whole prompt (ADR 0001/0007), and a question asked after other turns is a different prompt. */
  const [memory, setMemory] = useState(false);
  const [input, setInput] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backend, setBackend] = useState<BackendState>('checking');
  const [health, setHealth] = useState<ChatHealth | null>(null);
  const [simulateFailure, setSimulateFailure] = useState(false);
  const [railOpen, setRailOpen] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [demoOpen, setDemoOpen] = useState(false);
  const [highlight, setHighlight] = useState<Highlight>(null);

  const isDesktop = useMediaQuery('(min-width: 1024px)');
  const sessionMessages = useMemo(() => [...archived, ...messages], [archived, messages]);
  const stats = useSessionStats(sessionMessages);
  const endRef = useRef<HTMLDivElement>(null);

  // Refs so `send` (also driven by the guided demo across awaits) never reads stale state.
  const messagesRef = useRef(messages);
  messagesRef.current = messages;
  const modelRef = useRef(model);
  modelRef.current = model;
  const modelsRef = useRef(models);
  modelsRef.current = models;
  const simulateRef = useRef(simulateFailure);
  simulateRef.current = simulateFailure;
  const memoryRef = useRef(memory);
  memoryRef.current = memory;
  const firstCallDoneRef = useRef(false);
  const inFlightRef = useRef(false);

  const toggleAvailable = Boolean(health?.demo?.failure_toggle_enabled);
  const semanticEnabled = health ? Boolean(health.semantic_cache?.enabled) : null;

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages]);

  useEffect(() => {
    if (!highlight) return;
    const timer = setTimeout(() => setHighlight(null), HIGHLIGHT_MS);
    return () => clearTimeout(timer);
  }, [highlight]);

  useEffect(() => {
    try {
      const stored = localStorage.getItem(RAIL_PREF_KEY);
      if (stored === '0') setRailOpen(false);
    } catch {
      /* storage unavailable: keep the default */
    }
  }, []);

  const flash = useCallback((key: HighlightKey) => setHighlight({ key, nonce: Date.now() }), []);

  // Health probe with a "waking up" state and one retry, then load models.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setError(null);
      const hint = setTimeout(() => {
        if (!cancelled) setBackend('waking');
      }, WAKING_HINT_AFTER_MS);
      let healthy = false;
      for (let attempt = 0; attempt < 2 && !healthy && !cancelled; attempt += 1) {
        try {
          const res = await fetchWithTimeout(`${API_CONFIG.baseURL}/chat/health`, { headers: { Accept: 'application/json' } }, FIRST_CALL_TIMEOUT_MS);
          healthy = res.ok;
          if (res.ok) {
            const body: unknown = await res.json().catch(() => null);
            if (!cancelled && isRecord(body)) setHealth(body as ChatHealth);
          }
        } catch {
          /* retry once */
        }
      }
      clearTimeout(hint);
      if (cancelled) return;
      setBackend(healthy ? 'ready' : 'down');
      if (!healthy) {
        setError('Backend is not reachable. It may still be starting; retry in a minute.');
        return;
      }
      firstCallDoneRef.current = true;
      try {
        const res = await fetchWithTimeout(`${API_CONFIG.baseURL}/chat/models`, { headers: { Accept: 'application/json' } }, WARM_CALL_TIMEOUT_MS);
        if (!res.ok) throw new Error(await describeHttpError(res));
        const list = readModels(await res.json());
        if (cancelled) return;
        setModels(list);
        setModel((current) => current || (list.length ? modelId(list[0]) : ''));
      } catch (e) {
        if (!cancelled) setError(`Failed to load models: ${sanitize(e instanceof Error ? e.message : e)}`);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  /** Send one message. Resolves with the finished assistant message so the guided demo can read its telemetry. */
  const send: RunFn = useCallback(async (text, opts) => {
    const content = text.trim();
    if (!content || inFlightRef.current) return undefined;
    inFlightRef.current = true;

    const withContext = opts?.standalone ? false : memoryRef.current;
    const history = withContext
      ? messagesRef.current.filter((m) => !m.failed && !m.pending).map(({ role, content: c }) => ({ role, content: c }))
      : [];
    const userMsg: ChatMsg = { id: newId(), role: 'user', content, standalone: !withContext };
    let draft: ChatMsg = { id: newId(), role: 'assistant', content: '', pending: true };
    setMessages((prev) => [...prev, userMsg, draft]);
    setPending(true);
    setError(null);

    const update = (patch: (m: ChatMsg) => ChatMsg) => {
      draft = patch(draft);
      const next = draft;
      setMessages((prev) => prev.map((m) => (m.id === next.id ? next : m)));
    };

    const t0 = performance.now();
    const elapsed = () => Math.round(performance.now() - t0);
    const timeout = firstCallDoneRef.current ? WARM_CALL_TIMEOUT_MS : FIRST_CALL_TIMEOUT_MS;
    const controller = new AbortController();
    // Idle timeout: reset whenever bytes arrive, so a long answer is fine but a stall is not.
    let timer = setTimeout(() => controller.abort(), timeout);
    const touch = () => {
      clearTimeout(timer);
      timer = setTimeout(() => controller.abort(), WARM_CALL_TIMEOUT_MS);
    };

    const headers: Record<string, string> = { 'Content-Type': 'application/json', Accept: 'text/event-stream, application/json' };
    const simulate = opts?.simulate ?? simulateRef.current;
    if (simulate) headers[SIMULATE_HEADER] = '1';
    if (opts?.bypassCache) headers['Cache-Control'] = 'no-cache'; // backend reports cache BYPASS

    try {
      const fallbackModel = modelsRef.current[0] ? modelId(modelsRef.current[0]) : 'default';
      const res = await fetch(`${API_CONFIG.baseURL}/chat/completions`, {
        method: 'POST',
        headers,
        signal: controller.signal,
        body: JSON.stringify({
          model: modelRef.current || fallbackModel,
          messages: [...history, { role: 'user', content }],
          stream: true,
        }),
      });
      firstCallDoneRef.current = true;
      if (!res.ok) {
        const detail = await describeHttpError(res);
        setError(detail);
        update((m) => ({ ...m, content: `Request failed: ${detail}`, pending: false, failed: true, clientMs: elapsed() }));
        return draft;
      }

      const isSse = (res.headers.get('content-type') || '').includes('text/event-stream');
      if (!isSse || !res.body) {
        // Backend answered with plain JSON (streaming disabled server-side): same telemetry shape.
        const { answer, telemetry } = readJsonAnswer(await res.json());
        const ms = elapsed();
        update((m) => ({ ...m, content: answer, telemetry, pending: false, clientMs: ms, clientTtfbMs: ms }));
        setBackend('ready');
        return draft;
      }

      let streamError: string | null = null;
      let ttfb: number | undefined;
      await readSse(
        res.body,
        (event, data) => {
          if (event === 'delta') {
            const delta = isRecord(data) && typeof data.content === 'string' ? data.content : '';
            if (!delta) return;
            if (ttfb === undefined) ttfb = elapsed();
            update((m) => ({ ...m, content: m.content + delta }));
          } else if (event === 'done') {
            const telemetry = isRecord(data) ? (data as Telemetry) : undefined;
            update((m) => ({ ...m, telemetry, pending: false, clientMs: elapsed(), clientTtfbMs: ttfb }));
          } else if (event === 'error') {
            streamError = describeErrorBody(undefined, data);
            const err = asEnvelope(data).error;
            const partial = typeof err === 'object' && err?.partial_content ? err.partial_content : '';
            const message = streamError;
            update((m) => ({ ...m, content: partial || `Request failed: ${message}`, pending: false, failed: true, clientMs: elapsed() }));
          }
        },
        touch,
      );
      if (streamError) setError(streamError);
      setBackend('ready');
      return draft;
    } catch (e) {
      const detail = describeNetworkError(e);
      setError(detail);
      update((m) => ({ ...m, content: m.content || `Request failed: ${detail}`, pending: false, failed: true, clientMs: elapsed() }));
      return draft;
    } finally {
      clearTimeout(timer);
      setPending(false);
      inFlightRef.current = false;
      update((m) => (m.pending ? { ...m, pending: false, clientMs: m.clientMs ?? elapsed() } : m));
    }
  }, []);

  function submit() {
    const text = input;
    if (!text.trim() || pending) return;
    setInput('');
    void send(text);
  }

  function toggleEvidence() {
    if (isDesktop) {
      setRailOpen((open) => {
        try {
          localStorage.setItem(RAIL_PREF_KEY, open ? '0' : '1');
        } catch {
          /* ignore */
        }
        return !open;
      });
    } else {
      setDrawerOpen(true);
    }
  }

  function newChat() {
    if (pending) return;
    setArchived((prev) => [...prev, ...messagesRef.current]);
    setMessages([]);
    setError(null);
  }

  function openDemo() {
    setDemoOpen(true);
    setDrawerOpen(false);
  }

  const backendLabel: Record<BackendState, { text: string; dot: string }> = {
    checking: { text: 'Connecting…', dot: 'bg-yellow-500 motion-safe:animate-pulse' },
    waking: { text: 'Waking up the backend (free tier, ~30–60 s)…', dot: 'bg-yellow-500 motion-safe:animate-pulse' },
    ready: { text: 'Connected', dot: 'bg-green-500' },
    down: { text: 'Backend unreachable', dot: 'bg-red-500' },
  };

  const cachePill =
    semanticEnabled === true
      ? { text: 'Semantic Cache', title: `Exact key first, then ${health?.semantic_cache?.embedding_model ?? 'embedding'} similarity above ${health?.semantic_cache?.threshold ?? '?'} (ADR 0007)` }
      : semanticEnabled === false
        ? { text: 'Response Cache', title: 'Exact-match cache on this backend; semantic matching is off (ADR 0001)' }
        : { text: 'Cache', title: 'Waiting for /chat/health to report the cache mode' };
  const fallbackTitle = health?.fallback_chain?.length
    ? `Primary ${health.default_model ?? ''} → ${health.fallback_chain.join(' → ')} on 401/402/429/5xx/timeout (ADR 0003)`
    : 'Provider chain with failover on 401/402/429/5xx/timeout (ADR 0003)';
  const lastAssistantId = [...messages].reverse().find((m) => m.role === 'assistant')?.id;
  const evidencePressed = isDesktop ? railOpen : drawerOpen;

  return (
    <div className={cn('grid gap-4', isDesktop && railOpen && 'lg:grid-cols-[minmax(0,1fr)_340px]')}>
      <section aria-label="Chat" className="flex h-[calc(100dvh-7.5rem)] min-h-[520px] flex-col rounded-2xl border border-border bg-background/95 shadow-2xl">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-border bg-card/50 px-4 py-2.5">
          <ul className="flex flex-wrap items-center gap-2" aria-label="What this demo shows">
            <li className="inline-flex items-center gap-1.5 rounded-full border border-blue-500/30 bg-blue-500/10 px-2.5 py-1 text-xs font-medium text-blue-400" title="Server-Sent Events over one POST: meta → delta* → done | error (ADR 0005)">
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              SSE Streaming
            </li>
            <li className="inline-flex items-center gap-1.5 rounded-full border border-purple-500/30 bg-purple-500/10 px-2.5 py-1 text-xs font-medium text-purple-400" title={cachePill.title}>
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
              </svg>
              {cachePill.text}
            </li>
            <li className="inline-flex items-center gap-1.5 rounded-full border border-green-500/30 bg-green-500/10 px-2.5 py-1 text-xs font-medium text-green-400" title={fallbackTitle}>
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
              Multi-Provider Failover
            </li>
          </ul>

          <div className="flex flex-wrap items-center gap-3">
            {toggleAvailable && (
              <label className="flex cursor-pointer items-center gap-2 text-xs font-medium text-muted-foreground" title="Forces the primary provider to fail with a 503 so you can watch failover">
                <input
                  type="checkbox"
                  checked={simulateFailure}
                  onChange={(e) => setSimulateFailure(e.target.checked)}
                  className="h-3.5 w-3.5 accent-amber-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
                <span className={simulateFailure ? 'text-amber-300' : ''}>Simulate provider failure</span>
              </label>
            )}
            <label
              className="flex cursor-pointer items-center gap-2 text-xs font-medium text-muted-foreground"
              title="On: previous turns are sent as context (a follow-up can refer to them). Off: each message is a standalone request, so repeating or paraphrasing a question can hit the cache."
            >
              <input
                type="checkbox"
                checked={memory}
                onChange={(e) => setMemory(e.target.checked)}
                className="h-3.5 w-3.5 accent-blue-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
              <span>Conversation memory</span>
            </label>
            <button
              type="button"
              onClick={newChat}
              disabled={pending || messages.length === 0}
              title="Clear the conversation. Evidence keeps counting the cleared turns."
              className="rounded-lg border border-border px-2.5 py-1.5 text-xs font-medium hover:bg-accent disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              New chat
            </button>
            <label className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
              Model
              <select
                value={model}
                onChange={(e) => setModel(e.target.value)}
                className="rounded-lg border border-input bg-background px-2 py-1.5 text-sm text-foreground shadow-sm outline-none focus:ring-2 focus:ring-ring"
              >
                {models.map((m) => (
                  <option key={modelId(m)} value={modelId(m)}>
                    {modelLabel(m)}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={() => setDemoOpen((o) => !o)}
              aria-expanded={demoOpen}
              aria-controls="guided-demo"
              className="rounded-lg border border-border px-2.5 py-1.5 text-xs font-medium hover:bg-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              Demo
            </button>
            <button
              type="button"
              onClick={toggleEvidence}
              aria-pressed={evidencePressed}
              aria-controls="evidence-rail"
              className={cn(
                'rounded-lg border px-2.5 py-1.5 text-xs font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                evidencePressed ? 'border-amber-500/40 bg-amber-500/10 text-amber-300' : 'border-border hover:bg-accent',
              )}
            >
              Evidence
            </button>
          </div>
        </header>

        <div id="guided-demo">
          <GuidedDemo
            open={demoOpen}
            onClose={() => setDemoOpen(false)}
            run={send}
            busy={pending}
            backendReady={backend === 'ready'}
            toggleAvailable={toggleAvailable}
            semanticEnabled={semanticEnabled}
            onHighlight={flash}
          />
        </div>

        <div className="relative flex-1 space-y-3 overflow-y-auto px-4 py-3" role="log" aria-live="polite" aria-label="Conversation">
          <div
            className="pointer-events-none absolute inset-0 opacity-30"
            aria-hidden="true"
            style={{
              backgroundImage:
                'radial-gradient(circle at 20% 80%, rgba(59, 130, 246, 0.1) 0%, transparent 50%), radial-gradient(circle at 80% 20%, rgba(168, 85, 247, 0.1) 0%, transparent 50%)',
            }}
          />

          {error && (
            <div role="alert" className="relative rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive break-words">
              {error}
            </div>
          )}
          {backend === 'waking' && !error && (
            <div role="status" className="relative rounded-lg border border-yellow-500/40 bg-yellow-500/10 p-3 text-sm text-yellow-300">
              Waking up the backend. Free-tier instances sleep when idle; the first response can take 30–60 seconds.
            </div>
          )}

          {!messages.length && (
            <div className="relative flex h-full items-center justify-center">
              <div className="max-w-md space-y-4 text-center">
                <div className="inline-flex h-16 w-16 items-center justify-center rounded-2xl border border-blue-500/30 bg-gradient-to-br from-blue-500/20 to-purple-600/20" aria-hidden="true">
                  <svg className="h-8 w-8 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                  </svg>
                </div>
                <div>
                  <h2 className="mb-2 text-lg font-semibold text-foreground">Start a conversation</h2>
                  <p className="text-sm text-muted-foreground">
                    Every answer carries a chip with the provider, cache hit or miss, latency, tokens, cost, and any failover. Press{' '}
                    <button type="button" onClick={openDemo} className="underline underline-offset-2 hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                      Demo
                    </button>{' '}
                    for a three-step tour.
                  </p>
                </div>
              </div>
            </div>
          )}

          {messages.map((m) => (
            <div key={m.id} className={cn('relative flex', m.role === 'user' ? 'justify-end' : 'justify-start', 'motion-safe:animate-slide-in')}>
              <div
                className={cn(
                  'group relative max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed',
                  m.role === 'user' ? 'bg-gradient-to-br from-blue-600 to-blue-700 text-white shadow-lg shadow-blue-900/50' : 'border border-border bg-card shadow-lg',
                )}
              >
                {m.role === 'assistant' && (
                  <div className="absolute -left-3 top-3 flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-purple-500 to-pink-600 text-xs font-bold text-white shadow-lg" aria-hidden="true">
                    AI
                  </div>
                )}
                {m.role === 'user' && m.standalone && (
                  <span className="mb-1 block text-[10px] uppercase tracking-wide text-blue-200/80" title="Sent without conversation history">
                    standalone
                  </span>
                )}
                <div className="relative z-10 whitespace-pre-wrap">
                  {m.content}
                  {m.pending && <span className="ml-0.5 inline-block h-4 w-1.5 bg-blue-400 align-middle motion-safe:animate-pulse" role="status" aria-label="Streaming" />}
                </div>
                {m.role === 'assistant' && m.telemetry && <TelemetryChip t={m.telemetry} highlight={m.id === lastAssistantId ? highlight?.key ?? null : null} />}
              </div>
            </div>
          ))}
          <div ref={endRef} />
        </div>

        <footer className="border-t border-border bg-card/50 px-4 py-3">
          <div className="flex gap-2">
            <label htmlFor="chat-input" className="sr-only">
              Message
            </label>
            <textarea
              id="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  submit();
                }
              }}
              rows={1}
              placeholder="Type your message… (Enter to send, Shift+Enter for a new line)"
              disabled={pending}
              className="max-h-[120px] min-h-[44px] flex-1 resize-none rounded-lg border border-input bg-background px-3 py-2.5 text-sm shadow-sm outline-none placeholder:text-muted-foreground focus:ring-2 focus:ring-ring disabled:opacity-50"
            />
            <button
              type="button"
              onClick={submit}
              disabled={pending || !input.trim()}
              className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-blue-600 to-blue-700 px-5 text-sm font-medium text-white shadow-lg shadow-blue-900/50 transition-all hover:from-blue-700 hover:to-blue-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 motion-safe:active:scale-95"
            >
              {pending ? (
                <>
                  <svg className="h-4 w-4 motion-safe:animate-spin" fill="none" viewBox="0 0 24 24" aria-hidden="true">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Sending
                </>
              ) : (
                <>
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                  </svg>
                  Send
                </>
              )}
            </button>
          </div>
          <div className="mt-2 flex items-center justify-between text-xs text-muted-foreground">
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-1.5" role="status">
                <span className={cn('h-2 w-2 rounded-full', backendLabel[backend].dot)} aria-hidden="true" />
                {backendLabel[backend].text}
              </span>
              <span>
                {messages.length} messages{archived.length ? ` (+${archived.length} cleared)` : ''}
              </span>
              {health?.cache && <span title="Cache backend reported by /chat/health">cache: {health.cache}</span>}
            </div>
            <span className="opacity-70">© AI Chat System</span>
          </div>
        </footer>
      </section>

      {isDesktop && railOpen && (
        <aside id="evidence-rail" aria-label="Evidence" className="sticky top-4 max-h-[calc(100dvh-7.5rem)] overflow-y-auto rounded-2xl border border-border bg-background/95 p-4 shadow-2xl">
          <EvidenceRail stats={stats} highlight={highlight} semanticEnabled={semanticEnabled} onStartDemo={openDemo} />
        </aside>
      )}

      <Dialog open={!isDesktop && drawerOpen} onOpenChange={setDrawerOpen}>
        <DialogContent className="inset-y-0 right-0 w-full max-w-sm overflow-y-auto rounded-l-2xl">
          <DialogTitle className="sr-only">Evidence</DialogTitle>
          <DialogDescription className="sr-only">Statistics derived from this session&apos;s telemetry.</DialogDescription>
          <EvidenceRail stats={stats} highlight={highlight} semanticEnabled={semanticEnabled} onStartDemo={openDemo} />
        </DialogContent>
      </Dialog>
    </div>
  );
}
