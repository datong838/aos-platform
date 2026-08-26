import { getApiBase } from "../apiBase";
import { tenantAuthHeaders } from "../tenant";
import type { InvestigationCaseListResponse, InvestigationReadClient, InvestigationRunListResponse, InvestigationWorkbenchView } from "./contracts";
import { parseInvestigationCaseList, parseInvestigationRunList, parseInvestigationWorkbenchView } from "./parser";

type FetchImplementation = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
export type EcommerceInvestigationClientOptions = { fetch?: FetchImplementation; getBaseUrl?: () => string; getAuthHeaders?: () => Record<string, string> };
export class EcommerceInvestigationClientError extends Error {
  constructor(message: string, readonly status: number, readonly code: string) { super(message); this.name = "EcommerceInvestigationClientError"; }
}
const RESOURCE_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$/;

export class EcommerceInvestigationClient implements InvestigationReadClient {
  private readonly fetchImpl: FetchImplementation; private readonly baseUrl: () => string; private readonly authHeaders: () => Record<string, string>;
  constructor(options: EcommerceInvestigationClientOptions = {}) { this.fetchImpl = options.fetch ?? globalThis.fetch.bind(globalThis); this.baseUrl = options.getBaseUrl ?? getApiBase; this.authHeaders = options.getAuthHeaders ?? tenantAuthHeaders; }
  private async get(path: string, signal?: AbortSignal): Promise<unknown> {
    let response: Response;
    try { response = await this.fetchImpl(`${this.baseUrl().replace(/\/$/, "")}${path}`, { method: "GET", headers: { ...this.authHeaders(), Accept: "application/json" }, signal }); }
    catch (cause) { if (cause instanceof DOMException && cause.name === "AbortError") throw cause; throw new EcommerceInvestigationClientError(cause instanceof Error ? cause.message : String(cause), 0, "NETWORK"); }
    const payload: unknown = await response.json().catch(() => undefined);
    if (!response.ok) { const raw = typeof payload === "object" && payload !== null ? payload as Record<string, unknown> : {}; throw new EcommerceInvestigationClientError(typeof raw.message === "string" ? raw.message : response.statusText || `HTTP ${response.status}`, response.status, typeof raw.code === "string" ? raw.code : "HTTP_ERROR"); }
    if (payload === undefined) throw new EcommerceInvestigationClientError("canonical API returned non-JSON success", 0, "INVALID_SUCCESS_RESPONSE");
    return payload;
  }
  async listCases(signal?: AbortSignal): Promise<InvestigationCaseListResponse> { return parseInvestigationCaseList(await this.get("/v1/ecommerce/investigations/cases?limit=200", signal)); }
  async listRuns(caseId: string, signal?: AbortSignal): Promise<InvestigationRunListResponse> { if (!RESOURCE_ID.test(caseId)) throw new TypeError("caseId 无效"); return parseInvestigationRunList(await this.get(`/v1/ecommerce/investigations/cases/${encodeURIComponent(caseId)}/runs?limit=200`, signal), caseId); }
  async getRunView(runId: string, signal?: AbortSignal): Promise<InvestigationWorkbenchView> { if (!RESOURCE_ID.test(runId)) throw new TypeError("runId 无效"); return parseInvestigationWorkbenchView(await this.get(`/v1/ecommerce/investigations/runs/${encodeURIComponent(runId)}/view`, signal), runId); }
}

export const ecommerceInvestigationClient = new EcommerceInvestigationClient();
