import { getApiBase } from "../apiBase";
import { tenantAuthHeaders } from "../tenant";
import type { ContentCampaignViewResponse, CreatorGrowthViewResponse, EcommerceWorkshopApiErrorBody, EcommerceWorkshopModuleListResponse, EcommerceWorkshopModuleReadinessResponse, OperationCommandObservationResponse, OperationCommandReadinessResponse, OperationsViewResponse, SourceReadinessEnvelope, TaskCockpitActionReceiptResponse, TaskCockpitApprovalReviewResponse, TaskCockpitCheckpointPageResponse, TaskCockpitCoreQuery, TaskCockpitCoreResponse, TaskCockpitProductionContextResponse, TaskCockpitResponsibilityHandoffResponse, TaskCockpitRunDetailQuery, TaskCockpitStepPageResponse } from "./contracts";
import { parseContentCampaignView, parseCreatorGrowthView, parseEcommerceWorkshopApiError, parseEcommerceWorkshopModuleList, parseEcommerceWorkshopModuleReadiness, parseOperationCommandObservation, parseOperationCommandReadiness, parseOperationsView, parseSourceReadinessEnvelope, parseTaskCockpitActionReceipts, parseTaskCockpitApprovalReview, parseTaskCockpitCheckpoints, parseTaskCockpitCore, parseTaskCockpitProductionContext, parseTaskCockpitResponsibilityHandoffs, parseTaskCockpitSteps } from "./parser";

type FetchImplementation = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
export type EcommerceWorkshopClientOptions = { fetch?: FetchImplementation; getBaseUrl?: () => string; getAuthHeaders?: () => Record<string, string> };
export class EcommerceWorkshopClientError extends Error {
  constructor(message: string, readonly options: { status: number; body: EcommerceWorkshopApiErrorBody; operationId: string }) { super(message); this.name = "EcommerceWorkshopClientError"; }
  get status(): number { return this.options.status; }
  get body(): EcommerceWorkshopApiErrorBody { return this.options.body; }
  get operationId(): string { return this.options.operationId; }
}
const MODULE_ID = /^ecommerce\.[a-z0-9]+(?:[.-][a-z0-9]+)*$/;
const RUN_ID = /^[^\s/\\\u0000]{1,200}$/;
const COMMAND_OBSERVATION_REF = /^[^\s/\\\u0000]{1,300}$/;
const TASK_STATUSES = new Set(["pending", "planning", "awaiting_approval", "approved", "executing", "paused", "completed", "failed", "cancelled", "rolled_back"]);
function queryString(query: TaskCockpitRunDetailQuery & { status?: string }): string {
  const parameters = new URLSearchParams();
  if (query.status !== undefined) { if (!TASK_STATUSES.has(query.status)) throw new TypeError("status 无效"); parameters.set("status", query.status); }
  if (query.limit !== undefined) { if (!Number.isSafeInteger(query.limit) || query.limit < 1 || query.limit > 100) throw new TypeError("limit 无效"); parameters.set("limit", String(query.limit)); }
  if (query.cursor !== undefined) { if (!query.cursor || query.cursor !== query.cursor.trim() || query.cursor.length > 4096 || query.cursor.includes("\u0000")) throw new TypeError("cursor 无效"); parameters.set("cursor", query.cursor); }
  const value = parameters.toString(); return value ? `?${value}` : "";
}
export class EcommerceWorkshopClient {
  private readonly fetchImpl: FetchImplementation; private readonly baseUrl: () => string; private readonly authHeaders: () => Record<string, string>;
  constructor(options: EcommerceWorkshopClientOptions = {}) { this.fetchImpl = options.fetch ?? globalThis.fetch.bind(globalThis); this.baseUrl = options.getBaseUrl ?? getApiBase; this.authHeaders = options.getAuthHeaders ?? tenantAuthHeaders; }
  private async get(operationId: string, path: string): Promise<unknown> {
    let response: Response; try { response = await this.fetchImpl(`${this.baseUrl().replace(/\/$/, "")}${path}`, { method: "GET", headers: { ...this.authHeaders(), Accept: "application/json" } }); } catch (cause) { const message = cause instanceof Error ? cause.message : String(cause); throw new EcommerceWorkshopClientError(message, { status: 0, body: { code: "NETWORK", message, details: null, traceId: "" }, operationId }); }
    const payload: unknown = await response.json().catch(() => undefined); if (!response.ok) { const body = parseEcommerceWorkshopApiError(payload, response.statusText || `HTTP ${response.status}`); throw new EcommerceWorkshopClientError(body.message, { status: response.status, body, operationId }); } if (payload === undefined) throw new EcommerceWorkshopClientError("canonical API returned non-JSON success", { status: 0, body: { code: "INVALID_SUCCESS_RESPONSE", message: "canonical API returned non-JSON success", details: null, traceId: "" }, operationId }); return payload;
  }
  async listModules(): Promise<EcommerceWorkshopModuleListResponse> { return parseEcommerceWorkshopModuleList(await this.get("ecommerceWorkshopModulesList", "/v1/ecommerce-workshop/modules")); }
  async getModuleReadiness(moduleId: string): Promise<EcommerceWorkshopModuleReadinessResponse> { if (!MODULE_ID.test(moduleId)) throw new TypeError("moduleId 无效"); return parseEcommerceWorkshopModuleReadiness(await this.get("ecommerceWorkshopModuleReadinessGet", `/v1/ecommerce-workshop/modules/${encodeURIComponent(moduleId)}/readiness`)); }
  async getSourceReadiness(): Promise<SourceReadinessEnvelope> { return parseSourceReadinessEnvelope(await this.get("ecommerceWorkshopSourceReadinessGet", "/v1/ecommerce-workshop/source-readiness")); }
  async getOperationsView(): Promise<OperationsViewResponse> { return parseOperationsView(await this.get("ecommerceWorkshopOperationsViewGet", "/v1/ecommerce-workshop/views/operations")); }
  async getContentCampaignView(): Promise<ContentCampaignViewResponse> { return parseContentCampaignView(await this.get("ecommerceWorkshopContentCampaignViewGet", "/v1/ecommerce-workshop/views/content-campaign")); }
  async getCreatorGrowthView(): Promise<CreatorGrowthViewResponse> { return parseCreatorGrowthView(await this.get("ecommerceWorkshopCreatorGrowthViewGet", "/v1/ecommerce-workshop/views/creator-growth")); }
  async getOperationCommandReadiness(): Promise<OperationCommandReadinessResponse> { return parseOperationCommandReadiness(await this.get("ecommerceWorkshopOperationCommandReadinessGet", "/v1/ecommerce-workshop/commands/operations/readiness")); }
  async getOperationCommandObservation(proposalId: string, leaseId: string): Promise<OperationCommandObservationResponse> { if (!COMMAND_OBSERVATION_REF.test(proposalId) || !COMMAND_OBSERVATION_REF.test(leaseId)) throw new TypeError("operation command observation ref 无效"); return parseOperationCommandObservation(await this.get("ecommerceWorkshopOperationCommandObservationGet", `/v1/ecommerce-workshop/commands/operations/observations/${encodeURIComponent(proposalId)}/leases/${encodeURIComponent(leaseId)}`), undefined, proposalId, leaseId); }
  async getTaskCockpitCore(query: TaskCockpitCoreQuery = {}): Promise<TaskCockpitCoreResponse> { return parseTaskCockpitCore(await this.get("ecommerceWorkshopTaskCockpitCoreGet", `/v1/ecommerce-workshop/views/task-cockpit${queryString(query)}`)); }
  async listTaskCockpitRunSteps(runId: string, query: TaskCockpitRunDetailQuery = {}): Promise<TaskCockpitStepPageResponse> { if (!RUN_ID.test(runId)) throw new TypeError("runId 无效"); return parseTaskCockpitSteps(await this.get("ecommerceWorkshopTaskCockpitRunStepsList", `/v1/ecommerce-workshop/views/task-cockpit/runs/${encodeURIComponent(runId)}/steps${queryString(query)}`)); }
  async listTaskCockpitRunCheckpoints(runId: string, query: TaskCockpitRunDetailQuery = {}): Promise<TaskCockpitCheckpointPageResponse> { if (!RUN_ID.test(runId)) throw new TypeError("runId 无效"); return parseTaskCockpitCheckpoints(await this.get("ecommerceWorkshopTaskCockpitRunCheckpointsList", `/v1/ecommerce-workshop/views/task-cockpit/runs/${encodeURIComponent(runId)}/checkpoints${queryString(query)}`)); }
  async getTaskCockpitRunProductionContext(runId: string): Promise<TaskCockpitProductionContextResponse> { if (!RUN_ID.test(runId)) throw new TypeError("runId 无效"); return parseTaskCockpitProductionContext(await this.get("ecommerceWorkshopTaskCockpitRunProductionContextGet", `/v1/ecommerce-workshop/views/task-cockpit/runs/${encodeURIComponent(runId)}/production-context`)); }
  async getTaskCockpitRunResponsibilityHandoffs(runId: string): Promise<TaskCockpitResponsibilityHandoffResponse> { if (!RUN_ID.test(runId)) throw new TypeError("runId 无效"); return parseTaskCockpitResponsibilityHandoffs(await this.get("ecommerceWorkshopTaskCockpitRunResponsibilityHandoffsGet", `/v1/ecommerce-workshop/views/task-cockpit/runs/${encodeURIComponent(runId)}/responsibility-handoffs`)); }
  async getTaskCockpitRunApprovalReview(runId: string): Promise<TaskCockpitApprovalReviewResponse> { if (!RUN_ID.test(runId)) throw new TypeError("runId 无效"); return parseTaskCockpitApprovalReview(await this.get("ecommerceWorkshopTaskCockpitRunApprovalReviewIssuesGet", `/v1/ecommerce-workshop/views/task-cockpit/runs/${encodeURIComponent(runId)}/approval-review-issues`)); }
  async getTaskCockpitRunActionReceipts(runId: string): Promise<TaskCockpitActionReceiptResponse> { if (!RUN_ID.test(runId)) throw new TypeError("runId 无效"); return parseTaskCockpitActionReceipts(await this.get("ecommerceWorkshopTaskCockpitRunActionReceiptsGet", `/v1/ecommerce-workshop/views/task-cockpit/runs/${encodeURIComponent(runId)}/action-receipts`)); }
}
export const ecommerceWorkshopClient = new EcommerceWorkshopClient();
