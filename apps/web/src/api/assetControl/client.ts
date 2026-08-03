import { isOffline } from "../../lib/offlineStore";
import { getApiBase } from "../apiBase";
import { getDesktopClientVersion } from "../desktopClient";
import { tenantAuthHeaders } from "../tenant";
import type { IdempotencyKey } from "./idempotency";
import { parseInstallationDetail, parseInstallationList } from "./installations";
import {
  ASSET_CONTROL_HEADER_CONTRACT,
  ASSET_CONTROL_OPERATIONS,
  type AssetControlOperationSpec,
} from "./operations";
import {
  parseRegistryBundleDetail,
  parseRegistryBundleList,
  parseRegistryVersionDetail,
  type RegistryBundleDetail,
  type RegistryBundleSummary,
  type RegistryVersionDetail,
} from "./registry";
import type {
  ApiErrorBody,
  ApproveInstallationRequest,
  CompositionRequest,
  CreateInstallationRequest,
  EmptyInstallationActionRequest,
  InstallationListResponse,
  InstallationResponse,
  InstallationState,
  RejectInstallationRequest,
  RollbackInstallationRequest,
  StoredCompositionLock,
} from "./types";

type FetchImplementation = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

export interface AssetControlClientOptions {
  fetch?: FetchImplementation;
  getBaseUrl?: () => string;
  getAuthHeaders?: () => Record<string, string>;
}

export interface IdempotentCommandOptions {
  idempotencyKey: IdempotencyKey;
}

export interface InstallationActionOptions extends IdempotentCommandOptions {
  etagVersion: number;
}

export interface InstallationListQuery {
  state?: InstallationState;
  limit?: number;
  offset?: number;
}

export class AssetControlClientError extends Error {
  readonly status: number;
  readonly body: ApiErrorBody;
  readonly operationId: string;

  constructor(
    message: string,
    options: { status: number; body: ApiErrorBody; operationId: string },
  ) {
    super(message);
    this.name = "AssetControlClientError";
    this.status = options.status;
    this.body = options.body;
    this.operationId = options.operationId;
  }
}

const REGISTRY_PATH = "/v1/asset-bundles";
const MAX_INSTALLATION_LIST_LIMIT = 100;
const MAX_INSTALLATION_LIST_OFFSET = 10_000;
const EMPTY_ACTION_BODY: EmptyInstallationActionRequest = {};

function pathSegment(value: string, label: string): string {
  if (!value || value !== value.trim()) {
    throw new TypeError(`${label} must be a non-empty normalized string`);
  }
  return encodeURIComponent(value);
}

function positiveInteger(value: number, label: string): number {
  if (!Number.isSafeInteger(value) || value < 1) {
    throw new TypeError(`${label} must be a positive safe integer`);
  }
  return value;
}

function fillPath(
  operation: AssetControlOperationSpec,
  values: Record<string, string | number>,
): string {
  return operation.pathTemplate.replace(/\{([^}]+)\}/g, (_match, key: string) => {
    const value = values[key];
    if (value === undefined) {
      throw new TypeError(`missing path parameter: ${key}`);
    }
    return typeof value === "string"
      ? pathSegment(value, key)
      : encodeURIComponent(String(value));
  });
}

function idempotencyKey(value: IdempotencyKey): IdempotencyKey {
  const contract = ASSET_CONTROL_HEADER_CONTRACT.idempotencyKey;
  if (
    typeof value !== "string" ||
    value.length < contract.minLength ||
    value.length > contract.maxLength ||
    value !== value.trim() ||
    /[\u0000-\u001f\u007f]/.test(value)
  ) {
    throw new TypeError("idempotencyKey violates the canonical header contract");
  }
  return value;
}

function offlineMutationDisabled(operationId: string): never {
  const message = "asset control mutations are disabled while offline";
  const body: ApiErrorBody = {
    code: "OFFLINE_MUTATION_DISABLED",
    message,
    details: null,
    traceId: "",
  };
  throw new AssetControlClientError(message, {
    status: 0,
    body,
    operationId,
  });
}

function strongIfMatch(etagVersion: number): string {
  const value = `"${positiveInteger(etagVersion, "etagVersion")}"`;
  if (!new RegExp(ASSET_CONTROL_HEADER_CONTRACT.ifMatch.pattern).test(value)) {
    throw new TypeError("etagVersion cannot be represented as a strong If-Match");
  }
  return value;
}

function errorBody(value: unknown, fallbackMessage: string): ApiErrorBody {
  if (typeof value === "object" && value !== null && !Array.isArray(value)) {
    const candidate = value as Partial<ApiErrorBody>;
    if (
      typeof candidate.code === "string" &&
      typeof candidate.message === "string" &&
      typeof candidate.traceId === "string"
    ) {
      return {
        code: candidate.code,
        message: candidate.message,
        details: candidate.details ?? null,
        traceId: candidate.traceId,
      };
    }
  }
  return {
    code: "INVALID_ERROR_RESPONSE",
    message: fallbackMessage,
    details: null,
    traceId: "",
  };
}

function malformedResponse(operationId: string, message: string): never {
  const body: ApiErrorBody = {
    code: "INVALID_SUCCESS_RESPONSE",
    message,
    details: null,
    traceId: "",
  };
  throw new AssetControlClientError(message, {
    status: 0,
    body,
    operationId,
  });
}

export class AssetControlClient {
  private readonly fetchOverride?: FetchImplementation;
  private readonly baseUrl: () => string;
  private readonly authHeaders: () => Record<string, string>;

  constructor(options: AssetControlClientOptions = {}) {
    this.fetchOverride = options.fetch;
    this.baseUrl = options.getBaseUrl ?? getApiBase;
    this.authHeaders = options.getAuthHeaders ?? tenantAuthHeaders;
  }

  private fetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
    const implementation = this.fetchOverride ?? globalThis.fetch.bind(globalThis);
    return implementation(input, init);
  }

  private headers(command?: {
    idempotencyKey?: string;
    ifMatch?: string;
  }): Headers {
    const headers = new Headers(this.authHeaders());
    headers.set("Accept", "application/json");
    headers.set("Content-Type", "application/json");
    const desktopVersion = getDesktopClientVersion();
    if (desktopVersion) headers.set("X-AOS-Desktop-Version", desktopVersion);
    if (command?.idempotencyKey) {
      headers.set(
        ASSET_CONTROL_HEADER_CONTRACT.idempotencyKey.name,
        command.idempotencyKey,
      );
    }
    if (command?.ifMatch) {
      headers.set(ASSET_CONTROL_HEADER_CONTRACT.ifMatch.name, command.ifMatch);
    }
    return headers;
  }

  private async request<T>(
    operationId: string,
    path: string,
    init: RequestInit,
    expectEtag = false,
  ): Promise<T> {
    let response: Response;
    try {
      response = await this.fetch(`${this.baseUrl().replace(/\/$/, "")}${path}`, init);
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : String(cause);
      const body: ApiErrorBody = {
        code: "NETWORK",
        message,
        details: null,
        traceId: "",
      };
      throw new AssetControlClientError(message, {
        status: 0,
        body,
        operationId,
      });
    }

    const payload: unknown = await response.json().catch(() => undefined);
    if (!response.ok) {
      const body = errorBody(
        payload,
        response.statusText || `HTTP ${response.status}`,
      );
      throw new AssetControlClientError(body.message, {
        status: response.status,
        body,
        operationId,
      });
    }
    if (payload === undefined) {
      malformedResponse(operationId, "canonical API returned non-JSON success");
    }
    if (expectEtag) this.assertResponseEtag(operationId, response, payload);
    return payload as T;
  }

  private async get<T>(operationId: string, path: string, expectEtag = false) {
    return this.request<T>(
      operationId,
      path,
      { method: "GET", headers: this.headers() },
      expectEtag,
    );
  }

  private async post<T>(
    operation: AssetControlOperationSpec,
    path: string,
    body: unknown,
    options: IdempotentCommandOptions,
    etagVersion?: number,
  ): Promise<T> {
    // Asset-control commands are never queued or replayed by the generic
    // offline writer. A user must explicitly retry the same command identity.
    if (isOffline()) offlineMutationDisabled(operation.operationId);
    const key = idempotencyKey(options.idempotencyKey);
    const ifMatch =
      etagVersion === undefined ? undefined : strongIfMatch(etagVersion);
    return this.request<T>(
      operation.operationId,
      path,
      {
        method: "POST",
        headers: this.headers({ idempotencyKey: key, ifMatch }),
        body: JSON.stringify(body),
      },
      operation.returnsEtag,
    );
  }

  private assertResponseEtag(
    operationId: string,
    response: Response,
    payload: unknown,
  ): void {
    if (typeof payload !== "object" || payload === null || Array.isArray(payload)) {
      malformedResponse(operationId, "installation response must be an object");
    }
    const version = (payload as { etagVersion?: unknown }).etagVersion;
    if (typeof version !== "number") {
      malformedResponse(operationId, "installation response has no etagVersion");
    }
    const expected = strongIfMatch(version);
    if (response.headers.get(ASSET_CONTROL_HEADER_CONTRACT.etag.name) !== expected) {
      malformedResponse(operationId, "installation ETag does not match etagVersion");
    }
  }

  async listRegistryBundles(): Promise<RegistryBundleSummary[]> {
    const payload = await this.get<unknown>(
      "list_asset_bundles",
      REGISTRY_PATH,
    );
    return parseRegistryBundleList(payload);
  }

  async getRegistryBundle(
    bundleId: string,
    publisher?: string,
  ): Promise<RegistryBundleDetail> {
    const query = new URLSearchParams();
    if (publisher !== undefined) query.set("publisher", publisher);
    const suffix = query.size ? `?${query.toString()}` : "";
    const payload = await this.get<unknown>(
      "get_asset_bundle",
      `${REGISTRY_PATH}/${pathSegment(bundleId, "bundleId")}${suffix}`,
    );
    return parseRegistryBundleDetail(payload);
  }

  async getRegistryBundleVersion(
    bundleId: string,
    version: string,
    publisher?: string,
  ): Promise<RegistryVersionDetail> {
    const query = new URLSearchParams();
    if (publisher !== undefined) query.set("publisher", publisher);
    const suffix = query.size ? `?${query.toString()}` : "";
    const payload = await this.get<unknown>(
      "get_asset_bundle_version",
      `${REGISTRY_PATH}/${pathSegment(bundleId, "bundleId")}/versions/${pathSegment(version, "version")}${suffix}`,
    );
    return parseRegistryVersionDetail(payload);
  }

  resolveComposition(
    body: CompositionRequest,
    options: IdempotentCommandOptions,
  ): Promise<StoredCompositionLock> {
    const operation = ASSET_CONTROL_OPERATIONS.resolveComposition;
    return this.post(operation, operation.pathTemplate, body, options);
  }

  getCompositionLock(
    compositionId: string,
    revision: number,
  ): Promise<StoredCompositionLock> {
    const operation = ASSET_CONTROL_OPERATIONS.getCompositionLock;
    const path = fillPath(operation, {
      composition_id: compositionId,
      revision: positiveInteger(revision, "revision"),
    });
    return this.get(operation.operationId, path);
  }

  createInstallation(
    body: CreateInstallationRequest,
    options: IdempotentCommandOptions,
  ): Promise<InstallationResponse> {
    const operation = ASSET_CONTROL_OPERATIONS.createInstallation;
    return this.post(operation, operation.pathTemplate, body, options);
  }

  listInstallations(
    query: InstallationListQuery = {},
  ): Promise<InstallationListResponse> {
    const operation = ASSET_CONTROL_OPERATIONS.listInstallations;
    const params = new URLSearchParams();
    if (query.state !== undefined) params.set("state", query.state);
    if (query.limit !== undefined) {
      const limit = positiveInteger(query.limit, "limit");
      if (limit > MAX_INSTALLATION_LIST_LIMIT) {
        throw new TypeError(`limit must be <= ${MAX_INSTALLATION_LIST_LIMIT}`);
      }
      params.set("limit", String(limit));
    }
    if (query.offset !== undefined) {
      if (!Number.isSafeInteger(query.offset) || query.offset < 0) {
        throw new TypeError("offset must be a non-negative safe integer");
      }
      if (query.offset > MAX_INSTALLATION_LIST_OFFSET) {
        throw new TypeError(`offset must be <= ${MAX_INSTALLATION_LIST_OFFSET}`);
      }
      params.set("offset", String(query.offset));
    }
    const suffix = params.size ? `?${params.toString()}` : "";
    return this.get<unknown>(
      operation.operationId,
      `${operation.pathTemplate}${suffix}`,
    ).then(parseInstallationList);
  }

  async getInstallation(installationId: string): Promise<InstallationResponse> {
    const operation = ASSET_CONTROL_OPERATIONS.getInstallation;
    const path = fillPath(operation, {
      installation_id: installationId,
    });
    const payload = await this.get<unknown>(
      operation.operationId,
      path,
      operation.returnsEtag,
    );
    return parseInstallationDetail(payload);
  }

  private installationAction<TBody>(
    operation: AssetControlOperationSpec,
    installationId: string,
    body: TBody,
    options: InstallationActionOptions,
  ): Promise<InstallationResponse> {
    const path = fillPath(operation, {
      installation_id: installationId,
    });
    return this.post(operation, path, body, options, options.etagVersion);
  }

  submitInstallation(
    installationId: string,
    options: InstallationActionOptions,
  ): Promise<InstallationResponse> {
    return this.installationAction(
      ASSET_CONTROL_OPERATIONS.submitInstallation,
      installationId,
      EMPTY_ACTION_BODY,
      options,
    );
  }

  approveInstallation(
    installationId: string,
    body: ApproveInstallationRequest,
    options: InstallationActionOptions,
  ): Promise<InstallationResponse> {
    return this.installationAction(
      ASSET_CONTROL_OPERATIONS.approveInstallation,
      installationId,
      body,
      options,
    );
  }

  rejectInstallation(
    installationId: string,
    body: RejectInstallationRequest,
    options: InstallationActionOptions,
  ): Promise<InstallationResponse> {
    return this.installationAction(
      ASSET_CONTROL_OPERATIONS.rejectInstallation,
      installationId,
      body,
      options,
    );
  }

  applyInstallation(
    installationId: string,
    options: InstallationActionOptions,
  ): Promise<InstallationResponse> {
    return this.installationAction(
      ASSET_CONTROL_OPERATIONS.applyInstallation,
      installationId,
      EMPTY_ACTION_BODY,
      options,
    );
  }

  verifyInstallation(
    installationId: string,
    options: InstallationActionOptions,
  ): Promise<InstallationResponse> {
    return this.installationAction(
      ASSET_CONTROL_OPERATIONS.verifyInstallation,
      installationId,
      EMPTY_ACTION_BODY,
      options,
    );
  }

  rollbackInstallation(
    installationId: string,
    body: RollbackInstallationRequest,
    options: InstallationActionOptions,
  ): Promise<InstallationResponse> {
    return this.installationAction(
      ASSET_CONTROL_OPERATIONS.rollbackInstallation,
      installationId,
      body,
      options,
    );
  }
}

export const assetControlClient = new AssetControlClient();
