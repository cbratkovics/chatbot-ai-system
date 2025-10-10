"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { API } from "@/lib/api";
import { useChatWebSocket } from "@/hooks/useChatWebSocket";

type Message = { role: "user" | "assistant"; content: string };

const Bubble = ({ role, children }: { role: Message["role"]; children: React.ReactNode }) => (
  <div className={`flex ${role === "user" ? "justify-end" : "justify-start"} my-2`}>
    <div className={`${role === "user" ? "bg-primary text-primary-foreground" : "bg-secondary text-secondary-foreground"} max-w-[80%] rounded-2xl px-4 py-2 shadow-sm`}>
      {children}
    </div>
  </div>
);

export function ChatInterface() {
  const [models, setModels] = useState<string[]>([]);
  const [model, setModel] = useState<string>("");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scroller = useRef<HTMLDivElement>(null);

  const onWsMessage = useCallback((m: any) => {
    if (m?.role && m?.content) {
      setMessages(prev => [...prev, { role: m.role, content: m.content }]);
    }
  }, []);
  const { status: wsStatus, send: wsSend } = useChatWebSocket(onWsMessage);

  useEffect(() => { scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" }); }, [messages]);

  useEffect(() => {
    let mounted = true;
    API.models()
      .then(({ models }) => {
        if (!mounted) return;
        setModels(models);
        if (!model && models.length) setModel(models[0]);
      })
      .catch((e) => setError(`Failed to load models: ${e.message}`));
    return () => { mounted = false; };
  }, []);

  const canSend = useMemo(() => input.trim().length > 0 && (model?.length ?? 0) > 0, [input, model]);

  const handleSend = async () => {
    if (!canSend) return;
    const text = input.trim();
    setInput("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setLoading(true);
    setError(null);
    try {
      const { message } = await API.complete({ model, messages: [...messages, { role: "user", content: text }] });
      setMessages((m) => [...m, { role: "assistant", content: message }]);
      wsSend({ role: "user", content: text });
    } catch (e: any) {
      setError(e?.message ?? "Request failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid grid-rows-[auto,1fr,auto] gap-4 min-h-[70dvh] rounded-2xl border border-border bg-card shadow-sm">
      <div className="px-4 pt-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="text-sm text-muted-foreground">WebSocket: 
            <span className={`ml-1 font-medium ${wsStatus === "open" ? "text-green-500" : wsStatus === "connecting" ? "text-yellow-500" : "text-red-500"}`}>{wsStatus}</span>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm text-muted-foreground">Model</label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="rounded-md border border-input bg-background px-2 py-1 text-sm outline-none focus:ring-2 focus:ring-ring"
            >
              {models.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <button
            onClick={async () => { try { const h = await API.health(); setError(null); } catch (e:any) { setError(`Health check failed: ${e.message}`); } }}
            className="ml-auto rounded-md border border-input bg-background px-3 py-1 text-sm hover:bg-accent hover:text-accent-foreground"
          >
            Health
          </button>
        </div>
        {error && <div className="mt-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive-foreground">{error}</div>}
      </div>

      <div ref={scroller} className="overflow-y-auto px-4">
        {messages.length === 0 && (
          <div className="my-16 text-center text-sm text-muted-foreground">Ask anything to get started.</div>
        )}
        {messages.map((m, i) => <Bubble key={i} role={m.role}>{m.content}</Bubble>)}
        {loading && <div className="my-2 text-xs text-muted-foreground">Thinking…</div>}
      </div>

      <div className="border-t border-border p-3">
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            rows={1}
            placeholder="Type your message..."
            className="min-h-[44px] max-h-40 w-full resize-y rounded-lg border border-input bg-background px-3 py-2 outline-none focus:ring-2 focus:ring-ring"
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
          />
          <button
            onClick={handleSend}
            disabled={!canSend || loading}
            className="shrink-0 rounded-lg bg-primary px-4 py-2 text-primary-foreground shadow-sm disabled:opacity-60"
          >
            Send
          </button>
        </div>
        <div className="mt-2 flex justify-between text-[11px] text-muted-foreground">
          <span>Enter to send • Shift+Enter for newline</span>
          <span>Calls your Render API with model routing</span>
        </div>
      </div>
    </div>
  );
}
