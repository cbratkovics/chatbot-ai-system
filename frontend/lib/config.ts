/** Backend base URL. The only variable the demo needs is NEXT_PUBLIC_API_URL (ADR 0005: SSE, no WebSocket). */
const DEFAULT_API = 'https://chatbot-ai-system.onrender.com/api/v1';

function stripTrailingSlash(u: string) {
  return u.endsWith('/') ? u.slice(0, -1) : u;
}

/** Accepts a bare origin or a full /api/v1 URL and normalises to `<origin>/api/v1`. */
function normalizeApiUrl(urlStr: string) {
  try {
    if (!urlStr) return DEFAULT_API;
    const u = new URL(urlStr);
    let p = u.pathname.replace(/\/+$/, '');
    if (!/^\/api\//.test(p)) p = p === '' ? '/api/v1' : p + '/api/v1';
    u.pathname = p;
    u.search = '';
    u.hash = '';
    return stripTrailingSlash(u.toString());
  } catch {
    return DEFAULT_API;
  }
}

const baseURL = normalizeApiUrl(process.env.NEXT_PUBLIC_API_URL ?? '');

export const API_CONFIG = { baseURL, timeout: 30000 };
