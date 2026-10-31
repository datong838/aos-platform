import type { IdempotencyKey } from "./idempotency";
import type { RegistrationReceiptRef } from "./registrationStatus";
import type { CurrentInstallationRef, RuntimeConfigurationRef } from "./types";

export interface SuccessorRegistrationCommand {
  schemaVersion: "aos.ecommerce.successor-dispatch-registration/v1";
  registration: {
    schemaVersion: "aos.ecommerce.first-dispatch-registration/v1";
    installationRef: CurrentInstallationRef;
    generation: string; bindingRevision: number; executionEpoch: number;
    configRef: RuntimeConfigurationRef; groupId: string; idempotencyKey: IdempotencyKey;
  };
  expectedGroupRevision: number;
  predecessorDetachReceiptRef: {
    resourceType: "DispatchDisableDetachReceipt"; resourceId: string; revision: 1; contentHash: string;
  };
}
export interface SuccessorPreparation {
  schemaVersion: "aos.ecommerce.successor-preparation/v1";
  tenant: { orgId: string; projectId: string }; installationId: string;
  ready: boolean; reasons: string[];
  options: { label: "接续原安装的经营任务"; command: SuccessorRegistrationCommand }[];
  executable: false;
}
function check(ok: unknown): asserts ok { if (!ok) throw new Error("业务接续材料不一致，请核对原请求"); }
function exact(value: unknown, fields: string[]) {
  check(value && typeof value === "object" && !Array.isArray(value));
  const r = value as Record<string, unknown>;
  check(Object.keys(r).length === fields.length && fields.every(k => Object.hasOwn(r, k)));
}
const uuid = (s: unknown) => typeof s === "string" && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(s);
const hash = (s: unknown) => typeof s === "string" && /^sha256:[0-9a-f]{64}$/.test(s);
const positive = (n: unknown) => Number.isSafeInteger(n) && Number(n) > 0;

/** Transport snapshot only; the original service remains the authority. */
export function serializeSuccessorRegistration(c: SuccessorRegistrationCommand): SuccessorRegistrationCommand {
  exact(c, ["schemaVersion", "registration", "expectedGroupRevision", "predecessorDetachReceiptRef"]);
  const r = c.registration;
  exact(r, ["schemaVersion", "installationRef", "generation", "bindingRevision", "executionEpoch", "configRef", "groupId", "idempotencyKey"]);
  exact(r.installationRef, ["installationId", "revision", "lockHash", "overlayRevision"]);
  exact(r.configRef, ["configurationId", "revision", "hash"]);
  exact(c.predecessorDetachReceiptRef, ["resourceType", "resourceId", "revision", "contentHash"]);
  check(c.schemaVersion === "aos.ecommerce.successor-dispatch-registration/v1" &&
    r.schemaVersion === "aos.ecommerce.first-dispatch-registration/v1" &&
    uuid(r.installationRef.installationId) && positive(r.installationRef.revision) && hash(r.installationRef.lockHash) &&
    typeof r.installationRef.overlayRevision === "string" && r.installationRef.overlayRevision.length > 0 &&
    r.installationRef.overlayRevision.length <= 160 && r.installationRef.overlayRevision.trim() === r.installationRef.overlayRevision &&
    uuid(r.generation) && positive(r.bindingRevision) && positive(r.executionEpoch) &&
    uuid(r.configRef.configurationId) && positive(r.configRef.revision) && hash(r.configRef.hash) && uuid(r.groupId) &&
    typeof r.idempotencyKey === "string" && r.idempotencyKey.length > 0 && r.idempotencyKey.length <= 160 &&
    r.idempotencyKey.trim() === r.idempotencyKey && !/[\u0000-\u001f\u007f]/.test(r.idempotencyKey) &&
    positive(c.expectedGroupRevision) && c.predecessorDetachReceiptRef.resourceType === "DispatchDisableDetachReceipt" &&
    uuid(c.predecessorDetachReceiptRef.resourceId) && c.predecessorDetachReceiptRef.revision === 1 && hash(c.predecessorDetachReceiptRef.contentHash));
  return { schemaVersion: c.schemaVersion, registration: { schemaVersion: r.schemaVersion,
    installationRef: { installationId: r.installationRef.installationId, revision: r.installationRef.revision,
      lockHash: r.installationRef.lockHash, overlayRevision: r.installationRef.overlayRevision },
    generation: r.generation, bindingRevision: r.bindingRevision, executionEpoch: r.executionEpoch,
    configRef: { configurationId: r.configRef.configurationId, revision: r.configRef.revision, hash: r.configRef.hash },
    groupId: r.groupId, idempotencyKey: r.idempotencyKey }, expectedGroupRevision: c.expectedGroupRevision,
    predecessorDetachReceiptRef: { resourceType: c.predecessorDetachReceiptRef.resourceType,
      resourceId: c.predecessorDetachReceiptRef.resourceId, revision: c.predecessorDetachReceiptRef.revision,
      contentHash: c.predecessorDetachReceiptRef.contentHash } };
}

export function parseSuccessorRegistrationReceipt(value: unknown, command: SuccessorRegistrationCommand,
  tenant: { orgId: string | null; projectId: string | null }, historical: boolean): RegistrationReceiptRef {
  check(value && typeof value === "object" && !Array.isArray(value));
  const r = value as Record<string, unknown>;
  exact(r.tenant, ["orgId", "projectId"]);
  const t = r.tenant as Record<string, unknown>, c = command.registration;
  check(tenant.orgId && tenant.projectId && t.orgId === tenant.orgId && t.projectId === tenant.projectId &&
    r.schemaVersion === "aos.ecommerce.successor-dispatch-registration-receipt/v1" && r.executable === false &&
    r.installationId === c.installationRef.installationId && r.generation === c.generation && r.groupId === c.groupId &&
    r.idempotencyKey === c.idempotencyKey && uuid(r.receiptId) && hash(r.contentHash) && hash(r.requestHash) &&
    (historical ? r.historical === true : typeof r.replayed === "boolean"));
  const observed = serializeSuccessorRegistration(r.request as SuccessorRegistrationCommand);
  check(JSON.stringify(observed) === JSON.stringify(command));
  return { resourceType: "SuccessorDispatchRegistrationReceipt", resourceId: r.receiptId as string,
    revision: 1, contentHash: r.contentHash as string };
}

export function parseSuccessorPreparation(value: unknown, installationId: string, key: IdempotencyKey,
  tenant: { orgId: string | null; projectId: string | null }): SuccessorPreparation {
  exact(value, ["schemaVersion", "tenant", "installationId", "ready", "reasons", "options", "executable"]);
  const r = value as SuccessorPreparation;
  exact(r.tenant, ["orgId", "projectId"]);
  check(tenant.orgId && tenant.projectId && r.tenant.orgId === tenant.orgId && r.tenant.projectId === tenant.projectId &&
    r.schemaVersion === "aos.ecommerce.successor-preparation/v1" && r.installationId === installationId && r.executable === false &&
    typeof r.ready === "boolean" && Array.isArray(r.options) && r.options.length <= 1 && Array.isArray(r.reasons) &&
    r.reasons.every(s => typeof s === "string" && s.length > 0 && s.length <= 500) &&
    r.ready === (r.options.length > 0) && (r.ready ? r.reasons.length === 0 : r.reasons.length > 0));
  const options = r.options.map(option => {
    exact(option, ["label", "command"]);
    const command = serializeSuccessorRegistration(option.command);
    check(option.label === "接续原安装的经营任务" && command.registration.installationRef.installationId === installationId &&
      command.registration.idempotencyKey === key);
    return { label: option.label, command };
  });
  return { schemaVersion: r.schemaVersion, tenant: { ...r.tenant }, installationId,
    ready: r.ready, reasons: [...r.reasons], options, executable: false };
}
