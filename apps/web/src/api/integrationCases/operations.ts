export type IntegrationCaseHttpMethod = "GET" | "POST";
export type IntegrationCaseErrorStatus = 400 | 401 | 403 | 404 | 409 | 422 | 428 | 500;
export type IntegrationCaseOperationId =
  | "list_integration_cases"
  | "create_integration_case"
  | "get_integration_case"
  | "create_integration_evidence_snapshot"
  | "list_integration_case_timeline";

export type IntegrationCaseOperationSpec = Readonly<{
  method: IntegrationCaseHttpMethod;
  pathTemplate: string;
  operationId: IntegrationCaseOperationId;
  requiresIdempotencyKey: boolean;
  requiresIfMatch: boolean;
  returnsEtag: boolean;
  errorStatuses: readonly IntegrationCaseErrorStatus[];
}>;

const READ_ERRORS = [400, 401, 403, 404, 422, 500] as const;
const CREATE_ERRORS = [400, 401, 403, 404, 409, 422, 500] as const;
const SNAPSHOT_ERRORS = [400, 401, 403, 404, 409, 422, 428, 500] as const;

/** Frozen M4 five-endpoint inventory. This module performs no HTTP requests. */
export const INTEGRATION_CASE_OPERATIONS = {
  listCases: {
    method: "GET", pathTemplate: "/v1/integration-cases", operationId: "list_integration_cases",
    requiresIdempotencyKey: false, requiresIfMatch: false, returnsEtag: false, errorStatuses: READ_ERRORS,
  },
  createCase: {
    method: "POST", pathTemplate: "/v1/integration-cases", operationId: "create_integration_case",
    requiresIdempotencyKey: true, requiresIfMatch: false, returnsEtag: true, errorStatuses: CREATE_ERRORS,
  },
  getCase: {
    method: "GET", pathTemplate: "/v1/integration-cases/{case_id}", operationId: "get_integration_case",
    requiresIdempotencyKey: false, requiresIfMatch: false, returnsEtag: true, errorStatuses: READ_ERRORS,
  },
  createSnapshot: {
    method: "POST", pathTemplate: "/v1/integration-cases/{case_id}/evidence-snapshots", operationId: "create_integration_evidence_snapshot",
    requiresIdempotencyKey: true, requiresIfMatch: true, returnsEtag: true, errorStatuses: SNAPSHOT_ERRORS,
  },
  listTimeline: {
    method: "GET", pathTemplate: "/v1/integration-cases/{case_id}/timeline", operationId: "list_integration_case_timeline",
    requiresIdempotencyKey: false, requiresIfMatch: false, returnsEtag: false, errorStatuses: READ_ERRORS,
  },
} as const satisfies Record<string, IntegrationCaseOperationSpec>;

export const INTEGRATION_CASE_HEADER_CONTRACT = {
  idempotencyKey: { name: "Idempotency-Key", minLength: 1, maxLength: 160 },
  ifMatch: { name: "If-Match", pattern: '^"[1-9][0-9]*"$' },
  etag: { name: "ETag", pattern: '^"[1-9][0-9]*"$' },
} as const;
