import type {
  JsonValue,
  RuntimeAction,
  RuntimeBinding,
  RuntimeInstallation,
  RuntimeOperation,
  RuntimeOperationAccepted,
  RuntimeOperationEvent,
  RuntimeOperationRequest,
  RuntimeUiSession,
} from "./types";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const ACTIONS = new Set<RuntimeAction>(["runtime-apply", "runtime-verify", "configure", "enable", "disable"]);

function object(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(`${label} must be an object`);
  return value as Record<string, unknown>;
}
function keys(value: Record<string, unknown>, required: readonly string[], label: string) {
  const wanted = new Set(required);
  const missing = required.filter((key) => !(key in value));
  const extra = Object.keys(value).filter((key) => !wanted.has(key));
  if (missing.length || extra.length) throw new Error(`${label} keys mismatch; missing=${missing.join(",")}; extra=${extra.join(",")}`);
}
function text(value: unknown, label: string): asserts value is string {
  if (typeof value !== "string" || !value || value !== value.trim() || value.includes("\0")) throw new Error(`${label} must be normalized text`);
}
function uuid(value: unknown, label: string): asserts value is string { text(value, label); if (!UUID.test(value)) throw new Error(`${label} must be a canonical UUID`); }
function integer(value: unknown, label: string): asserts value is number { if (!Number.isSafeInteger(value) || Number(value) < 1) throw new Error(`${label} must be a positive integer`); }
function nullableInteger(value: unknown, label: string) { if (value !== null) integer(value, label); }
function timestamp(value: unknown, label: string): asserts value is string { text(value, label); if (!value.includes("T") || Number.isNaN(Date.parse(value))) throw new Error(`${label} must be an ISO timestamp`); }
function action(value: unknown, label: string): asserts value is RuntimeAction { if (!ACTIONS.has(value as RuntimeAction)) throw new Error(`${label} is invalid`); }
function nullableText(value: unknown, label: string) { if (value !== null) text(value, label); }

function parseEvent(value: unknown): RuntimeOperationEvent {
  const item = object(value, "Runtime event");
  keys(item, ["sequence", "type", "payloadHash", "occurredAt"], "Runtime event");
  integer(item.sequence, "Runtime event.sequence"); text(item.type, "Runtime event.type"); text(item.payloadHash, "Runtime event.payloadHash"); timestamp(item.occurredAt, "Runtime event.occurredAt");
  return item as unknown as RuntimeOperationEvent;
}

export function parseRuntimeOperation(value: unknown): RuntimeOperation {
  const item = object(value, "Runtime operation");
  keys(item, ["operationId", "installationId", "kind", "phase", "status", "revision", "requestedBy", "approvedBy", "expectedInstallationEtag", "expectedBindingRevision", "deadline", "failureCode", "createdAt", "events"], "Runtime operation");
  uuid(item.operationId, "Runtime operation.operationId"); uuid(item.installationId, "Runtime operation.installationId"); action(item.kind, "Runtime operation.kind");
  text(item.phase, "Runtime operation.phase"); text(item.status, "Runtime operation.status"); integer(item.revision, "Runtime operation.revision"); text(item.requestedBy, "Runtime operation.requestedBy"); nullableText(item.approvedBy, "Runtime operation.approvedBy"); integer(item.expectedInstallationEtag, "Runtime operation.expectedInstallationEtag"); nullableInteger(item.expectedBindingRevision, "Runtime operation.expectedBindingRevision"); timestamp(item.deadline, "Runtime operation.deadline"); nullableText(item.failureCode, "Runtime operation.failureCode"); timestamp(item.createdAt, "Runtime operation.createdAt");
  if (!Array.isArray(item.events)) throw new Error("Runtime operation.events must be an array");
  return { ...(item as unknown as RuntimeOperation), events: item.events.map(parseEvent) };
}

function parseBinding(value: unknown): RuntimeBinding | null {
  if (value === null) return null;
  const item = object(value, "Runtime binding");
  keys(item, ["generation", "installationRevision", "profileRef", "configRef", "executionEpoch", "desiredState", "observedState", "enabled", "operationFence", "revision"], "Runtime binding");
  uuid(item.generation, "Runtime binding.generation"); integer(item.installationRevision, "Runtime binding.installationRevision"); text(item.profileRef, "Runtime binding.profileRef");
  if (item.configRef !== null) object(item.configRef, "Runtime binding.configRef");
  integer(item.executionEpoch, "Runtime binding.executionEpoch"); text(item.desiredState, "Runtime binding.desiredState"); text(item.observedState, "Runtime binding.observedState");
  if (typeof item.enabled !== "boolean" || typeof item.operationFence !== "boolean") throw new Error("Runtime binding booleans are invalid");
  integer(item.revision, "Runtime binding.revision");
  return item as unknown as RuntimeBinding;
}

function stringList(value: unknown, label: string): string[] {
  if (!Array.isArray(value)) throw new Error(`${label} must be an array`);
  value.forEach((entry) => text(entry, `${label} item`));
  if (new Set(value).size !== value.length) throw new Error(`${label} must be unique`);
  return value as string[];
}

export function parseUiSession(value: unknown): RuntimeUiSession | null {
  if (value === null) return null;
  const item = object(value, "Runtime UI session");
  keys(item, ["title", "signedResourceUrl", "resourceHash", "initialRoute", "routeClaims", "readOperationClaims", "commandOperationClaims"], "Runtime UI session");
  text(item.title, "Runtime UI session.title"); text(item.signedResourceUrl, "Runtime UI session.signedResourceUrl"); text(item.initialRoute, "Runtime UI session.initialRoute"); text(item.resourceHash, "Runtime UI session.resourceHash");
  if (!/^sha256:[0-9a-f]{64}$/.test(item.resourceHash)) throw new Error("Runtime UI session.resourceHash must be canonical sha256");
  return { title: item.title, signedResourceUrl: item.signedResourceUrl, resourceHash: item.resourceHash as RuntimeUiSession["resourceHash"], initialRoute: item.initialRoute, routeClaims: stringList(item.routeClaims, "Runtime UI session.routeClaims"), readOperationClaims: stringList(item.readOperationClaims, "Runtime UI session.readOperationClaims"), commandOperationClaims: stringList(item.commandOperationClaims, "Runtime UI session.commandOperationClaims") };
}

export function parseRuntimeInstallation(value: unknown): RuntimeInstallation {
  const item = object(value, "Runtime installation");
  keys(item, ["installationId", "installationRevision", "installationEtag", "installationState", "effectiveState", "binding", "currentOperation", "ui", "allowedActions", "reasons"], "Runtime installation");
  uuid(item.installationId, "Runtime installation.installationId"); integer(item.installationRevision, "Runtime installation.installationRevision"); integer(item.installationEtag, "Runtime installation.installationEtag"); text(item.installationState, "Runtime installation.installationState"); text(item.effectiveState, "Runtime installation.effectiveState");
  if (!Array.isArray(item.allowedActions) || !Array.isArray(item.reasons)) throw new Error("Runtime installation action/reason lists are invalid");
  item.allowedActions.forEach((value) => action(value, "Runtime installation.allowedAction")); item.reasons.forEach((value) => text(value, "Runtime installation.reason"));
  return { ...(item as unknown as RuntimeInstallation), binding: parseBinding(item.binding), currentOperation: item.currentOperation === null ? null : parseRuntimeOperation(item.currentOperation), ui: parseUiSession(item.ui), allowedActions: item.allowedActions as RuntimeAction[], reasons: item.reasons as string[] };
}

export function parseRuntimeOperationAccepted(value: unknown): RuntimeOperationAccepted {
  const item = object(value, "Runtime operation receipt");
  keys(item, ["installationId", "operationId", "phase", "status", "revision"], "Runtime operation receipt");
  uuid(item.installationId, "Runtime operation receipt.installationId"); uuid(item.operationId, "Runtime operation receipt.operationId"); text(item.phase, "Runtime operation receipt.phase"); text(item.status, "Runtime operation receipt.status"); integer(item.revision, "Runtime operation receipt.revision");
  return item as unknown as RuntimeOperationAccepted;
}

export function serializeRuntimeOperationRequest(value: RuntimeOperationRequest): Record<string, JsonValue> {
  action(value.kind, "Runtime operation request.kind");
  const needsTarget = value.kind === "configure" || value.kind === "enable" || value.kind === "disable";
  if (needsTarget !== (value.target !== undefined)) throw new TypeError(needsTarget ? "runtime control requires an exact target" : "runtime preparation does not accept a target");
  return value.target === undefined ? { kind: value.kind } : { kind: value.kind, target: value.target };
}
