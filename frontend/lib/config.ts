// Production configuration validation
const requiredEnvVars = [
  'NEXT_PUBLIC_API_URL',
  'NEXT_PUBLIC_WS_URL',
] as const;

type RequiredEnvVar = typeof requiredEnvVars[number];

function validateEnv(): Record<RequiredEnvVar, string> {
  const missing: string[] = [];
  const config: Partial<Record<RequiredEnvVar, string>> = {};

  for (const envVar of requiredEnvVars) {
    const value = process.env[envVar];
    if (!value) {
      missing.push(envVar);
    } else {
      config[envVar] = value;
    }
  }

  if (missing.length > 0) {
    throw new Error(
      `Missing required environment variables: ${missing.join(', ')}`
    );
  }

  return config as Record<RequiredEnvVar, string>;
}

export const config = validateEnv();

export const API_CONFIG = {
  baseURL: config.NEXT_PUBLIC_API_URL,
  wsURL: config.NEXT_PUBLIC_WS_URL,
  timeout: 30000,
  retries: 3,
};
