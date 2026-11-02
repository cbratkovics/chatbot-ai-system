import { afterEach, describe, expect, it, vi } from 'vitest';
import { getLocalApiConfig } from './config';

afterEach(() => vi.unstubAllEnvs());

describe('source-only local chat configuration', () => {
  it('requires development mode and an explicit loopback backend', () => {
    vi.stubEnv('NODE_ENV', 'development');
    vi.stubEnv('NEXT_PUBLIC_API_URL', '');
    expect(() => getLocalApiConfig()).toThrow('explicitly');
    for (const raw of ['bad', 'https://example.com', 'https://user:pass@localhost', 'http://localhost/?live=1', 'ftp://localhost', 'http://localhost/unexpected']) {
      expect(() => getLocalApiConfig(raw)).toThrow();
    }
    expect(getLocalApiConfig('http://localhost:8000/').baseURL).toBe('http://localhost:8000/api/v1');
    expect(getLocalApiConfig('http://127.0.0.1:8000/api/v1/').baseURL).toBe('http://127.0.0.1:8000/api/v1');
    vi.stubEnv('NODE_ENV', 'production');
    expect(() => getLocalApiConfig('http://localhost:8000')).toThrow('local-development');
  });
});
