import { tenantAuthHeaders, type MeResponse, applyMeToTenant } from "./tenant";
import { getApiBase } from "./apiBase";
import { applyProbeResult, isOffline } from "../lib/offlineStore";
import {
  enqueueOfflineWrite,
  listOfflineQueue,
  markOfflineQueueError,
  removeOfflineQueueItem,
} from "../lib/offlineQueue";
import { readOfflineSnapshot, saveOfflineSnapshot } from "../lib/offlineSnapshot";
import { OfflineQueuedError } from "../lib/offlineQueuedError";

export type ApiErrorBody = {
  code: string;
  message: string;
  traceId?: string;
  details?: unknown;
};

/** 76 · 网络层错误可读化（避免裸 Failed to fetch） */
export function formatNetworkError(err: unknown, method: string, path: string): Error {
  const base = getApiBase();
  const raw = err instanceof Error ? err.message : String(err);
  const unreachable =
    raw === "Failed to fetch" ||
    raw.includes("NetworkError") ||
    raw.includes("Load failed") ||
    raw.includes("ECONNREFUSED");
  const message = unreachable
    ? `无法连接 aos-api（${base}${path}）· 请确认 API 已启动并检查网络`
    : raw;
  const out = Object.assign(new Error(message), {
    status: 0,
    body: { code: "NETWORK", message, path, method } as ApiErrorBody,
    cause: err,
  });
  console.error("[aos-api]", { method, path, base, error: message, raw });
  return out;
}

function authHeaders(): HeadersInit {
  return tenantAuthHeaders();
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

function guardOfflineWrite(method: string, path: string, body?: unknown): void {
  if (!isOffline()) return;
  const item = enqueueOfflineWrite({ method, path, body });
  throw new OfflineQueuedError(item.id, item.summary);
}

function tryParseBody(body: BodyInit): unknown {
  if (typeof body === "string") {
    try {
      return JSON.parse(body);
    } catch {
      return undefined;
    }
  }
  return undefined;
}

async function request<T>(
  method: string,
  path: string,
  init?: RequestInit,
): Promise<T> {
  const m = method.toUpperCase();
  if (m !== "GET" && m !== "HEAD") {
    guardOfflineWrite(m, path, init?.body ? tryParseBody(init.body) : undefined);
  }

  if (m === "GET" && isOffline()) {
    const cached = readOfflineSnapshot<T>(path);
    if (cached != null) {
      console.info("[aos-offline]", { event: "snap_hit", path });
      return cached;
    }
    throw Object.assign(new Error(`离线且无缓存：${path}`), {
      status: 0,
      body: { code: "OFFLINE_NO_CACHE", message: `离线且无缓存：${path}` },
    });
  }

  let res: Response;
  try {
    res = await fetch(`${getApiBase()}${path}`, {
      ...init,
      method,
      headers: { ...authHeaders(), ...(init?.headers || {}) },
    });
  } catch (e) {
    if (m === "GET") {
      const cached = readOfflineSnapshot<T>(path);
      if (cached != null) {
        applyProbeResult(false);
        console.info("[aos-offline]", { event: "snap_fallback", path });
        return cached;
      }
    }
    throw formatNetworkError(e, method, path);
  }
  if (!res.ok) {
    throw await parseError(res, method, path);
  }
  const data = (await res.json()) as T;
  if (m === "GET") {
    saveOfflineSnapshot(path, data);
  }
  return data;
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

/** TWA.2 · 启动时从 /v1/me 注入租户（失败保留默认测试工作区） */
export async function bootstrapTenantFromMe(): Promise<MeResponse | null> {
  try {
    const me = await apiGet<MeResponse>("/v1/me");
    applyMeToTenant(me);
    console.info("[aos-api]", {
      event: "tenant_bootstrapped",
      orgId: me.orgId,
      projectId: me.projectId,
      workspaceName: me.workspaceName,
    });
    return me;
  } catch (e) {
    console.warn("[aos-api]", {
      event: "tenant_bootstrap_failed",
      error: e instanceof Error ? e.message : String(e),
    });
    return null;
  }
}

/** 轻量健康探针（状态条用；失败不抛业务码） */
export async function probeApiHealth(): Promise<{ ok: boolean; detail: string }> {
  try {
    const res = await fetch(`${getApiBase()}/v1/health`, {
      headers: authHeaders(),
    });
    if (!res.ok) {
      console.warn("[aos-api]", { method: "GET", path: "/v1/health", status: res.status });
      applyProbeResult(false);
      return { ok: false, detail: `health HTTP ${res.status}` };
    }
    applyProbeResult(true);
    return { ok: true, detail: "ok" };
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    console.error("[aos-api]", { method: "GET", path: "/v1/health", error: msg });
    applyProbeResult(false);
    return {
      ok: false,
      detail: `无法连接 ${getApiBase()} · ensure-api.sh · deploy/dev/aos-api.*.log`,
    };
  }
}

/**
 * 手动冲刷待同步（上线后）；按入队序；失败保留 lastError。
 */
export async function flushOfflineQueue(): Promise<{
  ok: number;
  fail: number;
  remaining: number;
}> {
  if (isOffline()) {
    return { ok: 0, fail: 0, remaining: listOfflineQueue().length };
  }
  const items = [...listOfflineQueue()];
  let ok = 0;
  let fail = 0;
  for (const item of items) {
    try {
      await request(item.method, item.path, {
        body: item.body !== undefined ? JSON.stringify(item.body) : undefined,
        headers:
          item.body !== undefined
            ? { "Content-Type": "application/json" }
            : undefined,
      });
      removeOfflineQueueItem(item.id);
      ok += 1;
    } catch (e) {
      markOfflineQueueError(
        item.id,
        e instanceof Error ? e.message : String(e),
      );
      fail += 1;
    }
  }
  const remaining = listOfflineQueue().length;
  console.info("[aos-offline]", { event: "flush", ok, fail, remaining });
  return { ok, fail, remaining };
}

export { getApiBase, OfflineQueuedError };
