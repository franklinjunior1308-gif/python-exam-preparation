/** Browser-side API client. Talks to the same-origin /bff proxy, never to the backend directly. */

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: { loc: (string | number)[]; msg: string }[],
    public requestId?: string,
  ) {
    super(message);
  }
}

type Options = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
};

export function buildQuery(query?: Options["query"]): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const text = params.toString();
  return text ? `?${text}` : "";
}

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/bff/${path}${buildQuery(options.query)}`, {
      method: options.method ?? "GET",
      headers: {
        "content-type": "application/json",
        // custom header: cross-site pages cannot send it, which blocks CSRF on cookie auth
        "x-requested-with": "fixflow",
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      cache: "no-store",
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError(0, "network", "Network error");
  }

  if (res.status === 204) return undefined as T;
  const text = await res.text();
  const payload = text ? (JSON.parse(text) as unknown) : null;

  if (!res.ok) {
    const error = (payload as { error?: { code?: string; message?: string; details?: never; request_id?: string } })
      ?.error;
    throw new ApiError(
      res.status,
      error?.code ?? "generic",
      error?.message ?? res.statusText,
      error?.details,
      error?.request_id,
    );
  }
  return payload as T;
}

/** Multipart upload (the browser sets the boundary; JSON content-type must not be forced). */
export async function apiUpload<T>(path: string, form: FormData): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/bff/${path}`, {
      method: "POST",
      headers: { "x-requested-with": "fixflow" },
      body: form,
      cache: "no-store",
      credentials: "same-origin",
    });
  } catch {
    throw new ApiError(0, "network", "Network error");
  }
  const text = await res.text();
  const payload = text ? (JSON.parse(text) as unknown) : null;
  if (!res.ok) {
    const error = (payload as { error?: { code?: string; message?: string; request_id?: string } })?.error;
    throw new ApiError(res.status, error?.code ?? "generic", error?.message ?? res.statusText, undefined, error?.request_id);
  }
  return payload as T;
}

/** Map a backend error code to a translation key suffix, falling back to a generic message. */
export function errorKey(error: unknown): string {
  if (error instanceof ApiError) {
    return error.code === "network" ? "err.network" : `err.${error.code}`;
  }
  return "err.generic";
}
