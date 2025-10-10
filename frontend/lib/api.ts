import { API_CONFIG } from './config';

type ChatMessage = { role: 'user' | 'assistant' | 'system'; content: string };
type ChatRequest = {
  model: string;
  messages: ChatMessage[];
  stream?: boolean;
  temperature?: number;
  [k: string]: any;
};

function join(base: string, path: string) {
  if (!path) return base;
  if (/^https?:\/\//.test(path)) return path;
  const a = base.replace(/\/+$/, '');
  const b = path.replace(/^\/+/, '');
  return `${a}/${b}`;
}

async function request(path: string, init: RequestInit = {}) {
  const url = join(API_CONFIG.baseURL, path);
  const headers = new Headers(init.headers || {});
  if (!headers.has('Accept')) headers.set('Accept', 'application/json');
  if ((init.method || 'GET').toUpperCase() !== 'GET' && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const controller = new AbortController();
  const timeout = (API_CONFIG as any).timeout ?? 30000;
  const to = setTimeout(() => controller.abort(), timeout);
  try {
    const res = await fetch(url, { ...init, headers, signal: controller.signal });
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      throw new Error(`HTTP ${res.status} ${res.statusText} ${text}`);
    }
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('application/json')) return res.json();
    return res.text();
  } finally {
    clearTimeout(to);
  }
}

async function getModels(): Promise<any[]> {
  const data = await request('/chat/models');
  if (Array.isArray(data)) return data;
  return data?.models ?? data?.data ?? [];
}

async function createChatCompletion(payload: ChatRequest): Promise<any> {
  return request('/chat/completions', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

async function health(): Promise<any> {
  return request('/health');
}

type APIClient = {
  get: (path: string, init?: RequestInit) => Promise<any>;
  post: (path: string, body?: unknown, init?: RequestInit) => Promise<any>;
  request: (path: string, init?: RequestInit) => Promise<any>;
  getModels: () => Promise<any[]>;
  createChatCompletion: (payload: ChatRequest) => Promise<any>;
  health: () => Promise<any>;
};

const apiClient: APIClient = {
  get: (path, init) => request(path, { ...(init || {}), method: 'GET' }),
  post: (path, body, init) =>
    request(path, { ...(init || {}), method: 'POST', body: body == null ? undefined : JSON.stringify(body) }),
  request,
  getModels,
  createChatCompletion,
  health,
};

export { apiClient, request, getModels, createChatCompletion, health };
export default apiClient;
