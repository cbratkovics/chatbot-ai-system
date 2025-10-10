const ENV = {
  NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? '',
  NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL ?? '',
};

const DEFAULT_API = 'https://chatbot-ai-system.onrender.com/api/v1';

function stripTrailingSlash(u: string) {
  return u.endsWith('/') ? u.slice(0, -1) : u;
}

function normalizeApiUrl(urlStr: string) {
  try {
    if (!urlStr) return DEFAULT_API;
    const u = new URL(urlStr);
    let p = u.pathname.replace(/\/+$/, '');
    if (!/^\/api\//.test(p)) p = (p === '' ? '/api/v1' : p + '/api/v1');
    u.pathname = p; u.search = ''; u.hash = '';
    return stripTrailingSlash(u.toString());
  } catch {
    return DEFAULT_API;
  }
}

function deriveWsUrl(apiUrl: string, explicit?: string) {
  if (explicit) {
    try {
      const u = new URL(explicit);
      if (!/\/ws\//.test(u.pathname)) u.pathname = '/ws/chat';
      return stripTrailingSlash(u.toString());
    } catch {}
  }
  const u = new URL(apiUrl);
  const proto = u.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${u.host}/ws/chat`;
}

const baseURL = normalizeApiUrl(ENV.NEXT_PUBLIC_API_URL);
const wsURL = deriveWsUrl(baseURL, ENV.NEXT_PUBLIC_WS_URL);

export const config = { NEXT_PUBLIC_API_URL: baseURL, NEXT_PUBLIC_WS_URL: wsURL };
export const API_CONFIG = { baseURL, wsURL, timeout: 30000, retries: 3 };
