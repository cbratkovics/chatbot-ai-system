/** Fetch helpers for the SSE contract `meta → delta* → done | error` (ADR 0005). */

export async function fetchWithTimeout(url: string, init: RequestInit, timeoutMs: number): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

export type SseHandler = (event: string, data: unknown) => void;

/** Parse a Server-Sent Events body incrementally; calls onEvent for each complete event. */
export async function readSse(
  body: ReadableStream<Uint8Array>,
  onEvent: SseHandler,
  onChunk?: () => void,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
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
        let parsed: unknown = data;
        try {
          parsed = JSON.parse(data);
        } catch {
          /* non-JSON payload: pass the raw string */
        }
        onEvent(event, parsed);
      }
      sep = buffer.indexOf('\n\n');
    }
  }
}
