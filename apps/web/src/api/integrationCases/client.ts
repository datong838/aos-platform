import { isOffline } from "../../lib/offlineStore";
import { getApiBase } from "../apiBase";
import { getDesktopClientVersion } from "../desktopClient";
import { tenantAuthHeaders } from "../tenant";
import {
  IntegrationCaseClientError,
  type IntegrationCaseApiErrorBody,
} from "./errors";
import type { IntegrationCaseIdempotencyKey } from "./idempotency";
import {
  INTEGRATION_CASE_HEADER_CONTRACT,
  INTEGRATION_CASE_OPERATIONS,
  type IntegrationCaseOperationSpec,
} from "./operations";
import {
  parseCreateIntegrationCaseRequest,
  parseCreateIntegrationEvidenceSnapshotRequest,
  parseIntegrationCaseDetail,
  parseIntegrationCaseList,
  parseIntegrationCaseTimeline,
  parseIntegrationEvidenceSnapshot,
} from "./parsers";
import type {
  CreateIntegrationCaseRequest,
  IntegrationCaseDetail,
  IntegrationCaseListResponse,
  IntegrationCaseScope,
  IntegrationCaseTimelineResponse,
  IntegrationEvidenceSnapshotResponse,
} from "./types";

type FetchImplementation = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

export interface IntegrationCaseClientOptions {
  fetch?: FetchImplementation;
  getBaseUrl?: () => string;
  getAuthHeaders?: () => Record<string, string>;
}

export interface IntegrationCaseCommandOptions {
  idempotencyKey: IntegrationCaseIdempotencyKey;
}

export interface IntegrationCaseSnapshotOptions extends IntegrationCaseCommandOptions {
  etagVersion: number;
}

export interface IntegrationCaseListQuery {
  scope: IntegrationCaseScope;
  limit?: number;
  offset?: number;
}

export interface IntegrationCaseTimelineQuery {
  limit?: number;
  offset?: number;
}

const MAX_LIST_LIMIT = 100;
const MAX_LIST_OFFSET = 10_000;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

function canonicalUuid(value: string, label: string): string {
  if (typeof value !== "string" || !UUID.test(value)) {
    throw new TypeError(`${label} must be a canonical lowercase UUID`);
  }
  return value;
}

function positiveInteger(value: number, label: string): number {
  if (!Number.isSafeInteger(value) || value < 1) throw new TypeError(`${label} must be a positive safe integer`);
  return value;
}

function nonNegativeInteger(value: number, label: string): number {
  if (!Number.isSafeInteger(value) || value < 0) throw new TypeError(`${label} must be a non-negative safe integer`);
  return value;
}

function paging(query: { limit?: number; offset?: number }): URLSearchParams {
  const params = new URLSearchParams();
  if (query.limit !== undefined) {
    const limit = positiveInteger(query.limit, "limit");
    if (limit > MAX_LIST_LIMIT) throw new TypeError(`limit must be <= ${MAX_LIST_LIMIT}`);
    params.set("limit", String(limit));
  }
  if (query.offset !== undefined) {
    const offset = nonNegativeInteger(query.offset, "offset");
    if (offset > MAX_LIST_OFFSET) throw new TypeError(`offset must be <= ${MAX_LIST_OFFSET}`);
    params.set("offset", String(offset));
  }
  return params;
}

function fillCasePath(operation: IntegrationCaseOperationSpec, caseId: string): string {
  const encoded = encodeURIComponent(canonicalUuid(caseId, "caseId"));
  return operation.pathTemplate.replace("{case_id}", encoded);
}

function validateIdempotencyKey(value: IntegrationCaseIdempotencyKey): string {
  const contract = INTEGRATION_CASE_HEADER_CONTRACT.idempotencyKey;
  if (
    typeof value !== "string" || value.length < contract.minLength || value.length > contract.maxLength ||
    value !== value.trim() || /[\u0000-\u001f\u007f]/.test(value)
  ) {
    throw new TypeError("idempotencyKey violates the canonical header contract");
  }
  return value;
}

function strongEtag(etagVersion: number): string {
  const value = `"${positiveInteger(etagVersion, "etagVersion")}"`;
  if (!new RegExp(INTEGRATION_CASE_HEADER_CONTRACT.ifMatch.pattern).test(value)) {
    throw new TypeError("etagVersion cannot be represented as a strong ETag");
  }
  return value;
}

function apiErrorBody(value: unknown, fallback: string): IntegrationCaseApiErrorBody {
  if (typeof value === "object" && value !== null && !Array.isArray(value)) {
    const body = value as Partial<IntegrationCaseApiErrorBody>;
    if (typeof body.code === "string" && typeof body.message === "string" && typeof body.traceId === "string") {
      return { code: body.code, message: body.message, traceId: body.traceId, details: body.details ?? null };
    }
  }
  return { code: "INVALID_ERROR_RESPONSE", message: fallback, traceId: "", details: null };
}

export class IntegrationCaseClient {
  private readonly fetchOverride?: FetchImplementation;
  private readonly baseUrl: () => string;
  private readonly authHeaders: () => Record<string, string>;

  constructor(options: IntegrationCaseClientOptions = {}) {
    this.fetchOverride = options.fetch;
    this.baseUrl = options.getBaseUrl ?? getApiBase;
    this.authHeaders = options.getAuthHeaders ?? tenantAuthHeaders;
  }

  private fetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
    const implementation = this.fetchOverride ?? globalThis.fetch.bind(globalThis);
    return implementation(input, init);
  }

  private headers(command?: { idempotencyKey?: string; ifMatch?: string }): Headers {
    const headers = new Headers(this.authHeaders());
    headers.set("Accept", "application/json");
    headers.set("Content-Type", "application/json");
    const desktopVersion = getDesktopClientVersion();
    if (desktopVersion) headers.set("X-AOS-Desktop-Version", desktopVersion);
    if (command?.idempotencyKey) headers.set(INTEGRATION_CASE_HEADER_CONTRACT.idempotencyKey.name, command.idempotencyKey);
    if (command?.ifMatch) headers.set(INTEGRATION_CASE_HEADER_CONTRACT.ifMatch.name, command.ifMatch);
    return headers;
  }

  private fail(
    operationId: string,
    mutation: boolean,
    status: number,
    body: IntegrationCaseApiErrorBody,
  ): never {
    throw new IntegrationCaseClientError(body.message, { status, body, operationId, mutation });
  }

  private malformed(operationId: string, mutation: boolean, message: string): never {
    this.fail(operationId, mutation, 0, { code: "INVALID_SUCCESS_RESPONSE", message, details: null, traceId: "" });
  }

  private async request(
    operation: IntegrationCaseOperationSpec,
    path: string,
    init: RequestInit,
  ): Promise<{ payload: unknown; response: Response }> {
    const mutation = operation.method === "POST";
    let response: Response;
    try {
      response = await this.fetch(`${this.baseUrl().replace(/\/$/, "")}${path}`, init);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : String(cause);
      this.fail(operation.operationId, mutation, 0, { code: "NETWORK", message, details: null, traceId: "" });
    }
    const payload: unknown = await response.json().catch(() => undefined);
    if (!response.ok) {
      this.fail(
        operation.operationId,
        mutation,
        response.status,
        apiErrorBody(payload, response.statusText || `HTTP ${response.status}`),
      );
    }
    if (payload === undefined) this.malformed(operation.operationId, mutation, "canonical API returned non-JSON success");
    return { payload, response };
  }

  private assertEtag(
    operation: IntegrationCaseOperationSpec,
    response: Response,
    etagVersion: number,
  ): void {
    const expected = strongEtag(etagVersion);
    if (response.headers.get(INTEGRATION_CASE_HEADER_CONTRACT.etag.name) !== expected) {
      this.malformed(operation.operationId, operation.method === "POST", "response ETag does not match body etagVersion");
    }
  }

  private get(operation: IntegrationCaseOperationSpec, path: string) {
    return this.request(operation, path, { method: "GET", headers: this.headers() });
  }

  private post(
    operation: IntegrationCaseOperationSpec,
    path: string,
    body: unknown,
    options: IntegrationCaseCommandOptions,
    etagVersion?: number,
  ) {
    if (isOffline()) {
      this.fail(operation.operationId, true, 0, {
        code: "OFFLINE_MUTATION_DISABLED",
        message: "integration case mutations are disabled while offline",
        details: null,
        traceId: "",
      });
    }
    const idempotencyKey = validateIdempotencyKey(options.idempotencyKey);
    const ifMatch = etagVersion === undefined ? undefined : strongEtag(etagVersion);
    return this.request(operation, path, {
      method: "POST",
      headers: this.headers({ idempotencyKey, ifMatch }),
      body: JSON.stringify(body),
    });
  }

  async listCases(query: IntegrationCaseListQuery): Promise<IntegrationCaseListResponse> {
    if (query.scope !== "current" && query.scope !== "reference") throw new TypeError("scope must be current or reference");
    const operation = INTEGRATION_CASE_OPERATIONS.listCases;
    const params = paging(query);
    params.set("scope", query.scope);
    const { payload } = await this.get(operation, `${operation.pathTemplate}?${params.toString()}`);
    try {
      const parsed = parseIntegrationCaseList(payload);
      if (parsed.scope !== query.scope) this.malformed(operation.operationId, false, "list response scope does not match requested scope");
      return parsed;
    } catch (error) {
      if (error instanceof IntegrationCaseClientError) throw error;
      return this.malformed(operation.operationId, false, error instanceof Error ? error.message : "invalid list response");
    }
  }

  async createCase(
    body: CreateIntegrationCaseRequest,
    options: IntegrationCaseCommandOptions,
  ): Promise<IntegrationCaseDetail> {
    const operation = INTEGRATION_CASE_OPERATIONS.createCase;
    const requestBody = parseCreateIntegrationCaseRequest(body);
    const { payload, response } = await this.post(operation, operation.pathTemplate, requestBody, options);
    try {
      const parsed = parseIntegrationCaseDetail(payload);
      if (parsed.scope !== "current") this.malformed(operation.operationId, true, "create response must be a current case");
      this.assertEtag(operation, response, parsed.etagVersion);
      return parsed;
    } catch (error) {
      if (error instanceof IntegrationCaseClientError) throw error;
      return this.malformed(operation.operationId, true, error instanceof Error ? error.message : "invalid create response");
    }
  }

  async getCase(caseId: string): Promise<IntegrationCaseDetail> {
    const operation = INTEGRATION_CASE_OPERATIONS.getCase;
    const { payload, response } = await this.get(operation, fillCasePath(operation, caseId));
    try {
      const parsed = parseIntegrationCaseDetail(payload);
      if (parsed.caseId !== caseId) this.malformed(operation.operationId, false, "detail response caseId does not match request");
      this.assertEtag(operation, response, parsed.etagVersion);
      return parsed;
    } catch (error) {
      if (error instanceof IntegrationCaseClientError) throw error;
      return this.malformed(operation.operationId, false, error instanceof Error ? error.message : "invalid detail response");
    }
  }

  async createEvidenceSnapshot(
    caseId: string,
    options: IntegrationCaseSnapshotOptions,
  ): Promise<IntegrationEvidenceSnapshotResponse> {
    const operation = INTEGRATION_CASE_OPERATIONS.createSnapshot;
    const path = fillCasePath(operation, caseId);
    const body = parseCreateIntegrationEvidenceSnapshotRequest({});
    const { payload, response } = await this.post(operation, path, body, options, options.etagVersion);
    try {
      const parsed = parseIntegrationEvidenceSnapshot(payload);
      if (parsed.caseId !== caseId) this.malformed(operation.operationId, true, "snapshot response caseId does not match request");
      this.assertEtag(operation, response, parsed.etagVersion);
      return parsed;
    } catch (error) {
      if (error instanceof IntegrationCaseClientError) throw error;
      return this.malformed(operation.operationId, true, error instanceof Error ? error.message : "invalid snapshot response");
    }
  }

  async listTimeline(
    caseId: string,
    query: IntegrationCaseTimelineQuery = {},
  ): Promise<IntegrationCaseTimelineResponse> {
    const operation = INTEGRATION_CASE_OPERATIONS.listTimeline;
    const params = paging(query);
    const suffix = params.size ? `?${params.toString()}` : "";
    const { payload } = await this.get(operation, `${fillCasePath(operation, caseId)}${suffix}`);
    try {
      const parsed = parseIntegrationCaseTimeline(payload);
      if (parsed.caseId !== caseId) this.malformed(operation.operationId, false, "timeline response caseId does not match request");
      return parsed;
    } catch (error) {
      if (error instanceof IntegrationCaseClientError) throw error;
      return this.malformed(operation.operationId, false, error instanceof Error ? error.message : "invalid timeline response");
    }
  }
}

export const integrationCaseClient = new IntegrationCaseClient();
