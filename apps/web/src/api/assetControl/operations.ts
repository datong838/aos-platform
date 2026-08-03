export type AssetControlHttpMethod = "GET" | "POST";

export type AssetControlErrorStatus =
  | 400
  | 401
  | 403
  | 404
  | 409
  | 412
  | 422
  | 428
  | 500;

export type AssetControlOperationId =
  | "resolve_bundle_composition"
  | "get_bundle_composition_lock"
  | "create_bundle_installation"
  | "list_bundle_installations"
  | "get_bundle_installation"
  | "submit_bundle_installation"
  | "approve_bundle_installation"
  | "reject_bundle_installation"
  | "apply_bundle_installation"
  | "verify_bundle_installation"
  | "rollback_bundle_installation";

export type AssetControlOperationSpec = Readonly<{
  method: AssetControlHttpMethod;
  pathTemplate: string;
  operationId: AssetControlOperationId;
  requiresIdempotencyKey: boolean;
  requiresIfMatch: boolean;
  returnsEtag: boolean;
  errorStatuses: readonly AssetControlErrorStatus[];
}>;

const BASE_ERRORS = [400, 401, 403, 404, 422, 500] as const;
const COMMAND_ERRORS = [400, 401, 403, 404, 409, 422, 500] as const;
const ACTION_ERRORS = [400, 401, 403, 404, 409, 412, 422, 428, 500] as const;

/**
 * Frozen M2-B HTTP surface consumed by M3.
 *
 * This is a contract inventory, not an authorization or client-side state
 * machine. The server remains authoritative for every transition and error.
 */
export const ASSET_CONTROL_OPERATIONS = {
  resolveComposition: {
    method: "POST",
    pathTemplate: "/v1/bundle-compositions:resolve",
    operationId: "resolve_bundle_composition",
    requiresIdempotencyKey: true,
    requiresIfMatch: false,
    returnsEtag: false,
    errorStatuses: COMMAND_ERRORS,
  },
  getCompositionLock: {
    method: "GET",
    pathTemplate: "/v1/bundle-compositions/{composition_id}/locks/{revision}",
    operationId: "get_bundle_composition_lock",
    requiresIdempotencyKey: false,
    requiresIfMatch: false,
    returnsEtag: false,
    errorStatuses: COMMAND_ERRORS,
  },
  createInstallation: {
    method: "POST",
    pathTemplate: "/v1/bundle-installations",
    operationId: "create_bundle_installation",
    requiresIdempotencyKey: true,
    requiresIfMatch: false,
    returnsEtag: true,
    errorStatuses: COMMAND_ERRORS,
  },
  listInstallations: {
    method: "GET",
    pathTemplate: "/v1/bundle-installations",
    operationId: "list_bundle_installations",
    requiresIdempotencyKey: false,
    requiresIfMatch: false,
    returnsEtag: false,
    errorStatuses: BASE_ERRORS,
  },
  getInstallation: {
    method: "GET",
    pathTemplate: "/v1/bundle-installations/{installation_id}",
    operationId: "get_bundle_installation",
    requiresIdempotencyKey: false,
    requiresIfMatch: false,
    returnsEtag: true,
    errorStatuses: BASE_ERRORS,
  },
  submitInstallation: {
    method: "POST",
    pathTemplate: "/v1/bundle-installations/{installation_id}/submit",
    operationId: "submit_bundle_installation",
    requiresIdempotencyKey: true,
    requiresIfMatch: true,
    returnsEtag: true,
    errorStatuses: ACTION_ERRORS,
  },
  approveInstallation: {
    method: "POST",
    pathTemplate: "/v1/bundle-installations/{installation_id}/approve",
    operationId: "approve_bundle_installation",
    requiresIdempotencyKey: true,
    requiresIfMatch: true,
    returnsEtag: true,
    errorStatuses: ACTION_ERRORS,
  },
  rejectInstallation: {
    method: "POST",
    pathTemplate: "/v1/bundle-installations/{installation_id}/reject",
    operationId: "reject_bundle_installation",
    requiresIdempotencyKey: true,
    requiresIfMatch: true,
    returnsEtag: true,
    errorStatuses: ACTION_ERRORS,
  },
  applyInstallation: {
    method: "POST",
    pathTemplate: "/v1/bundle-installations/{installation_id}/apply",
    operationId: "apply_bundle_installation",
    requiresIdempotencyKey: true,
    requiresIfMatch: true,
    returnsEtag: true,
    errorStatuses: ACTION_ERRORS,
  },
  verifyInstallation: {
    method: "POST",
    pathTemplate: "/v1/bundle-installations/{installation_id}/verify",
    operationId: "verify_bundle_installation",
    requiresIdempotencyKey: true,
    requiresIfMatch: true,
    returnsEtag: true,
    errorStatuses: ACTION_ERRORS,
  },
  rollbackInstallation: {
    method: "POST",
    pathTemplate: "/v1/bundle-installations/{installation_id}/rollback",
    operationId: "rollback_bundle_installation",
    requiresIdempotencyKey: true,
    requiresIfMatch: true,
    returnsEtag: true,
    errorStatuses: ACTION_ERRORS,
  },
} as const satisfies Record<string, AssetControlOperationSpec>;

export const ASSET_CONTROL_HEADER_CONTRACT = {
  idempotencyKey: {
    name: "Idempotency-Key",
    minLength: 1,
    maxLength: 160,
  },
  ifMatch: {
    name: "If-Match",
    pattern: '^"[1-9][0-9]*"$',
  },
  etag: {
    name: "ETag",
    pattern: '^"[1-9][0-9]*"$',
  },
} as const;

export const ASSET_CONTROL_ERROR_STATUS_MEANINGS = {
  400: "invalid_request",
  401: "unauthenticated",
  403: "forbidden",
  404: "not_visible_or_missing",
  409: "state_or_idempotency_conflict",
  412: "etag_precondition_failed",
  422: "validation_or_resolution_limit",
  428: "if_match_required",
  500: "server_error",
} as const satisfies Record<AssetControlErrorStatus, string>;
