'use client';

import React, { useEffect, useRef, useState } from 'react';
import { API_CONFIG } from '../../lib/config';

type Role = 'user' | 'assistant' | 'system';

/** What answered, from where, at what cost. Mirrors the backend `telemetry` object. */
type Attempt = { provider: string; model: string; outcome: 'ok' | 'failed' | 'skipped'; status_code?: number | null; error_code?: string | null; latency_ms?: number };
type Telemetry = {
  request_id?: string;
  provider?: string;
  model?: string;
  cache?: { status?: 'hit' | 'miss' | 'bypass'; backend?: string; similarity?: number | null };
  latency_ms?: number;
  ttfb_ms?: number | null;
  usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number; source?: string };
  cost_usd?: number | null;
  attempts?: Attempt[];
  failover?: boolean;
  simulated_failure?: boolean;
  streamed?: boolean;
};
type Msg = { role: Role; content: string; telemetry?: Telemetry; pending?: boolean; failed?: boolean };
type Model = { id?: string; name?: string; provider?: string } | string;
type BackendState = 'checking' | 'waking' | 'ready' | 'down';

function modelId(m: Model) { return typeof m === 'string' ? m : m.id ?? m.name ?? ''; }
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

async function fetchWithTimeout(url: string, init: RequestInit, timeoutMs: number) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

/** Keep printable ASCII only and cap length: the banner shows backend text verbatim otherwise. */
function sanitize(text: unknown, max = 300) {
  return String(text ?? '').replace(/[^\x20-\x7E]/g, '').slice(0, max);
}

/** Turn an error envelope `{error:{code,message,provider,request_id}}` into one readable line. */
function describeErrorBody(status: number | undefined, body: any) {
  const err = body?.error;
  const code = typeof err === 'object' ? err?.code : undefined;
  const message = typeof err === 'object' ? err?.message : (err ?? body?.detail ?? 'Unknown error');
  const provider = typeof err === 'object' && err?.provider ? ` [${sanitize(err.provider, 20)}]` : '';
  const reqId = body?.request_id ? ` · request ${sanitize(body.request_id, 36)}` : '';
  const statusPart = status ?? (typeof err === 'object' ? err?.status_code : undefined);
  return `${statusPart ?? ''}${code ? ` ${sanitize(code, 40)}` : ''}${provider}: ${sanitize(message)}${reqId}`.trim();
}

async function describeHttpError(res: Response) {
  let body: any = null;
  try { body = await res.json(); } catch { /* not JSON */ }
  return describeErrorBody(res.status, body ?? { error: res.statusText });
}

function describeNetworkError(e: unknown) {
  if (e instanceof DOMException && e.name === 'AbortError') {
    return 'Timed out waiting for the backend. Free-tier instances sleep when idle; try again in a moment.';
  }
  return `Network error: ${sanitize((e as Error)?.message ?? e)}`;
}

/** Parse a Server-Sent Events body incrementally; calls onEvent for each complete event. */
async function readSse(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: string, data: any) => void,
  onChunk?: () => void,
) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    onChunk?.();
    buffer += decoder.decode(value, { stream: true });
    let sep = buffer.indexOf('\n\n');
    while (sep !== -1) {
      const block = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      let event = 'message';
      let data = '';
      for (const line of block.split('\n')) {
        if (line.startsWith('event:')) event = line.slice(6).trim();
        else if (line.startsWith('data:')) data += line.slice(5).trim();
      }
      if (data) {
        try { onEvent(event, JSON.parse(data)); } catch { onEvent(event, data); }
      }
      sep = buffer.indexOf('\n\n');
    }
  }
}

function fmtCost(usd: number | null | undefined) {
  if (usd === null || usd === undefined) return 'cost n/a';
  if (usd === 0) return '$0.00';
  return usd < 0.0001 ? `$${usd.toExponential(1)}` : `$${usd.toFixed(5)}`;
}

/** The per-message evidence: provider, model, cache, latency, tokens, cost, failover. */
function TelemetryChip({ t }: { t: Telemetry }) {
  const hit = t.cache?.status === 'hit';
  const pill = 'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] leading-4 whitespace-nowrap';
  const neutral = `${pill} border-border bg-background/60 text-muted-foreground`;
  const failed = (t.attempts ?? []).filter((a) => a.outcome === 'failed');
  const usage = t.usage ?? {};
  const est = usage.source === 'estimated' ? '~' : '';
  return (
    <div className="mt-2 flex flex-wrap gap-1.5" aria-label="response telemetry">
      <span className={`${pill} border-blue-500/40 bg-blue-500/10 text-blue-300`} title="Provider slot and model that answered">
        {t.provider ?? '?'} · {t.model ?? '?'}
      </span>
      <span
        className={`${pill} ${hit ? 'border-green-500/40 bg-green-500/10 text-green-300' : 'border-purple-500/40 bg-purple-500/10 text-purple-300'}`}
        title={`Cache ${hit ? 'hit' : 'miss'} · backend: ${t.cache?.backend ?? '?'}${hit && t.cache?.similarity != null ? ` · similarity ${t.cache.similarity.toFixed(2)}` : ''}`}
      >
        cache {hit ? 'HIT' : (t.cache?.status ?? 'miss').toUpperCase()}
        {hit && t.cache?.similarity != null ? ` (${t.cache.similarity.toFixed(2)})` : ''}
      </span>
      <span className={neutral} title={t.ttfb_ms != null ? `time to first token ${Math.round(t.ttfb_ms)} ms` : 'server-side latency'}>
        {Math.round(t.latency_ms ?? 0)} ms{t.ttfb_ms != null ? ` · ttfb ${Math.round(t.ttfb_ms)}` : ''}
      </span>
      <span className={neutral} title={usage.source === 'estimated' ? 'token counts estimated locally (provider did not report usage)' : 'token counts reported by the provider'}>
        {est}{usage.prompt_tokens ?? 0} in / {est}{usage.completion_tokens ?? 0} out
      </span>
      <span className={neutral} title="estimated from list prices; $0.00 on a cache hit">{fmtCost(t.cost_usd)}</span>
      {t.streamed && <span className={neutral}>streamed</span>}
      {t.failover && (
        <span className={`${pill} border-amber-500/50 bg-amber-500/10 text-amber-300`} title={failed.map((a) => `${a.provider}/${a.model}: ${a.status_code ?? ''} ${a.error_code ?? ''}`).join('\n')}>
          failover: {failed.map((a) => a.provider).join(', ')} → {t.provider}{t.simulated_failure ? ' (simulated)' : ''}
        </span>
      )}
    </div>
  );
}

export function ChatInterface() {
  const [models, setModels] = useState<Model[]>([]);
  const [model, setModel] = useState<string>('');
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backend, setBackend] = useState<BackendState>('checking');
  const [firstCallDone, setFirstCallDone] = useState(false);
  const [toggleAvailable, setToggleAvailable] = useState(false);
  const [simulateFailure, setSimulateFailure] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  // Health probe with a "waking up" state and one retry, then load models.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setError(null);
      const hint = setTimeout(() => { if (!cancelled) setBackend('waking'); }, WAKING_HINT_AFTER_MS);
      let healthy = false;
      for (let attempt = 0; attempt < 2 && !healthy && !cancelled; attempt++) {
        try {
          const res = await fetchWithTimeout(`${API_CONFIG.baseURL}/chat/health`, { headers: { Accept: 'application/json' } }, FIRST_CALL_TIMEOUT_MS);
          healthy = res.ok;
          if (res.ok) {
            const health = await res.json().catch(() => null);
            if (!cancelled) setToggleAvailable(Boolean(health?.demo?.failure_toggle_enabled));
          }
        } catch { /* retry once */ }
      }
      clearTimeout(hint);
      if (cancelled) return;
      setBackend(healthy ? 'ready' : 'down');
      if (healthy) setFirstCallDone(true);
      if (!healthy) { setError('Backend is not reachable. It may still be starting; retry in a minute.'); return; }
      try {
        const res = await fetchWithTimeout(`${API_CONFIG.baseURL}/chat/models`, { headers: { Accept: 'application/json' } }, WARM_CALL_TIMEOUT_MS);
        if (!res.ok) throw new Error(await describeHttpError(res));
        const data = await res.json();
        const list: Model[] = Array.isArray(data) ? data : (data.models ?? data.data ?? []);
        if (cancelled) return;
        setModels(list);
        setModel((current) => current || (list.length ? modelId(list[0]) : ''));
      } catch (e) {
        if (!cancelled) setError(`Failed to load models: ${sanitize((e as Error)?.message)}`);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  function patchLast(update: (m: Msg) => Msg) {
    setMessages((prev) => prev.length ? [...prev.slice(0, -1), update(prev[prev.length - 1])] : prev);
  }

  async function send() {
    const content = input.trim();
    if (!content) return;

    const history = messages.filter((m) => !m.failed).map(({ role, content }) => ({ role, content }));
    const draft: Msg[] = [...messages, { role: 'user', content }];
    setMessages([...draft, { role: 'assistant', content: '', pending: true }]);
    setInput('');
    setPending(true);
    setError(null);

    const timeout = firstCallDone ? WARM_CALL_TIMEOUT_MS : FIRST_CALL_TIMEOUT_MS;
    const controller = new AbortController();
    // Idle timeout: reset whenever bytes arrive, so a long answer is fine but a stall is not.
    let timer = setTimeout(() => controller.abort(), timeout);
    const touch = () => { clearTimeout(timer); timer = setTimeout(() => controller.abort(), WARM_CALL_TIMEOUT_MS); };

    const headers: Record<string, string> = { 'Content-Type': 'application/json', Accept: 'text/event-stream, application/json' };
    if (toggleAvailable && simulateFailure) headers[SIMULATE_HEADER] = '1';

    try {
      const res = await fetch(`${API_CONFIG.baseURL}/chat/completions`, {
        method: 'POST',
        headers,
        signal: controller.signal,
        body: JSON.stringify({
          model: model || (models[0] ? modelId(models[0]) : 'default'),
          messages: [...history, { role: 'user', content }],
          stream: true,
        }),
      });
      setFirstCallDone(true);
      if (!res.ok) {
        const detail = await describeHttpError(res);
        setError(detail);
        patchLast((m) => ({ ...m, content: `Request failed: ${detail}`, pending: false, failed: true }));
        return;
      }

      const isSse = (res.headers.get('content-type') || '').includes('text/event-stream');
      if (!isSse || !res.body) {
        // Backend answered with plain JSON (streaming disabled server-side): same telemetry shape.
        const data = await res.json();
        const answer = data?.choices?.[0]?.message?.content ?? data?.message?.content ?? data?.content ?? '';
        patchLast((m) => ({ ...m, content: String(answer || ''), telemetry: data?.telemetry, pending: false }));
        setBackend('ready');
        return;
      }

      let streamError: string | null = null;
      await readSse(res.body, (event, data) => {
        if (event === 'delta' && typeof data?.content === 'string') {
          patchLast((m) => ({ ...m, content: m.content + data.content }));
        } else if (event === 'done') {
          patchLast((m) => ({ ...m, telemetry: data, pending: false }));
        } else if (event === 'error') {
          streamError = describeErrorBody(undefined, data);
          const partial = data?.error?.partial_content;
          patchLast((m) => ({ ...m, content: partial || `Request failed: ${streamError}`, pending: false, failed: true }));
        }
      }, touch);
      if (streamError) setError(streamError);
      setBackend('ready');
    } catch (e) {
      const detail = describeNetworkError(e);
      setError(detail);
      patchLast((m) => ({ ...m, content: m.content || `Request failed: ${detail}`, pending: false, failed: true }));
    } finally {
      clearTimeout(timer);
      setPending(false);
      patchLast((m) => (m.pending ? { ...m, pending: false } : m));
    }
  }

  const backendLabel: Record<BackendState, { text: string; dot: string }> = {
    checking: { text: 'Connecting…', dot: 'bg-yellow-500 animate-pulse' },
    waking: { text: 'Waking up the backend (free tier, ~30–60 s)…', dot: 'bg-yellow-500 animate-pulse' },
    ready: { text: 'Connected', dot: 'bg-green-500' },
    down: { text: 'Backend unreachable', dot: 'bg-red-500' },
  };

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

          {/* Demo failure toggle (only when the backend enables it) + Model Selector */}
          <div className="flex items-center gap-3">
            {toggleAvailable && (
              <label className="flex cursor-pointer items-center gap-2 text-xs font-medium text-muted-foreground" title="Forces the primary provider to fail with a 503 so you can watch failover">
                <input
                  type="checkbox"
                  checked={simulateFailure}
                  onChange={(e) => setSimulateFailure(e.target.checked)}
                  className="h-3.5 w-3.5 accent-amber-500"
                />
                <span className={simulateFailure ? 'text-amber-300' : ''}>Simulate provider failure</span>
              </label>
            )}
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
            <div role="alert" className="rounded-lg border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive break-words">
              {error}
            </div>
          )}
          {backend === 'waking' && !error && (
            <div role="status" className="rounded-lg border border-yellow-500/40 bg-yellow-500/10 p-3 text-sm text-yellow-300">
              Waking up the backend. Free-tier instances sleep when idle; the first response can take 30–60 seconds.
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
                <div className="relative z-10 whitespace-pre-wrap">
                  {m.content}
                  {m.pending && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-blue-400 align-middle" aria-label="streaming" />}
                </div>
                {m.role === 'assistant' && m.telemetry && <TelemetryChip t={m.telemetry} />}
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
                <span className={`h-2 w-2 rounded-full ${backendLabel[backend].dot}`} />
                {backendLabel[backend].text}
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
