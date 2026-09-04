export type OperationCaseWorkspaceTenant = { orgId: string; projectId: string };
export type OperationCaseWorkspaceRef = {
  tenant: OperationCaseWorkspaceTenant;
  resourceType: string;
  resourceId: string;
  contentHash: string;
  sourceUpdatedAt: string;
};
export type OperationCaseWorkspaceCandidate = {
  candidateId: string;
  kind: "inventory_data_gap" | "aftersale_followup";
  title: string;
  summary: string;
  priority: "normal" | "high";
  memberRefs: OperationCaseWorkspaceRef[];
  externalEffectAllowed: false;
};
export type OperationCaseWorkspaceCase = {
  caseRef: { resourceId: string; revision: number; contentHash: string };
  version: number;
  status: "open" | "paused" | "closed";
  priority: "low" | "normal" | "high" | "critical";
  memberRefs: OperationCaseWorkspaceRef[];
  memberLedger: { orders: number; orderLines: number; inventory: number; shipments: number; payments: number; aftersaleEvents: number; total: number };
};
export type OperationCaseWorkspaceResponse = {
  schemaVersion: "aos.ecommerce-workshop.operation-case-workspace/v1";
  tenant: OperationCaseWorkspaceTenant;
  status: "ready" | "partial" | "blocked";
  evaluatedAt: string;
  dataCutoff: string;
  sources: Array<{ sourceId: "orders" | "inventory" | "shipments" | "aftersaleEvents" | "payments" | "operationCases"; status: "ready" | "blocked"; count: number; blocker: null | { code: string; requiredAction: string } }>;
  cases: OperationCaseWorkspaceCase[];
  candidates: OperationCaseWorkspaceCandidate[];
  availableRefs: OperationCaseWorkspaceRef[];
  ledger: { sourceTotal: number; assigned: number; unassigned: number; candidates: number; openCases: number; pausedCases: number; closedCases: number };
  externalEffectAllowed: false;
};

const HASH = /^[0-9a-f]{64}$/;
const SOURCE_IDS = ["orders", "inventory", "shipments", "aftersaleEvents", "payments", "operationCases"] as const;

function object(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new TypeError(`${label} 必须是对象`);
  return value as Record<string, unknown>;
}
function exact(value: Record<string, unknown>, keys: readonly string[], label: string) {
  const actual = Object.keys(value).sort().join("|");
  const expected = [...keys].sort().join("|");
  if (actual !== expected) throw new TypeError(`${label} 字段漂移`);
}
function text(value: unknown, label: string, max = 500): string {
  if (typeof value !== "string" || !value.trim() || value.length > max) throw new TypeError(`${label} 无效`);
  return value;
}
function timestamp(value: unknown, label: string): string {
  const result = text(value, label, 80);
  if (!Number.isFinite(Date.parse(result))) throw new TypeError(`${label} 时间无效`);
  return result;
}
function count(value: unknown, label: string): number {
  if (!Number.isSafeInteger(value) || Number(value) < 0) throw new TypeError(`${label} 数量无效`);
  return Number(value);
}
function oneOf<T extends string>(value: unknown, values: readonly T[], label: string): T {
  if (typeof value !== "string" || !values.includes(value as T)) throw new TypeError(`${label} 枚举无效`);
  return value as T;
}
function tenant(value: unknown): OperationCaseWorkspaceTenant {
  const raw = object(value, "operationCaseWorkspace.tenant");
  exact(raw, ["orgId", "projectId"], "operationCaseWorkspace.tenant");
  return { orgId: text(raw.orgId, "tenant.orgId", 200), projectId: text(raw.projectId, "tenant.projectId", 200) };
}
function sameTenant(actual: OperationCaseWorkspaceTenant, expected: OperationCaseWorkspaceTenant, label: string) {
  if (actual.orgId !== expected.orgId || actual.projectId !== expected.projectId) throw new TypeError(`${label} tenant 漂移`);
}
function originalRef(value: unknown, expectedTenant: OperationCaseWorkspaceTenant, label: string): OperationCaseWorkspaceRef {
  const raw = object(value, label);
  exact(raw, ["tenant", "resourceType", "resourceId", "contentHash", "sourceUpdatedAt"], label);
  const refTenant = tenant(raw.tenant);
  sameTenant(refTenant, expectedTenant, label);
  const contentHash = text(raw.contentHash, `${label}.contentHash`, 64);
  if (!HASH.test(contentHash)) throw new TypeError(`${label}.contentHash 非 SHA-256`);
  return { tenant: refTenant, resourceType: text(raw.resourceType, `${label}.resourceType`, 120), resourceId: text(raw.resourceId, `${label}.resourceId`, 300), contentHash, sourceUpdatedAt: timestamp(raw.sourceUpdatedAt, `${label}.sourceUpdatedAt`) };
}

export function parseOperationCaseWorkspace(value: unknown, expectedTenant?: OperationCaseWorkspaceTenant): OperationCaseWorkspaceResponse {
  const raw = object(value, "operationCaseWorkspace");
  exact(raw, ["schemaVersion", "tenant", "status", "evaluatedAt", "dataCutoff", "sources", "cases", "candidates", "availableRefs", "ledger", "externalEffectAllowed"], "operationCaseWorkspace");
  if (raw.schemaVersion !== "aos.ecommerce-workshop.operation-case-workspace/v1" || raw.externalEffectAllowed !== false) throw new TypeError("operationCaseWorkspace 权限边界漂移");
  const scope = tenant(raw.tenant);
  if (expectedTenant) sameTenant(scope, expectedTenant, "operationCaseWorkspace");
  if (!Array.isArray(raw.sources) || !Array.isArray(raw.cases) || !Array.isArray(raw.candidates) || !Array.isArray(raw.availableRefs)) throw new TypeError("operationCaseWorkspace 列表无效");
  const sources = raw.sources.map((item, index) => {
    const source = object(item, `sources[${index}]`);
    exact(source, ["sourceId", "status", "count", "blocker"], `sources[${index}]`);
    const sourceId = oneOf(source.sourceId, SOURCE_IDS, `sources[${index}].sourceId`);
    if (sourceId !== SOURCE_IDS[index]) throw new TypeError("operationCaseWorkspace source canonical order 漂移");
    const status = oneOf(source.status, ["ready", "blocked"] as const, `sources[${index}].status`);
    let blocker: null | { code: string; requiredAction: string } = null;
    if (source.blocker !== null) {
      const blockerRaw = object(source.blocker, `sources[${index}].blocker`);
      exact(blockerRaw, ["code", "requiredAction"], `sources[${index}].blocker`);
      blocker = { code: text(blockerRaw.code, "blocker.code", 120), requiredAction: text(blockerRaw.requiredAction, "blocker.requiredAction") };
    }
    const sourceCount = count(source.count, `sources[${index}].count`);
    if ((status === "ready") !== (blocker === null) || (status === "blocked" && sourceCount !== 0)) throw new TypeError("operationCaseWorkspace source 状态漂移");
    return { sourceId, status, count: sourceCount, blocker };
  });
  const cases = raw.cases.map((item, index): OperationCaseWorkspaceCase => {
    const current = object(item, `cases[${index}]`);
    exact(current, ["caseRef", "version", "status", "priority", "memberRefs", "memberLedger"], `cases[${index}]`);
    const caseRefRaw = object(current.caseRef, `cases[${index}].caseRef`);
    exact(caseRefRaw, ["resourceId", "revision", "contentHash"], `cases[${index}].caseRef`);
    const caseHash = text(caseRefRaw.contentHash, "caseRef.contentHash", 64);
    if (!HASH.test(caseHash) || !Array.isArray(current.memberRefs)) throw new TypeError("operationCaseWorkspace case 引用无效");
    const ledgerRaw = object(current.memberLedger, `cases[${index}].memberLedger`);
    exact(ledgerRaw, ["orders", "orderLines", "inventory", "shipments", "payments", "aftersaleEvents", "total"], `cases[${index}].memberLedger`);
    const memberLedger = { orders: count(ledgerRaw.orders, "memberLedger.orders"), orderLines: count(ledgerRaw.orderLines, "memberLedger.orderLines"), inventory: count(ledgerRaw.inventory, "memberLedger.inventory"), shipments: count(ledgerRaw.shipments, "memberLedger.shipments"), payments: count(ledgerRaw.payments, "memberLedger.payments"), aftersaleEvents: count(ledgerRaw.aftersaleEvents, "memberLedger.aftersaleEvents"), total: count(ledgerRaw.total, "memberLedger.total") };
    const memberRefs = current.memberRefs.map((ref, refIndex) => originalRef(ref, scope, `cases[${index}].memberRefs[${refIndex}]`));
    if (memberLedger.total !== memberRefs.length || memberLedger.total !== memberLedger.orders + memberLedger.orderLines + memberLedger.inventory + memberLedger.shipments + memberLedger.payments + memberLedger.aftersaleEvents) throw new TypeError("operationCaseWorkspace case member ledger 漂移");
    return { caseRef: { resourceId: text(caseRefRaw.resourceId, "caseRef.resourceId", 300), revision: count(caseRefRaw.revision, "caseRef.revision"), contentHash: caseHash }, version: count(current.version, "case.version"), status: oneOf(current.status, ["open", "paused", "closed"] as const, "case.status"), priority: oneOf(current.priority, ["low", "normal", "high", "critical"] as const, "case.priority"), memberRefs, memberLedger };
  });
  const candidates = raw.candidates.map((item, index): OperationCaseWorkspaceCandidate => {
    const current = object(item, `candidates[${index}]`);
    exact(current, ["candidateId", "kind", "title", "summary", "priority", "memberRefs", "externalEffectAllowed"], `candidates[${index}]`);
    const candidateId = text(current.candidateId, "candidate.candidateId", 64);
    if (!HASH.test(candidateId) || current.externalEffectAllowed !== false || !Array.isArray(current.memberRefs) || current.memberRefs.length < 1) throw new TypeError("operationCaseWorkspace candidate 权限边界漂移");
    return { candidateId, kind: oneOf(current.kind, ["inventory_data_gap", "aftersale_followup"] as const, "candidate.kind"), title: text(current.title, "candidate.title", 120), summary: text(current.summary, "candidate.summary"), priority: oneOf(current.priority, ["normal", "high"] as const, "candidate.priority"), memberRefs: current.memberRefs.map((ref, refIndex) => originalRef(ref, scope, `candidates[${index}].memberRefs[${refIndex}]`)), externalEffectAllowed: false };
  });
  const availableRefs = raw.availableRefs.map((ref, index) => originalRef(ref, scope, `availableRefs[${index}]`));
  const ledgerRaw = object(raw.ledger, "operationCaseWorkspace.ledger");
  exact(ledgerRaw, ["sourceTotal", "assigned", "unassigned", "candidates", "openCases", "pausedCases", "closedCases"], "operationCaseWorkspace.ledger");
  const ledger = { sourceTotal: count(ledgerRaw.sourceTotal, "ledger.sourceTotal"), assigned: count(ledgerRaw.assigned, "ledger.assigned"), unassigned: count(ledgerRaw.unassigned, "ledger.unassigned"), candidates: count(ledgerRaw.candidates, "ledger.candidates"), openCases: count(ledgerRaw.openCases, "ledger.openCases"), pausedCases: count(ledgerRaw.pausedCases, "ledger.pausedCases"), closedCases: count(ledgerRaw.closedCases, "ledger.closedCases") };
  const businessSourceTotal = sources.filter((source) => source.sourceId !== "operationCases").reduce((sum, source) => sum + source.count, 0);
  if (ledger.sourceTotal !== ledger.assigned + ledger.unassigned || ledger.sourceTotal !== businessSourceTotal || ledger.unassigned !== availableRefs.length || ledger.candidates !== candidates.length || ledger.openCases !== cases.filter((item) => item.status === "open").length || ledger.pausedCases !== cases.filter((item) => item.status === "paused").length || ledger.closedCases !== cases.filter((item) => item.status === "closed").length) throw new TypeError("operationCaseWorkspace ledger 漂移");
  const blocked = sources.filter((source) => source.status === "blocked").length;
  const status = oneOf(raw.status, ["ready", "partial", "blocked"] as const, "operationCaseWorkspace.status");
  const expectedStatus = blocked === 0 ? "ready" : blocked === sources.length ? "blocked" : "partial";
  if (status !== expectedStatus) throw new TypeError("operationCaseWorkspace readiness 漂移");
  return { schemaVersion: "aos.ecommerce-workshop.operation-case-workspace/v1", tenant: scope, status, evaluatedAt: timestamp(raw.evaluatedAt, "operationCaseWorkspace.evaluatedAt"), dataCutoff: timestamp(raw.dataCutoff, "operationCaseWorkspace.dataCutoff"), sources, cases, candidates, availableRefs, ledger, externalEffectAllowed: false };
}
