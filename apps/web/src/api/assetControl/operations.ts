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
  | 500
  | 503;

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
  | "rollback_bundle_installation"
  | "uninstall_bundle_installation"
  | "withdraw_ecommerce_growth_registration"
  | "get_ecommerce_growth_withdrawal_receipt"
  | "get_ecommerce_growth_registration_status"
  | "list_bundle_runtime_configuration_sources"
  | "submit_runtime_configuration_stage"
  | "lookup_runtime_configuration_stage"
  | "get_runtime_configuration_stage"
  | "list_bundle_runtime_configurations"
  | "get_bundle_runtime_installation"
  | "get_bundle_runtime_operation"
  | "create_bundle_runtime_operation";

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
  uninstallInstallation: {
    method: "POST",
    pathTemplate: "/v1/bundle-installations/{installation_id}/uninstall",
    operationId: "uninstall_bundle_installation",
    requiresIdempotencyKey: true,
    requiresIfMatch: true,
    returnsEtag: true,
    errorStatuses: ACTION_ERRORS,
  },
  withdrawRegistration: {
    method: "POST", pathTemplate: "/v1/bundle-runtime-installations/{installation_id}/ecommerce-growth-registrations/withdrawals",
    operationId: "withdraw_ecommerce_growth_registration", requiresIdempotencyKey: true,
    requiresIfMatch: true, returnsEtag: false, errorStatuses: [...ACTION_ERRORS, 503],
  },
  readRegistrationWithdrawal: {
    method: "GET", pathTemplate: "/v1/bundle-runtime-installations/{installation_id}/ecommerce-growth-registrations/withdrawals/receipt",
    operationId: "get_ecommerce_growth_withdrawal_receipt", requiresIdempotencyKey: true,
    requiresIfMatch: false, returnsEtag: false, errorStatuses: [...COMMAND_ERRORS, 503],
  },
  getRegistrationStatus: {
    method: "GET",
    pathTemplate: "/v1/bundle-runtime-installations/{installation_id}/ecommerce-growth-registrations/status",
    operationId: "get_ecommerce_growth_registration_status",
    requiresIdempotencyKey: false,
    requiresIfMatch: false,
    returnsEtag: false,
    errorStatuses: [...COMMAND_ERRORS, 503],
  },
  getConfigurationSources: {
    method: "GET", pathTemplate: "/v1/bundle-runtime-installations/{installation_id}/configuration-sources",
    operationId: "list_bundle_runtime_configuration_sources", requiresIdempotencyKey: false,
    requiresIfMatch: false, returnsEtag: false, errorStatuses: [...COMMAND_ERRORS, 503],
  },
  stageConfiguration: {
    method: "POST", pathTemplate: "/v1/bundle-runtime-installations/configuration-requests",
    operationId: "submit_runtime_configuration_stage", requiresIdempotencyKey: true,
    requiresIfMatch: false, returnsEtag: false, errorStatuses: [...COMMAND_ERRORS, 503],
  },
  findConfigurationStage: {
    method: "GET", pathTemplate: "/v1/bundle-runtime-installations/configuration-requests/lookup",
    operationId: "lookup_runtime_configuration_stage", requiresIdempotencyKey: true,
    requiresIfMatch: false, returnsEtag: false, errorStatuses: [...COMMAND_ERRORS, 503],
  },
  getConfigurationStage: {
    method: "GET", pathTemplate: "/v1/bundle-runtime-installations/configuration-requests/{request_id}",
    operationId: "get_runtime_configuration_stage", requiresIdempotencyKey: false,
    requiresIfMatch: false, returnsEtag: false, errorStatuses: [...COMMAND_ERRORS, 503],
  },
  getRuntimeConfigurations: {
    method: "GET", pathTemplate: "/v1/bundle-runtime-installations/{installation_id}/configurations",
    operationId: "list_bundle_runtime_configurations", requiresIdempotencyKey: false,
    requiresIfMatch: false, returnsEtag: false, errorStatuses: [...BASE_ERRORS, 409, 503],
  },
  getRuntimeInstallation: {
    method: "GET",
    pathTemplate: "/v1/bundle-runtime-installations/{installation_id}",
    operationId: "get_bundle_runtime_installation",
    requiresIdempotencyKey: false,
    requiresIfMatch: false,
    returnsEtag: false,
    errorStatuses: [...BASE_ERRORS, 503],
  },
  getRuntimeOperation: {
    method: "GET",
    pathTemplate: "/v1/bundle-runtime-installations/operations/{operation_id}",
    operationId: "get_bundle_runtime_operation",
    requiresIdempotencyKey: false,
    requiresIfMatch: false,
    returnsEtag: true,
    errorStatuses: [...BASE_ERRORS, 503],
  },
  createRuntimeOperation: {
    method: "POST",
    pathTemplate: "/v1/bundle-runtime-installations/{installation_id}/operations",
    operationId: "create_bundle_runtime_operation",
    requiresIdempotencyKey: true,
    requiresIfMatch: true,
    returnsEtag: true,
    errorStatuses: [...ACTION_ERRORS, 503],
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
  503: "trust_root_unavailable",
} as const satisfies Record<AssetControlErrorStatus, string>;
