import { getApiBase } from "../apiBase";
import { tenantAuthHeaders } from "../tenant";
import { AIP_OPERATIONS, type AipOperationId } from "./operations";
import { aipClientError } from "./errors";

type FetchImplementation = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

export type AipClientOptions = {
  fetch?: FetchImplementation;
  getBaseUrl?: () => string;
  getAuthHeaders?: () => Record<string, string>;
};

function hasClientScope(value: unknown): boolean {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  return Object.keys(value as Record<string, unknown>).some((key) =>
    ["orgId", "projectId", "org_id", "project_id"].includes(key),
  );
}

function fillPath(template: string, params: Record<string, string>): string {
  return template.replace(/\{([^}]+)\}/g, (_match, key: string) => {
    const value = params[key];
    if (!value || value !== value.trim()) throw new TypeError(`missing or invalid path parameter: ${key}`);
    return encodeURIComponent(value);
  });
}

export class AipClient {
  private readonly fetchOverride?: FetchImplementation;
  private readonly baseUrl: () => string;
  private readonly authHeaders: () => Record<string, string>;

  constructor(options: AipClientOptions = {}) {
    this.fetchOverride = options.fetch;
    this.baseUrl = options.getBaseUrl ?? getApiBase;
    this.authHeaders = options.getAuthHeaders ?? tenantAuthHeaders;
  }

  async request<T>(
    operationId: AipOperationId,
    options: {
      params?: Record<string, string>;
      body?: unknown;
      headers?: Record<string, string>;
    } = {},
  ): Promise<T> {
    const operation = AIP_OPERATIONS[operationId];
    if (hasClientScope(options.body)) {
      throw new TypeError("AIP request body must not contain org/project scope");
    }
    const path = fillPath(operation.path, options.params ?? {});
    const fetcher = this.fetchOverride ?? globalThis.fetch.bind(globalThis);
    let response: Response;
    try {
      response = await fetcher(`${this.baseUrl().replace(/\/$/, "")}${path}`, {
        method: operation.method,
        headers: {
          ...this.authHeaders(),
          ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
          ...(options.headers ?? {}),
        },
        ...(options.body === undefined ? {} : { body: JSON.stringify(options.body) }),
      });
    } catch (error) {
      throw aipClientError(error, {
        status: 0,
        operationId: `${operation.mutation ? "mutate" : "read"}:${operationId}`,
        fallbackMessage: `AIP dependency unavailable: ${path}`,
      });
    }
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      throw aipClientError(payload, {
        status: response.status,
        operationId: `${operation.mutation ? "mutate" : "read"}:${operationId}`,
        fallbackMessage: response.statusText || `HTTP ${response.status}`,
      });
    }
    if (payload === null || typeof payload !== "object") {
      throw aipClientError(null, {
        status: 0,
        operationId: `${operation.mutation ? "mutate" : "read"}:${operationId}`,
        fallbackMessage: "AIP success response is malformed",
      });
    }
    return payload as T;
  }
}

export const aipClient = new AipClient();

