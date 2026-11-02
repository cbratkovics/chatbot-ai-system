/** Local-reference chat only. The public site never imports this module. */
export function getLocalApiConfig(raw = process.env.NEXT_PUBLIC_API_URL) {
  if (process.env.NODE_ENV !== 'development') {
    throw new Error('Live chat is a local-development reference only.');
  }
  if (!raw) throw new Error('Set NEXT_PUBLIC_API_URL explicitly to a loopback backend URL.');
  const url = new URL(raw);
  if (!['http:', 'https:'].includes(url.protocol) ||
      !['localhost', '127.0.0.1', '[::1]'].includes(url.hostname) ||
      url.username || url.password || url.search || url.hash ||
      !['', '/', '/api/v1', '/api/v1/'].includes(url.pathname)) {
    throw new Error('Local chat requires a loopback origin or /api/v1 URL without credentials, query or fragment.');
  }
  url.pathname = '/api/v1';
  return { baseURL: url.toString().replace(/\/$/, ''), timeout: 30_000 };
}
