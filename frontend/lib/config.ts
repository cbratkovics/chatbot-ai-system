const envVars = ['NEXT_PUBLIC_API_URL','NEXT_PUBLIC_WS_URL'] as const;
type EnvVar = (typeof envVars)[number];

const DEFAULT_CONFIG = {
  NEXT_PUBLIC_API_URL: 'https://chatbot-ai-system.onrender.com/api/v1',
  NEXT_PUBLIC_WS_URL: 'wss://chatbot-ai-system.onrender.com/ws/chat',
} as const;

function stripTrailingSlash(u: string) {
  return u.endsWith('/') ? u.slice(0, -1) : u;
}

function loadEnvConfig(): Record<string, string> {
  const cfg: Record<string, string> = {} as Record<string, string>;
  for (const k of envVars) {
    const v = process.env[k];
    cfg[k] = v && v.length ? v : DEFAULT_CONFIG[k];
  }
  return {
    ...cfg,
    NEXT_PUBLIC_API_URL: stripTrailingSlash(cfg.NEXT_PUBLIC_API_URL),
    NEXT_PUBLIC_WS_URL: stripTrailingSlash(cfg.NEXT_PUBLIC_WS_URL),
  };
}

export const config = loadEnvConfig();
export const API_CONFIG = {
  baseURL: config.NEXT_PUBLIC_API_URL,
  wsURL: config.NEXT_PUBLIC_WS_URL,
  timeout: 30000,
  retries: 3,
};
