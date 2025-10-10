import { config } from "./config";

const BASE = config.NEXT_PUBLIC_API_URL;
const TIMEOUT = 30000;

function withTimeout<T>(p: Promise<T>, ms = TIMEOUT): Promise<T> {
  return new Promise((resolve, reject) => {
    const id = setTimeout(() => reject(new Error("Request timeout")), ms);
    p.then(v => { clearTimeout(id); resolve(v); }).catch(e => { clearTimeout(id); reject(e); });
  });
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${BASE}${path.startsWith("/") ? "" : "/"}${path}`;
  const res = await withTimeout(fetch(url, {
    method: init?.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
    mode: "cors",
    credentials: "omit",
    cache: "no-store",
    body: init?.body,
  }));
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status} ${res.statusText} ${text}`);
  }
  if (res.status === 204) return {} as T;
  return res.json() as Promise<T>;
}

export const API = {
  models: () => request<{ models: string[] }>("/chat/models"),
  complete: (payload: unknown) =>
    request<{ message: string }>("/chat/completions", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  health: () => request<{ status: string }>("/health"),
};
