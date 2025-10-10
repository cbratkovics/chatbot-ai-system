// Environment configuration with fallback defaults
const DEFAULT_CONFIG = {
  NEXT_PUBLIC_API_URL: 'https://chatbot-ai-system.onrender.com',
  NEXT_PUBLIC_WS_URL: 'wss://chatbot-ai-system.onrender.com',
} as const;

const envVars = [
  'NEXT_PUBLIC_API_URL',
  'NEXT_PUBLIC_WS_URL',
] as const;

type EnvVar = typeof envVars[number];

function loadEnvConfig(): Record<EnvVar, string> {
  const config: Record<EnvVar, string> = {} as Record<EnvVar, string>;
  const usingDefaults: string[] = [];

  for (const envVar of envVars) {
    const value = process.env[envVar];
    if (!value) {
      config[envVar] = DEFAULT_CONFIG[envVar];
      usingDefaults.push(envVar);
    } else {
      config[envVar] = value;
    }
  }

  if (usingDefaults.length > 0) {
    console.warn(
      `[Config] Using default values for: ${usingDefaults.join(', ')}\n` +
      `Default API URL: ${DEFAULT_CONFIG.NEXT_PUBLIC_API_URL}\n` +
      `Default WS URL: ${DEFAULT_CONFIG.NEXT_PUBLIC_WS_URL}`
    );
  }

  return config;
}

export const config = loadEnvConfig();

export const API_CONFIG = {
  baseURL: config.NEXT_PUBLIC_API_URL,
  wsURL: config.NEXT_PUBLIC_WS_URL,
  timeout: 30000,
  retries: 3,
};
