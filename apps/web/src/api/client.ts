const API_BASE = import.meta.env.VITE_AOS_API_BASE ?? "http://127.0.0.1:8080";

export type ApiErrorBody = {
  code: string;
  message: string;
  traceId?: string;
  details?: unknown;
};

/** 76 · 网络层错误可读化（避免裸 Failed to fetch） */
export function formatNetworkError(err: unknown, method: string, path: string): Error {
  const raw = err instanceof Error ? err.message : String(err);
  const unreachable =
    raw === "Failed to fetch" ||
    raw.includes("NetworkError") ||
    raw.includes("Load failed") ||
    raw.includes("ECONNREFUSED");
  const message = unreachable
    ? `无法连接 aos-api（${API_BASE}${path}）· 请确认 API 已启动并检查网络`
    : raw;
  const out = Object.assign(new Error(message), {
    status: 0,
    body: { code: "NETWORK", message, path, method } as ApiErrorBody,
    cause: err,
  });
  console.error("[aos-api]", { method, path, base: API_BASE, error: message, raw });
  return out;
}

function authHeaders(): HeadersInit {
  return {
    Authorization: "Bearer dev",
    "X-Org-Id": "dev-org",
    "X-Project-Id": "dev-project",
    "Content-Type": "application/json",
  };
}

async function parseError(res: Response, method: string, path: string): Promise<Error> {
  const body = (await res.json().catch(() => ({}))) as ApiErrorBody;
  const message = body.message || res.statusText || `HTTP ${res.status}`;
  console.warn("[aos-api]", {
    method,
    path,
    status: res.status,
    code: body.code,
    traceId: body.traceId,
    message,
  });
  return Object.assign(new Error(message), { status: res.status, body });
}

async function request<T>(
  method: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      method,
      headers: { ...authHeaders(), ...(init?.headers || {}) },
    });
  } catch (e) {
    throw formatNetworkError(e, method, path);
  }
  if (!res.ok) {
    throw await parseError(res, method, path);
  }
  return res.json() as Promise<T>;
}

export async function apiGet<T>(path: string): Promise<T> {
  return request<T>("GET", path);
}

export async function apiPost<T>(
  path: string,
  body: unknown,
  extraHeaders?: HeadersInit,
): Promise<T> {
  return request<T>("POST", path, {
    headers: extraHeaders,
    body: JSON.stringify(body),
  });
}

export async function apiPut<T>(
  path: string,
  body: unknown,
  extraHeaders?: HeadersInit,
): Promise<T> {
  return request<T>("PUT", path, {
    headers: extraHeaders,
    body: JSON.stringify(body),
  });
}

export async function apiPatch<T>(
  path: string,
  body: unknown,
  extraHeaders?: HeadersInit,
): Promise<T> {
  return request<T>("PATCH", path, {
    headers: extraHeaders,
    body: JSON.stringify(body),
  });
}

export async function apiDelete<T>(path: string, extraHeaders?: HeadersInit): Promise<T> {
  return request<T>("DELETE", path, { headers: extraHeaders });
}

/** 轻量健康探针（状态条用；失败不抛业务码） */
export async function probeApiHealth(): Promise<{ ok: boolean; detail: string }> {
  try {
    const res = await fetch(`${API_BASE}/v1/health`, {
      headers: {
        Authorization: "Bearer dev",
        "X-Org-Id": "dev-org",
        "X-Project-Id": "dev-project",
      },
    });
    if (!res.ok) {
      console.warn("[aos-api]", { method: "GET", path: "/v1/health", status: res.status });
      return { ok: false, detail: `health HTTP ${res.status}` };
    }
    return { ok: true, detail: "ok" };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    console.error("[aos-api]", { method: "GET", path: "/v1/health", error: msg });
    return {
      ok: false,
      detail: `无法连接 ${API_BASE} · ensure-api.sh · deploy/dev/aos-api.*.log`,
    };
  }
}

export { API_BASE };
