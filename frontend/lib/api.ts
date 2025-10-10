import { API_CONFIG } from './config';

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
  const to = setTimeout(() => controller.abort(), (API_CONFIG as any).timeout ?? 30000);
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

const apiClient = {
  get: (path: string, init?: RequestInit) => request(path, { ...(init || {}), method: 'GET' }),
  post: (path: string, body?: unknown, init?: RequestInit) =>
    request(path, { ...(init || {}), method: 'POST', body: body == null ? undefined : JSON.stringify(body) }),
  request,
};

export { apiClient, request };
export default apiClient;
