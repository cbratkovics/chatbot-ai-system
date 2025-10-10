import { useEffect, useRef, useState } from "react";
import { config } from "@/lib/config";

type Msg = { role: "user" | "assistant" | "system"; content: string };

export function useChatWebSocket(onMessage: (m: Msg) => void) {
  const [status, setStatus] = useState<"connecting"|"open"|"closed"|"error">("connecting");
  const socketRef = useRef<WebSocket | null>(null);
  const retryRef = useRef<number>(0);

  useEffect(() => {
    let alive = true;

    const connect = () => {
      setStatus("connecting");
      const ws = new WebSocket(config.NEXT_PUBLIC_WS_URL);
      socketRef.current = ws;

      ws.onopen = () => { if (!alive) return; retryRef.current = 0; setStatus("open"); };
      ws.onmessage = (e) => { if (!alive) return; try { onMessage(JSON.parse(e.data)); } catch {} };
      ws.onerror = () => { if (!alive) return; setStatus("error"); };
      ws.onclose = () => {
        if (!alive) return;
        setStatus("closed");
        const backoff = Math.min(1000 * Math.pow(2, retryRef.current++), 15000);
        setTimeout(connect, backoff);
      };
    };

    connect();
    return () => { alive = false; socketRef.current?.close(); };
  }, [onMessage]);

  const send = (m: Msg) => {
    if (socketRef.current?.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(m));
      return true;
    }
    return false;
  };

  return { status, send };
}
