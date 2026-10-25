/**
 * One way to turn any backend error response into readable text.
 *
 * The backend sends {"message", "detail", "code"}; FastAPI validation errors carry a `detail`
 * list ({loc, msg}); unknown routes may carry only `detail`.  Never returns an object, so a
 * toast or error banner can't crash React.
 */

export class HttpError extends Error {
  constructor(message: string, public status: number, public code?: string, public body?: any) {
    super(message);
    this.name = 'HttpError';
  }
}

function fromDetail(detail: unknown): string | null {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((d: any) => {
      const loc = Array.isArray(d?.loc) ? d.loc.filter((p: unknown) => !['body', 'query', 'path'].includes(String(p))).join('.') : '';
      const msg = typeof d?.msg === 'string' ? d.msg : JSON.stringify(d);
      return loc ? `${loc}: ${msg}` : msg;
    });
    return parts.join('; ') || null;
  }
  return null;
}

export function messageFromBody(body: any, fallback: string): string {
  if (body && typeof body === 'object') {
    if (typeof body.message === 'string' && body.message) return body.message;
    const detail = fromDetail(body.detail);
    if (detail) return detail;
  }
  return fallback;
}

/** Build an HttpError from a failed Response (reads the body once). */
export async function httpError(res: Response): Promise<HttpError> {
  const body = await res.json().catch(() => null);
  return new HttpError(messageFromBody(body, res.statusText || `HTTP ${res.status}`), res.status, body?.code, body);
}

/** fetch JSON, throwing an HttpError with a readable message on failure. */
export async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) throw await httpError(res);
  return res.json();
}

/** Any thrown value as display text (for toasts). */
export function errorText(e: unknown): string {
  if (e instanceof Error) return e.message || e.name;
  if (typeof e === 'string') return e;
  try {
    return JSON.stringify(e);
  } catch {
    return 'Unexpected error';
  }
}
