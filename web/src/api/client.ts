const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export interface ApiErrorDetail {
  field: string;
  message: string;
}

/**
 * A failed API call, carrying the server's error envelope.
 *
 * The API returns one shape for every failure — { error: { code, message, details } } —
 * so the frontend has exactly one thing to parse and can show the server's own message
 * instead of inventing its own.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: ApiErrorDetail[];

  constructor(status: number, code: string, message: string, details: ApiErrorDetail[] = []) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }

  /** True when the caller is not signed in, which the UI treats as "log in first". */
  get isUnauthenticated() {
    return this.status === 401;
  }

  /** Field-level messages keyed by field name, for inline form errors. */
  get fieldErrors(): Record<string, string> {
    return Object.fromEntries(this.details.map((d) => [d.field, d.message]));
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      // The session lives in an httpOnly cookie, so every call must carry credentials.
      credentials: 'include',
      headers: init.body ? { 'Content-Type': 'application/json' } : undefined,
      ...init,
    });
  } catch {
    // fetch only rejects on a genuine network failure, which deserves its own message.
    throw new ApiError(0, 'network_error', 'Could not reach the server. Is the API running?');
  }

  if (response.status === 204) return undefined as T;

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const envelope = payload?.error;
    throw new ApiError(
      response.status,
      envelope?.code ?? 'unknown_error',
      envelope?.message ?? 'Something went wrong',
      envelope?.details ?? [],
    );
  }

  return payload as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};

export function buildQuery(params: Record<string, string | number | undefined | null>) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : '';
}
