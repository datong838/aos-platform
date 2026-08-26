import { getApiBase } from "../apiBase";
import { tenantAuthHeaders } from "../tenant";
import type { InvestigationCaseListResponse, InvestigationCommandClient, InvestigationControlCommand, InvestigationDataCommandResult, InvestigationMissingDataInput, InvestigationRunCommandResult, InvestigationRunListResponse, InvestigationStageReviewProjection, InvestigationStageReviewResult, InvestigationWorkbenchView } from "./contracts";
import { parseInvestigationCaseList, parseInvestigationDataCommandResponse, parseInvestigationRunList, parseInvestigationRunStateCommandResponse, parseInvestigationStageReviewProjection, parseInvestigationStageReviewResponse, parseInvestigationWorkbenchView } from "./parser";

type FetchImplementation = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;
export type EcommerceInvestigationClientOptions = { fetch?: FetchImplementation; getBaseUrl?: () => string; getAuthHeaders?: () => Record<string, string> };
export class EcommerceInvestigationClientError extends Error {
  constructor(message: string, readonly status: number, readonly code: string) { super(message); this.name = "EcommerceInvestigationClientError"; }
}
const RESOURCE_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,199}$/;

export class EcommerceInvestigationClient implements InvestigationCommandClient {
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
  async getStageReview(runId: string, signal?: AbortSignal): Promise<InvestigationStageReviewProjection> { if (!RESOURCE_ID.test(runId)) throw new TypeError("runId 无效"); return parseInvestigationStageReviewProjection(await this.get(`/v1/ecommerce/investigations/runs/${encodeURIComponent(runId)}/stage-review`, signal), runId); }
  async executeRunCommand(input: { runId: string; command: InvestigationControlCommand; commandId: string; expectedStateVersion: number }, signal?: AbortSignal): Promise<InvestigationRunCommandResult> {
    if (!RESOURCE_ID.test(input.runId)) throw new TypeError("runId 无效");
    if (!RESOURCE_ID.test(input.commandId)) throw new TypeError("commandId 无效");
    if (!Number.isInteger(input.expectedStateVersion) || input.expectedStateVersion < 1) throw new TypeError("expectedStateVersion 无效");
    const operation = { PAUSE_RUN: "pause", RESUME_RUN: "resume", CANCEL_RUN: "cancel" }[input.command];
    if (!operation) throw new TypeError("command 无效");
    let response: Response;
    try {
      response = await this.fetchImpl(`${this.baseUrl().replace(/\/$/, "")}/v1/ecommerce/investigations/runs/${encodeURIComponent(input.runId)}:${operation}`, {
        method: "POST",
        headers: { ...this.authHeaders(), Accept: "application/json", "Content-Type": "application/json", "Idempotency-Key": input.commandId, "If-Match": `"${input.expectedStateVersion}"` },
        body: "{}",
        signal,
      });
    } catch (cause) {
      throw new EcommerceInvestigationClientError(cause instanceof Error ? cause.message : String(cause), 0, "COMMAND_OUTCOME_UNKNOWN");
    }
    const payload: unknown = await response.json().catch(() => undefined);
    if (!response.ok) {
      const raw = typeof payload === "object" && payload !== null ? payload as Record<string, unknown> : {};
      throw new EcommerceInvestigationClientError(typeof raw.message === "string" ? raw.message : response.statusText || `HTTP ${response.status}`, response.status, typeof raw.code === "string" ? raw.code : "HTTP_ERROR");
    }
    if (payload === undefined) throw new EcommerceInvestigationClientError("canonical command returned non-JSON success", 0, "INVALID_SUCCESS_RESPONSE");
    let commandResponse;
    try { commandResponse = parseInvestigationRunStateCommandResponse(payload, input.runId); }
    catch (cause) { throw new EcommerceInvestigationClientError(cause instanceof Error ? cause.message : String(cause), 0, "INVALID_SUCCESS_RESPONSE"); }
    let view: InvestigationWorkbenchView;
    try { view = await this.getRunView(input.runId, signal); }
    catch (cause) { throw new EcommerceInvestigationClientError(cause instanceof Error ? cause.message : String(cause), 0, "COMMAND_OUTCOME_UNKNOWN"); }
    if (view.tenant.orgId !== commandResponse.tenant.orgId || view.tenant.projectId !== commandResponse.tenant.projectId || view.stateRef.revision !== commandResponse.authority.version || view.stateRef.contentHash !== commandResponse.authority.contentHash) {
      throw new EcommerceInvestigationClientError("command readback did not converge to exact authority", 409, "COMMAND_READBACK_CONFLICT");
    }
    return { commandId: input.commandId, command: input.command, replayed: commandResponse.replayed, authority: commandResponse.authority, view };
  }

  async requestMissingData(input: { runId: string; commandId: string; expectedStateVersion: number; body: InvestigationMissingDataInput }, signal?: AbortSignal): Promise<InvestigationDataCommandResult> {
    return this.executeDataCommand({ ...input, command: "REQUEST_DATA", operation: "request-missing-data", body: input.body }, signal);
  }

  async confirmDataRequirement(input: { runId: string; commandId: string; expectedStateVersion: number; decision: "accept" | "reject"; reason?: string }, signal?: AbortSignal): Promise<InvestigationDataCommandResult> {
    if (input.decision === "reject" && (!input.reason?.trim() || input.reason !== input.reason.trim() || input.reason.length > 500)) throw new TypeError("reason 无效");
    if (input.decision === "accept" && input.reason !== undefined) throw new TypeError("accept 不接受 reason");
    return this.executeDataCommand({ ...input, command: "CONFIRM_DATA_REQUIREMENT", operation: "confirm-data-requirement", body: input.decision === "reject" ? { decision: input.decision, reason: input.reason } : { decision: input.decision } }, signal);
  }

  private async executeDataCommand(input: { runId: string; commandId: string; expectedStateVersion: number; command: "REQUEST_DATA" | "CONFIRM_DATA_REQUIREMENT"; operation: string; body: unknown }, signal?: AbortSignal): Promise<InvestigationDataCommandResult> {
    if (!RESOURCE_ID.test(input.runId) || !RESOURCE_ID.test(input.commandId)) throw new TypeError("data command identity 无效");
    if (!Number.isInteger(input.expectedStateVersion) || input.expectedStateVersion < 1) throw new TypeError("expectedStateVersion 无效");
    let response: Response;
    try {
      response = await this.fetchImpl(`${this.baseUrl().replace(/\/$/, "")}/v1/ecommerce/investigations/runs/${encodeURIComponent(input.runId)}:${input.operation}`, {
        method: "POST",
        headers: { ...this.authHeaders(), Accept: "application/json", "Content-Type": "application/json", "Idempotency-Key": input.commandId, "If-Match": `"${input.expectedStateVersion}"` },
        body: JSON.stringify(input.body),
        signal,
      });
    } catch (cause) {
      throw new EcommerceInvestigationClientError(cause instanceof Error ? cause.message : String(cause), 0, "COMMAND_OUTCOME_UNKNOWN");
    }
    const payload: unknown = await response.json().catch(() => undefined);
    if (!response.ok) {
      const raw = typeof payload === "object" && payload !== null ? payload as Record<string, unknown> : {};
      throw new EcommerceInvestigationClientError(typeof raw.message === "string" ? raw.message : response.statusText || `HTTP ${response.status}`, response.status, typeof raw.code === "string" ? raw.code : "HTTP_ERROR");
    }
    if (payload === undefined) throw new EcommerceInvestigationClientError("canonical data command returned non-JSON success", 0, "INVALID_SUCCESS_RESPONSE");
    let commandResponse;
    try { commandResponse = parseInvestigationDataCommandResponse(payload, input.runId); }
    catch (cause) { throw new EcommerceInvestigationClientError(cause instanceof Error ? cause.message : String(cause), 0, "INVALID_SUCCESS_RESPONSE"); }
    let view: InvestigationWorkbenchView;
    try { view = await this.getRunView(input.runId, signal); }
    catch (cause) { throw new EcommerceInvestigationClientError(cause instanceof Error ? cause.message : String(cause), 0, "COMMAND_OUTCOME_UNKNOWN"); }
    if (view.tenant.orgId !== commandResponse.tenant.orgId || view.tenant.projectId !== commandResponse.tenant.projectId || view.stateRef.revision !== commandResponse.runAuthority.version || view.stateRef.contentHash !== commandResponse.runAuthority.contentHash || JSON.stringify(view.pendingRequirementRef) !== JSON.stringify(commandResponse.requirementRef)) {
      throw new EcommerceInvestigationClientError("data command readback did not converge to exact authority", 409, "COMMAND_READBACK_CONFLICT");
    }
    return { commandId: input.commandId, command: input.command, response: commandResponse, view };
  }

  async reviewStage(input: { runId: string; commandId: string; expectedStateVersion: number; decision: "accept" | "return"; issueId: string; expectedIssueVersion: number; reason: string }, signal?: AbortSignal): Promise<InvestigationStageReviewResult> {
    if (!RESOURCE_ID.test(input.runId) || !RESOURCE_ID.test(input.commandId) || !RESOURCE_ID.test(input.issueId)) throw new TypeError("review command identity 无效");
    if (!Number.isInteger(input.expectedStateVersion) || input.expectedStateVersion < 1 || !Number.isInteger(input.expectedIssueVersion) || input.expectedIssueVersion < 1) throw new TypeError("review command version 无效");
    if (!input.reason.trim() || input.reason !== input.reason.trim() || input.reason.length > 2000) throw new TypeError("review reason 无效");
    let response: Response;
    try {
      response = await this.fetchImpl(`${this.baseUrl().replace(/\/$/, "")}/v1/ecommerce/investigations/runs/${encodeURIComponent(input.runId)}:review-stage`, {
        method: "POST",
        headers: { ...this.authHeaders(), Accept: "application/json", "Content-Type": "application/json", "Idempotency-Key": input.commandId, "If-Match": `"${input.expectedStateVersion}"` },
        body: JSON.stringify({ decision: input.decision, issueId: input.issueId, expectedIssueVersion: input.expectedIssueVersion, reason: input.reason }),
        signal,
      });
    } catch (cause) {
      throw new EcommerceInvestigationClientError(cause instanceof Error ? cause.message : String(cause), 0, "COMMAND_OUTCOME_UNKNOWN");
    }
    const payload: unknown = await response.json().catch(() => undefined);
    if (!response.ok) { const raw = typeof payload === "object" && payload !== null ? payload as Record<string, unknown> : {}; throw new EcommerceInvestigationClientError(typeof raw.message === "string" ? raw.message : response.statusText || `HTTP ${response.status}`, response.status, typeof raw.code === "string" ? raw.code : "HTTP_ERROR"); }
    if (payload === undefined) throw new EcommerceInvestigationClientError("canonical review command returned non-JSON success", 0, "INVALID_SUCCESS_RESPONSE");
    let commandResponse;
    try { commandResponse = parseInvestigationStageReviewResponse(payload); }
    catch (cause) { throw new EcommerceInvestigationClientError(cause instanceof Error ? cause.message : String(cause), 0, "INVALID_SUCCESS_RESPONSE"); }
    let projection: InvestigationStageReviewProjection;
    try { projection = await this.getStageReview(input.runId, signal); }
    catch (cause) { throw new EcommerceInvestigationClientError(cause instanceof Error ? cause.message : String(cause), 0, "COMMAND_OUTCOME_UNKNOWN"); }
    const readback = projection.items.find((item) => item.issue.issueId === commandResponse.issue.issueId)?.issue;
    const expectedStatus = input.decision === "accept" ? "resolved" : "returned";
    if (!readback || readback.version !== commandResponse.issue.version || readback.status !== expectedStatus || readback.tenant.orgId !== commandResponse.tenant.orgId || readback.tenant.projectId !== commandResponse.tenant.projectId) throw new EcommerceInvestigationClientError("review command readback did not converge to canonical issue", 409, "COMMAND_READBACK_CONFLICT");
    return { commandId: input.commandId, response: commandResponse, projection };
  }
}

export const ecommerceInvestigationClient = new EcommerceInvestigationClient();
