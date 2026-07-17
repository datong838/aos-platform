const API_BASE = import.meta.env.VITE_AOS_API_BASE ?? "http://127.0.0.1:8080";

export type ApiErrorBody = {
  code: string;
  message: string;
  traceId?: string;
  details?: unknown;
};

function authHeaders(): HeadersInit {
  return {
    Authorization: "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "Content-Type": "application/json",
  };
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: authHeaders() });
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as ApiErrorBody;
    throw Object.assign(new Error(body.message || res.statusText), {
      status: res.status,
      body,
    });
  }
  return res.json() as Promise<T>;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as ApiErrorBody;
    throw Object.assign(new Error(err.message || res.statusText), {
      status: res.status,
      body: err,
    });
  }
  return res.json() as Promise<T>;
}

export { API_BASE };
