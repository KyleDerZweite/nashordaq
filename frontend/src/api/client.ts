const BASE_URL = "/api";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// FastAPI validation errors (422) return detail as an array of error objects.
function formatErrorDetail(detail: unknown): string | undefined {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((entry) =>
        typeof entry?.msg === "string" ? entry.msg : JSON.stringify(entry),
      )
      .join(", ");
    return messages || undefined;
  }
  if (detail != null) return JSON.stringify(detail);
  return undefined;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(
      formatErrorDetail(body.detail) ?? `Request failed: ${res.status}`,
      res.status,
    );
  }
  return res.json() as Promise<T>;
}

export function get<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function put<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function del<T>(path: string): Promise<T> {
  return request<T>(path, { method: "DELETE" });
}

export function getMarketQuote<T>(
  gameName: string,
  tagLine: string,
): Promise<T> {
  const search = new URLSearchParams({
    gameName,
    tagLine,
  });

  return get<T>(`/market/quote?${search.toString()}`);
}

export function getMarketAccount<T>(
  gameName: string,
  tagLine: string,
): Promise<T> {
  const search = new URLSearchParams({
    gameName,
    tagLine,
  });

  return get<T>(`/market/account?${search.toString()}`);
}
