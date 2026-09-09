/** Typed readers for the backend's error envelope: `{error: {code, message, provider, status_code}, request_id}`. */

export type ErrorDetail = {
  code?: string;
  message?: string;
  provider?: string;
  status_code?: number;
  partial_content?: string | null;
};

export type ErrorEnvelope = {
  error?: ErrorDetail | string;
  detail?: string;
  request_id?: string;
};

function isRecord(x: unknown): x is Record<string, unknown> {
  return typeof x === 'object' && x !== null;
}

export function asEnvelope(body: unknown): ErrorEnvelope {
  if (!isRecord(body)) return {};
  const raw = body.error;
  const error: ErrorDetail | string | undefined =
    typeof raw === 'string' ? raw : isRecord(raw) ? (raw as ErrorDetail) : undefined;
  return {
    error,
    detail: typeof body.detail === 'string' ? body.detail : undefined,
    request_id: typeof body.request_id === 'string' ? body.request_id : undefined,
  };
}

/** Keep printable ASCII only and cap length: the banner shows backend text verbatim otherwise. */
export function sanitize(text: unknown, max = 300): string {
  return String(text ?? '')
    .replace(/[^\x20-\x7E]/g, '')
    .slice(0, max);
}

/** One readable line from an error envelope, e.g. `402 provider_quota_exhausted [openai]: … · request <id>`. */
export function describeErrorBody(status: number | undefined, body: unknown): string {
  const env = asEnvelope(body);
  const err = env.error;
  const detail: ErrorDetail = typeof err === 'string' ? { message: err } : err ?? {};
  const message = detail.message ?? env.detail ?? 'Unknown error';
  const provider = detail.provider ? ` [${sanitize(detail.provider, 20)}]` : '';
  const reqId = env.request_id ? ` · request ${sanitize(env.request_id, 36)}` : '';
  const statusPart = status ?? detail.status_code;
  const code = detail.code ? ` ${sanitize(detail.code, 40)}` : '';
  return `${statusPart ?? ''}${code}${provider}: ${sanitize(message)}${reqId}`.trim();
}

export async function describeHttpError(res: Response): Promise<string> {
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    body = { error: res.statusText };
  }
  return describeErrorBody(res.status, body);
}

export function describeNetworkError(e: unknown): string {
  if (e instanceof DOMException && e.name === 'AbortError') {
    return 'Timed out waiting for the backend. Free-tier instances sleep when idle; try again in a moment.';
  }
  const message = e instanceof Error ? e.message : String(e);
  return `Network error: ${sanitize(message)}`;
}
