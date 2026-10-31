import { apiGetAuthoritative, apiPostUnqueued } from './client';
import { getTenant, getAuthRevision } from './tenant';
import { getApiBase } from './apiBase';

type Tenant = { orgId: 'org-org'; projectId: 'dev-project' };
type OwnerMetadata = { tenant: Tenant; contentHash: string; createdBy: string; createdAt: string };
type AssetRef = { assetType: string; assetId: string; revision: number; contentHash: string };
type Window = 'expired' | 'effective' | 'not-yet-effective';
type Lifecycle = 'draft' | 'active' | 'suspended' | 'revoked' | 'expired';
export type RenewalBudget = OwnerMetadata & {
  budgetId: string; revision: number; environment: 'development'; currency: 'CNY';
  dailyLimitMinor: number; monthlyLimitMinor: number; alertThresholdPct: number;
  hardStop: true; unknownUsageBehavior: 'block'; effectiveFrom: string; effectiveUntil: string;
  owner: string; overBudgetApprover: string; lifecycle: Lifecycle;
};
type CostAuthorization = { tenant: Tenant; provider: AssetRef; providerModelId: string;
  approvalRef: string; environment: 'development'; effectiveFrom: string; effectiveUntil: string };
export type RenewalPolicy = OwnerMetadata & {
  policyId: string; revision: number; environment: 'development'; effectiveFrom: string;
  effectiveUntil: string; owner: string; approvalRef: string; lifecycle: Lifecycle | 'blocked';
  budgetRevisionRef: AssetRef; currency: 'CNY'; hardStop: true; unknownUsageBehavior: 'block';
  unknownPriceBehavior: 'block'; allowZeroPrice: boolean; zeroPriceApprovalRef: string | null;
  developmentCostAuthorization?: CostAuthorization;
};
export type RenewalProvider = OwnerMetadata & {
  providerInstanceId: string; revision: number; pluginRef: AssetRef;
  endpointProfile: { baseUrl: string; region: string; timeoutMs: number; metadata: Record<string, string> };
  secretRef: string; secretVersion: string; egressPolicyRef: AssetRef;
  dataClassificationPolicyRef: AssetRef; lifecycle: Exclude<Lifecycle, 'expired'> | 'validated';
};
export type RenewalSource = {
  schemaVersion: 'aos.budget-policy-renewal.review-source/v1'; tenant: Tenant; evaluatedAt: string;
  sourcePolicy: RenewalPolicy; sourceHeadVersion: number;
  sourceBudget: RenewalBudget | null; currentBudget: RenewalBudget | null;
  sourceProvider: RenewalProvider | null; currentProvider: RenewalProvider | null;
  sourceWindow: Window; budgetWindow: Window | 'unknown'; state: 'ready' | 'blocked';
  blockers: string[]; approvalVerified: false; activationEligible: false;
};

function requireValue(ok: unknown): asserts ok {
  if (!ok) throw new Error('预算续期只读来源不完整或不一致，请重新核对');
}
function row(value: unknown): Record<string, unknown> {
  requireValue(value !== null && typeof value === 'object' && !Array.isArray(value));
  return value as Record<string, unknown>;
}
function exact(value: Record<string, unknown>, fields: string[], optional: string[] = []) {
  requireValue(fields.every(k => Object.hasOwn(value, k)) &&
    Object.keys(value).every(k => fields.includes(k) || optional.includes(k)));
}
function text(value: unknown, max = 200): value is string {
  return typeof value === 'string' && value.length > 0 && value.length <= max &&
    value.trim() === value && !/[\u0000-\u001f\u007f]/.test(value);
}
function identifier(value: unknown, max = 200): value is string {
  return text(value, max) && /^[A-Za-z0-9][A-Za-z0-9._:-]*$/.test(value);
}
function positive(value: unknown): value is number { return Number.isSafeInteger(value) && Number(value) > 0; }
function hash(value: unknown): value is string { return typeof value === 'string' && /^[0-9a-f]{64}$/.test(value); }
function oneOf(value: unknown, allowed: readonly string[]): value is string {
  return typeof value === 'string' && allowed.includes(value);
}

// Compare the server's aware instants at its microsecond precision, without
// consulting the workstation clock or rounding an expiry boundary to a ms.
function instant(value: unknown): bigint {
  requireValue(typeof value === 'string');
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(Z|[+-]\d{2}:\d{2})$/.exec(value);
  requireValue(m);
  const [, year, month, day, hour, minute, second, fraction, zone] = m;
  requireValue(Number(year) >= 1 && Number(month) >= 1 && Number(month) <= 12 &&
    Number(day) >= 1 && Number(day) <= new Date(Date.UTC(Number(year), Number(month), 0)).getUTCDate() &&
    Number(hour) < 24 && Number(minute) < 60 && Number(second) < 60 &&
    (zone === 'Z' || (Number(zone.slice(1, 3)) < 24 && Number(zone.slice(4, 6)) < 60)));
  const whole = Date.parse(`${year}-${month}-${day}T${hour}:${minute}:${second}${zone}`);
  requireValue(Number.isFinite(whole));
  return BigInt(whole) * 1000n + BigInt((fraction ?? '').padEnd(6, '0'));
}
function period(value: Record<string, unknown>) {
  requireValue(instant(value.effectiveFrom) < instant(value.effectiveUntil));
}
function tenant(value: unknown) {
  const t = row(value); exact(t, ['orgId', 'projectId']);
  const current = getTenant();
  requireValue(t.orgId === 'org-org' && t.projectId === 'dev-project' &&
    t.orgId === current.orgId && t.projectId === current.projectId);
}
function metadata(value: Record<string, unknown>) {
  tenant(value.tenant); requireValue(hash(value.contentHash) && text(value.createdBy)); instant(value.createdAt);
}
const metadataKeys = ['tenant', 'contentHash', 'createdBy', 'createdAt'];
function ref(value: unknown, kind: string): AssetRef {
  const r = row(value); exact(r, ['assetType', 'assetId', 'revision', 'contentHash']);
  requireValue(r.assetType === kind && text(r.assetId) && positive(r.revision) && hash(r.contentHash));
  return r as AssetRef;
}
function budget(value: unknown): RenewalBudget | null {
  if (value === null) return null;
  const b = row(value); exact(b, [...metadataKeys, 'budgetId', 'revision', 'environment', 'currency',
    'dailyLimitMinor', 'monthlyLimitMinor', 'alertThresholdPct', 'hardStop', 'unknownUsageBehavior',
    'effectiveFrom', 'effectiveUntil', 'owner', 'overBudgetApprover', 'lifecycle']); metadata(b); period(b);
  requireValue(text(b.budgetId, 160) && positive(b.revision) && b.environment === 'development' && b.currency === 'CNY' &&
    positive(b.dailyLimitMinor) && positive(b.monthlyLimitMinor) && b.monthlyLimitMinor >= b.dailyLimitMinor &&
    positive(b.alertThresholdPct) && b.alertThresholdPct <= 100 && b.hardStop === true && b.unknownUsageBehavior === 'block' &&
    text(b.owner, 160) && text(b.overBudgetApprover, 160) && oneOf(b.lifecycle, ['draft', 'active', 'suspended', 'revoked', 'expired']));
  return b as RenewalBudget;
}
function policy(value: unknown): RenewalPolicy {
  const p = row(value); exact(p, [...metadataKeys, 'policyId', 'revision', 'environment', 'effectiveFrom',
    'effectiveUntil', 'owner', 'approvalRef', 'lifecycle', 'budgetRevisionRef', 'currency', 'hardStop',
    'unknownUsageBehavior', 'unknownPriceBehavior', 'allowZeroPrice', 'zeroPriceApprovalRef'], ['developmentCostAuthorization']);
  metadata(p); period(p); ref(p.budgetRevisionRef, 'BudgetRevision');
  requireValue(identifier(p.policyId) && positive(p.revision) && p.environment === 'development' &&
    text(p.owner, 160) && text(p.approvalRef, 240) && p.currency === 'CNY' && p.hardStop === true &&
    p.unknownUsageBehavior === 'block' && p.unknownPriceBehavior === 'block' && typeof p.allowZeroPrice === 'boolean' &&
    oneOf(p.lifecycle, ['draft', 'blocked', 'active', 'suspended', 'revoked', 'expired']) &&
    (p.allowZeroPrice ? text(p.zeroPriceApprovalRef, 240) : p.zeroPriceApprovalRef === null));
  if (Object.hasOwn(p, 'developmentCostAuthorization')) {
    const a = row(p.developmentCostAuthorization); exact(a, ['tenant', 'provider', 'providerModelId', 'approvalRef',
      'environment', 'effectiveFrom', 'effectiveUntil']); tenant(a.tenant); period(a); ref(a.provider, 'ProviderInstanceRevision');
    requireValue(text(a.providerModelId, 240) && a.approvalRef === p.approvalRef && a.environment === 'development' &&
      p.allowZeroPrice === false && instant(a.effectiveFrom) <= instant(p.effectiveFrom) && instant(a.effectiveUntil) >= instant(p.effectiveUntil));
  }
  return p as RenewalPolicy;
}
function provider(value: unknown): RenewalProvider | null {
  if (value === null) return null;
  const p = row(value); exact(p, [...metadataKeys, 'providerInstanceId', 'revision', 'pluginRef', 'endpointProfile',
    'secretRef', 'secretVersion', 'egressPolicyRef', 'dataClassificationPolicyRef', 'lifecycle']); metadata(p);
  ref(p.pluginRef, 'ProviderPluginRevision'); ref(p.egressPolicyRef, 'EgressPolicyRevision');
  ref(p.dataClassificationPolicyRef, 'DataClassificationPolicyRevision');
  const e = row(p.endpointProfile); exact(e, ['baseUrl', 'region', 'timeoutMs', 'metadata']);
  const attributes = row(e.metadata);
  requireValue(text(e.baseUrl, 1024) && text(e.region, 120) && positive(e.timeoutMs) && e.timeoutMs >= 100 && e.timeoutMs <= 3600000 &&
    Object.keys(attributes).length <= 32 && Object.values(attributes).every(v => typeof v === 'string') &&
    text(p.providerInstanceId) && positive(p.revision) && text(p.secretRef, 512) &&
    /^(vault|secret|keychain):\/\//.test(p.secretRef) && text(p.secretVersion, 120) &&
    oneOf(p.lifecycle, ['draft', 'validated', 'active', 'suspended', 'revoked']));
  return p as RenewalProvider;
}
function windowAt(value: { effectiveFrom: string; effectiveUntil: string }, now: bigint): Window {
  return now < instant(value.effectiveFrom) ? 'not-yet-effective' : now < instant(value.effectiveUntil) ? 'effective' : 'expired';
}
function matches(value: RenewalBudget | RenewalProvider | null, expected: AssetRef) {
  return value !== null && value.revision === expected.revision && value.contentHash === expected.contentHash &&
    ('budgetId' in value ? value.budgetId : value.providerInstanceId) === expected.assetId;
}
export function parseRenewalSource(value: unknown, policyId: string): RenewalSource {
  requireValue(identifier(policyId));
  const s = row(value); exact(s, ['schemaVersion', 'tenant', 'evaluatedAt', 'sourcePolicy', 'sourceHeadVersion',
    'sourceBudget', 'currentBudget', 'sourceProvider', 'currentProvider', 'sourceWindow', 'budgetWindow',
    'state', 'blockers', 'approvalVerified', 'activationEligible']); tenant(s.tenant);
  const now = instant(s.evaluatedAt), p = policy(s.sourcePolicy), b = budget(s.sourceBudget), current = budget(s.currentBudget);
  const v = provider(s.sourceProvider), currentProvider = provider(s.currentProvider);
  requireValue(s.schemaVersion === 'aos.budget-policy-renewal.review-source/v1' && p.policyId === policyId &&
    positive(s.sourceHeadVersion) && s.approvalVerified === false && s.activationEligible === false &&
    s.sourceWindow === windowAt(p, now) && s.budgetWindow === (b ? windowAt(b, now) : 'unknown') &&
    Array.isArray(s.blockers) && s.blockers.every(v => typeof v === 'string' && /^[A-Z][A-Z0-9_]{1,159}$/.test(v)) &&
    ((s.state === 'blocked' && s.blockers.length > 0) || (s.state === 'ready' && s.blockers.length === 0)));
  if (!p.developmentCostAuthorization) requireValue(v === null && currentProvider === null);
  if (s.state === 'ready') {
    requireValue(p.lifecycle === 'active' && b?.lifecycle === 'active' && current?.lifecycle === 'active' &&
      s.budgetWindow === 'effective' && matches(b, p.budgetRevisionRef) && matches(current, p.budgetRevisionRef) &&
      p.developmentCostAuthorization && v?.lifecycle === 'active' && currentProvider?.lifecycle === 'active' &&
      matches(v, p.developmentCostAuthorization.provider) && matches(currentProvider, p.developmentCostAuthorization.provider));
  }
  // Preserve all typed Owner facts, including blocked drift. No hash is
  // recomputed here, and even a ready observation still has both false flags.
  return s as RenewalSource;
}
export async function readRenewalSource(policyId: string): Promise<RenewalSource> {
  requireValue(identifier(policyId));
  const current = getTenant();
  requireValue(current.orgId === 'org-org' && current.projectId === 'dev-project');
  return readChecked('/v1/aip/model-governance-policies/budgets/' + encodeURIComponent(policyId) + '/renewal-source',
    value => parseRenewalSource(value, policyId));
}

export type RenewalOperation = 'propose' | 'decide' | 'revoke' | 'consume';
type CommandBase = { schemaVersion: 1; orgId: 'org-org'; projectId: 'dev-project'; idempotencyKey: string };
export type RenewalProposalCommand = CommandBase & { sourcePolicyId: string; expectedSourceRevision: number;
  expectedHeadVersion: number; expectedSourceHash: string; effectiveFrom: string; effectiveUntil: string };
export type RenewalDecisionCommand = CommandBase & { proposalId: string; proposalHash: string;
  targetActiveHash: string; decision: 'approved' | 'rejected' };
export type RenewalConsumeCommand = CommandBase & { proposalId: string; proposalHash: string;
  decisionId: string; decisionHash: string };
export type RenewalRevocationCommand = RenewalConsumeCommand & {
  reasonCode: 'approval_withdrawn' | 'scope_changed' | 'dependency_changed' };
export type RenewalCommand = RenewalProposalCommand | RenewalDecisionCommand | RenewalConsumeCommand | RenewalRevocationCommand;
export type RenewalTarget = Omit<RenewalPolicy, keyof OwnerMetadata | 'lifecycle'> & { lifecycle: 'draft' | 'active' };
export type RenewalPreparedProposal = {
  schemaVersion: 1; tenant: Tenant; makerSubject: string; checkerSubject: string;
  sourceRef: AssetRef; sourceHeadVersion: number; budgetRef: AssetRef; providerRef: AssetRef;
  sourcePolicy: RenewalPolicy; sourceBudget: RenewalBudget; sourceProvider: RenewalProvider;
  targetDraft: RenewalTarget; targetActive: RenewalTarget; approvalSlot: string;
  contract: { schemaVersion: 1; tenant: Tenant; sourcePolicy: RenewalPolicy; targetPolicy: RenewalTarget;
    expectedHeadVersion: number; makerSubject: string; checkerSubject: string };
  contractHash: string; request: RenewalProposalCommand; requestHash: string;
};
type ReceiptBase = { requestHash: string; activationEligible: false };
export type RenewalPreparedReceipt = ReceiptBase & { operation: 'propose'; status: 'prepared' | 'observed';
  proposalId: string; proposalHash: string; targetActiveHash: string; targetDraft: RenewalTarget; proposal: RenewalPreparedProposal };
export type RenewalDecisionPayload = { proposalId: string; proposalHash: string; targetActiveHash: string;
  actorSubject: string; decision: 'approved' | 'rejected' | 'revoked'; command: RenewalDecisionCommand | RenewalRevocationCommand;
  issuerReceiptId: string; expiresAt: string; originalDecisionId?: string; originalDecisionHash?: string;
  reasonCode?: RenewalRevocationCommand['reasonCode'] };
export type RenewalDecisionReceipt = ReceiptBase & { operation: 'decide' | 'revoke'; status: 'decided' | 'revoked' | 'observed';
  proposalId: string; proposalHash: string; decisionId: string; decisionHash: string;
  targetActiveHash: string; actorSubject: string; decisionPayload: RenewalDecisionPayload };
export type RenewalPublicationReceipt = ReceiptBase & { operation: 'consume'; status: 'observed';
  proposalId: string; proposalHash: string; decisionId: string; decisionHash: string; command: RenewalConsumeCommand;
  policy: RenewalPolicy; ref: AssetRef; actorSubject: string; headVersionBefore: number; headVersionAfter: number };
export type RenewalIncompleteReceipt = ReceiptBase & { operation: RenewalOperation; status: 'unresolved' | 'conflict' | 'blocked' };
export type RenewalReceipt = RenewalPreparedReceipt | RenewalDecisionReceipt | RenewalPublicationReceipt | RenewalIncompleteReceipt;
export type RenewalOperationResult = { schemaVersion: 'aos.budget-policy-renewal.gateway-operation/v1';
  operation: RenewalOperation; idempotencyKey: string; requestHash: string; activationEligible: false; approvalVerified: false;
  state: 'unknown' | RenewalReceipt['status']; receipt: RenewalReceipt | null; recoveryPath: string };
export type RenewalStatus = { schemaVersion: 'aos.budget-policy-renewal.gateway-status/v1'; tenant: Tenant;
  writerEnabled: boolean; state: 'configured' | 'closed'; approvalVerified: false; activationEligible: false };
export type RenewalChain = { schemaVersion: 'aos.budget-policy-renewal.gateway-chain/v1'; proposalId: string;
  decisionIdempotencyKey: string; consumeIdempotencyKey: string; decision: RenewalOperationResult | null;
  publication: RenewalOperationResult | null; state: 'unknown' | 'decision-not-attempted' | 'publication-not-attempted' | 'published';
  approvalVerified: false; activationEligible: false; recoveryPath: string };
export type RenewalHistory = { schemaVersion: 'aos.budget-policy-renewal.gateway-history/v1';
  items: RenewalOperationResult[]; nextPage: number | null; approvalVerified: false; activationEligible: false };

const renewalPrefix = '/v1/aip/budget-policy-renewal';
const checkerSubject = '6f31cfdc-a26c-4f1f-ad6b-95a8559cc657';
const makerSubject = 'postgres-service:aos_budget_renewal_maker_call';
const consumerSubject = 'postgres-service:aos_budget_renewal_consumer_call';
const baseCommandKeys = ['schemaVersion', 'orgId', 'projectId', 'idempotencyKey'];
function operation(value: unknown): asserts value is RenewalOperation {
  requireValue(oneOf(value, ['propose', 'decide', 'revoke', 'consume']));
}
// Structural display/linkage comparison only, never a second canonical hash authority.
function same(left: unknown, right: unknown): boolean {
  if (left === right) return true;
  if (left === null || right === null || typeof left !== 'object' || typeof right !== 'object') return false;
  if (Array.isArray(left) !== Array.isArray(right)) return false;
  const l = left as Record<string, unknown>, r = right as Record<string, unknown>;
  const keys = Object.keys(l);
  return keys.length === Object.keys(r).length && keys.every(k => Object.hasOwn(r, k) && same(l[k], r[k]));
}
function sameCommand(op: RenewalOperation, actual: unknown, expected: RenewalCommand): boolean {
  const a = parseRenewalCommand(op, actual), b = parseRenewalCommand(op, expected);
  if (op !== 'propose') return same(a, b);
  const p = a as RenewalProposalCommand, q = b as RenewalProposalCommand;
  return instant(p.effectiveFrom) === instant(q.effectiveFrom) && instant(p.effectiveUntil) === instant(q.effectiveUntil) &&
    same({ ...p, effectiveFrom: '', effectiveUntil: '' }, { ...q, effectiveFrom: '', effectiveUntil: '' });
}
function currentScope() { const t = getTenant(); tenant({ orgId: t.orgId, projectId: t.projectId }); }
function nonauthorizing(value: Record<string, unknown>) {
  currentScope(); requireValue(value.approvalVerified === false && value.activationEligible === false);
}
export function parseRenewalCommand(op: RenewalOperation, value: unknown): RenewalCommand {
  operation(op); currentScope(); const c = row(value);
  requireValue(c.schemaVersion === 1 && c.orgId === 'org-org' && c.projectId === 'dev-project' && identifier(c.idempotencyKey, 120));
  if (op === 'propose') {
    exact(c, [...baseCommandKeys, 'sourcePolicyId', 'expectedSourceRevision', 'expectedHeadVersion', 'expectedSourceHash', 'effectiveFrom', 'effectiveUntil']);
    requireValue(identifier(c.sourcePolicyId) && positive(c.expectedSourceRevision) && positive(c.expectedHeadVersion) && hash(c.expectedSourceHash));
    period(c);
  } else {
    exact(c, [...baseCommandKeys, 'proposalId', 'proposalHash', ...(op === 'decide'
      ? ['targetActiveHash', 'decision'] : ['decisionId', 'decisionHash', ...(op === 'revoke' ? ['reasonCode'] : [])])]);
    requireValue(identifier(c.proposalId, 160) && hash(c.proposalHash));
    if (op === 'decide') requireValue(hash(c.targetActiveHash) && oneOf(c.decision, ['approved', 'rejected']));
    else requireValue(identifier(c.decisionId, 160) && hash(c.decisionHash));
    if (op === 'revoke') requireValue(oneOf(c.reasonCode, ['approval_withdrawn', 'scope_changed', 'dependency_changed']));
  }
  // Detach the submitted command from mutable form objects before the await.
  return structuredClone(c) as RenewalCommand;
}
function parsePrepared(value: Record<string, unknown>, key: string): RenewalPreparedReceipt {
  exact(value, ['operation', 'status', 'requestHash', 'proposalId', 'proposalHash', 'targetActiveHash', 'targetDraft', 'proposal', 'activationEligible']);
  requireValue(value.operation === 'propose' && oneOf(value.status, ['prepared', 'observed']) && hash(value.requestHash) &&
    value.activationEligible === false && identifier(value.proposalId, 160) && hash(value.proposalHash) && hash(value.targetActiveHash));
  const p = row(value.proposal);
  exact(p, ['schemaVersion', 'tenant', 'makerSubject', 'checkerSubject', 'sourceRef', 'sourceHeadVersion', 'budgetRef', 'providerRef',
    'sourcePolicy', 'sourceBudget', 'sourceProvider', 'targetDraft', 'targetActive', 'approvalSlot', 'contract', 'contractHash', 'request', 'requestHash']);
  tenant(p.tenant);
  const source = policy(p.sourcePolicy), b = budget(p.sourceBudget), v = provider(p.sourceProvider);
  const request = parseRenewalCommand('propose', p.request) as RenewalProposalCommand;
  const sourceRef = ref(p.sourceRef, 'BudgetPolicyRevision'); ref(p.budgetRef, 'BudgetRevision'); ref(p.providerRef, 'ProviderInstanceRevision');
  requireValue(p.schemaVersion === 1 && p.makerSubject === makerSubject && p.checkerSubject === checkerSubject &&
    positive(p.sourceHeadVersion) && hash(p.contractHash) && p.requestHash === value.requestHash &&
    request.idempotencyKey === key && request.sourcePolicyId === source.policyId && request.expectedSourceRevision === source.revision &&
    request.expectedHeadVersion === p.sourceHeadVersion && request.expectedSourceHash === source.contentHash &&
    sourceRef.assetId === source.policyId && sourceRef.revision === source.revision && sourceRef.contentHash === source.contentHash &&
    source.lifecycle === 'active' && b?.lifecycle === 'active' && v?.lifecycle === 'active' &&
    matches(b, source.budgetRevisionRef) && same(p.budgetRef, source.budgetRevisionRef) && source.developmentCostAuthorization &&
    same(p.providerRef, source.developmentCostAuthorization.provider) && matches(v, source.developmentCostAuthorization.provider) &&
    text(p.approvalSlot, 240) && p.approvalSlot !== source.approvalRef && source.allowZeroPrice === false &&
    instant(request.effectiveFrom) >= instant(source.effectiveUntil) && instant(request.effectiveFrom) >= instant(b.effectiveFrom) &&
    instant(request.effectiveUntil) <= instant(b.effectiveUntil) && positive(source.revision + 1));
  const body = Object.fromEntries(Object.entries(source).filter(([k]) => !metadataKeys.includes(k)));
  const active = { ...body, revision: source.revision + 1, effectiveFrom: request.effectiveFrom, effectiveUntil: request.effectiveUntil,
    approvalRef: p.approvalSlot, lifecycle: 'active', developmentCostAuthorization: { ...source.developmentCostAuthorization,
      effectiveFrom: request.effectiveFrom, effectiveUntil: request.effectiveUntil, approvalRef: p.approvalSlot } };
  const draft = { ...active, lifecycle: 'draft' };
  requireValue(same(p.targetActive, active) && same(p.targetDraft, draft) && same(value.targetDraft, draft));
  const contract = row(p.contract);
  exact(contract, ['schemaVersion', 'tenant', 'sourcePolicy', 'targetPolicy', 'expectedHeadVersion', 'makerSubject', 'checkerSubject']);
  requireValue(contract.schemaVersion === 1 && same(contract.tenant, p.tenant) && same(contract.sourcePolicy, source) &&
    same(contract.targetPolicy, draft) && contract.expectedHeadVersion === p.sourceHeadVersion &&
    contract.makerSubject === makerSubject && contract.checkerSubject === checkerSubject);
  return value as RenewalPreparedReceipt;
}
function parseDecision(value: Record<string, unknown>, op: 'decide' | 'revoke', key: string): RenewalDecisionReceipt {
  exact(value, ['operation', 'status', 'requestHash', 'proposalId', 'proposalHash', 'decisionId', 'decisionHash',
    'decisionPayload', 'targetActiveHash', 'actorSubject', 'activationEligible']);
  requireValue(value.operation === op && oneOf(value.status, op === 'decide' ? ['decided', 'observed'] : ['revoked', 'observed']) &&
    hash(value.requestHash) && value.activationEligible === false && identifier(value.proposalId, 160) && hash(value.proposalHash) && identifier(value.decisionId, 160) &&
    hash(value.decisionHash) && hash(value.targetActiveHash) && value.actorSubject === checkerSubject);
  const p = row(value.decisionPayload);
  exact(p, ['proposalId', 'proposalHash', 'targetActiveHash', 'actorSubject', 'decision', 'command', 'issuerReceiptId', 'expiresAt',
    ...(op === 'revoke' ? ['originalDecisionId', 'originalDecisionHash', 'reasonCode'] : [])]);
  const c = parseRenewalCommand(op, p.command);
  instant(p.expiresAt);
  requireValue(c.idempotencyKey === key && 'proposalId' in c && p.proposalId === c.proposalId && p.proposalHash === c.proposalHash &&
    value.proposalId === p.proposalId && value.proposalHash === p.proposalHash && value.targetActiveHash === p.targetActiveHash &&
    p.actorSubject === checkerSubject && identifier(p.issuerReceiptId, 160));
  if (op === 'decide') requireValue('decision' in c && p.decision === c.decision && p.targetActiveHash === c.targetActiveHash);
  else requireValue('reasonCode' in c && p.decision === 'revoked' && p.reasonCode === c.reasonCode &&
    p.originalDecisionId === c.decisionId && p.originalDecisionHash === c.decisionHash);
  return value as RenewalDecisionReceipt;
}
function parsePublication(value: Record<string, unknown>, key: string): RenewalPublicationReceipt {
  exact(value, ['operation', 'status', 'requestHash', 'proposalId', 'proposalHash', 'decisionId', 'decisionHash', 'command',
    'policy', 'ref', 'actorSubject', 'headVersionBefore', 'headVersionAfter', 'activationEligible']);
  const c = parseRenewalCommand('consume', value.command) as RenewalConsumeCommand;
  const p = policy(value.policy), r = ref(value.ref, 'BudgetPolicyRevision');
  requireValue(value.operation === 'consume' && value.status === 'observed' && hash(value.requestHash) && value.activationEligible === false &&
    c.idempotencyKey === key && c.proposalId === value.proposalId && c.proposalHash === value.proposalHash &&
    c.decisionId === value.decisionId && c.decisionHash === value.decisionHash && value.actorSubject === consumerSubject &&
    p.createdBy === consumerSubject && p.lifecycle === 'active' && p.allowZeroPrice === false && p.developmentCostAuthorization &&
    r.assetId === p.policyId && r.revision === p.revision && r.contentHash === p.contentHash &&
    positive(value.headVersionBefore) && positive(value.headVersionAfter) && value.headVersionAfter === Number(value.headVersionBefore) + 1);
  return value as RenewalPublicationReceipt;
}
export function parseRenewalOperation(value: unknown, op: RenewalOperation, key: string, expected?: RenewalCommand): RenewalOperationResult {
  operation(op); requireValue(identifier(key, 120)); const v = row(value);
  exact(v, ['schemaVersion', 'operation', 'idempotencyKey', 'requestHash', 'activationEligible', 'approvalVerified', 'state', 'receipt', 'recoveryPath']);
  nonauthorizing(v);
  requireValue(v.schemaVersion === 'aos.budget-policy-renewal.gateway-operation/v1' && v.operation === op &&
    v.idempotencyKey === key && hash(v.requestHash) && v.recoveryPath === `${renewalPrefix}/requests/${op}/${key}`);
  if (v.state === 'unknown') requireValue(v.receipt === null);
  else {
    const r = row(v.receipt);
    requireValue(r.operation === op && r.status === v.state && r.requestHash === v.requestHash && r.activationEligible === false);
    if (['unresolved', 'conflict', 'blocked'].includes(String(v.state))) exact(r, ['operation', 'status', 'requestHash', 'activationEligible']);
    else if (op === 'propose' && ['prepared', 'observed'].includes(String(v.state))) parsePrepared(r, key);
    else if (op === 'decide' && ['decided', 'observed'].includes(String(v.state))) parseDecision(r, op, key);
    else if (op === 'revoke' && ['revoked', 'observed'].includes(String(v.state))) parseDecision(r, op, key);
    else if (op === 'consume' && v.state === 'observed') parsePublication(r, key);
    else requireValue(false);
    if (expected && 'proposal' in r) requireValue(sameCommand(op, row(r.proposal).request, expected));
    else if (expected && 'decisionPayload' in r) requireValue(sameCommand(op, row(r.decisionPayload).command, expected));
    else if (expected && 'command' in r) requireValue(sameCommand(op, r.command, expected));
  }
  if (expected) requireValue(parseRenewalCommand(op, expected).idempotencyKey === key);
  return v as RenewalOperationResult;
}
export function parseRenewalStatus(value: unknown): RenewalStatus {
  const v = row(value); exact(v, ['schemaVersion', 'tenant', 'writerEnabled', 'state', 'approvalVerified', 'activationEligible']);
  tenant(v.tenant); nonauthorizing(v);
  requireValue(v.schemaVersion === 'aos.budget-policy-renewal.gateway-status/v1' && typeof v.writerEnabled === 'boolean' &&
    v.state === (v.writerEnabled ? 'configured' : 'closed'));
  return v as RenewalStatus;
}
export function parseRenewalChain(value: unknown, proposalId: string): RenewalChain {
  requireValue(identifier(proposalId, 160)); const v = row(value);
  exact(v, ['schemaVersion', 'proposalId', 'decisionIdempotencyKey', 'consumeIdempotencyKey', 'decision', 'publication', 'state',
    'approvalVerified', 'activationEligible', 'recoveryPath']); nonauthorizing(v);
  requireValue(v.schemaVersion === 'aos.budget-policy-renewal.gateway-chain/v1' && v.proposalId === proposalId &&
    identifier(v.decisionIdempotencyKey, 120) && identifier(v.consumeIdempotencyKey, 120) && v.decisionIdempotencyKey !== v.consumeIdempotencyKey &&
    v.recoveryPath === `${renewalPrefix}/chains/${proposalId}`);
  const d = v.decision === null ? null : parseRenewalOperation(v.decision, 'decide', v.decisionIdempotencyKey);
  const p = v.publication === null ? null : parseRenewalOperation(v.publication, 'consume', v.consumeIdempotencyKey);
  const dr = d?.receipt, pr = p?.receipt;
  if (dr && 'proposalId' in dr) requireValue(dr.proposalId === proposalId);
  if (pr && 'proposalId' in pr) requireValue(pr.proposalId === proposalId);
  if (p !== null) {
    requireValue(d?.state === 'observed' && dr && 'decisionPayload' in dr && dr.decisionPayload.decision === 'approved');
    if (pr && 'decisionId' in pr) requireValue(pr.proposalHash === dr.proposalHash &&
      pr.decisionId === dr.decisionId && pr.decisionHash === dr.decisionHash);
  }
  if (v.state === 'decision-not-attempted') requireValue(d === null && p === null);
  else if (v.state === 'unknown') requireValue(d !== null && (p === null || p.state !== 'observed'));
  else if (v.state === 'publication-not-attempted' || v.state === 'published') {
    requireValue(d?.state === 'observed' && dr && 'decisionPayload' in dr && dr.decisionPayload.decision === 'approved');
    if (v.state === 'publication-not-attempted') requireValue(p === null);
    else requireValue(p?.state === 'observed' && pr && 'policy' in pr && pr.proposalHash === dr.proposalHash &&
      pr.decisionId === dr.decisionId && pr.decisionHash === dr.decisionHash);
  } else requireValue(false);
  return v as RenewalChain;
}
export function parseRenewalHistory(value: unknown): RenewalHistory {
  const v = row(value); exact(v, ['schemaVersion', 'items', 'nextPage', 'approvalVerified', 'activationEligible']); nonauthorizing(v);
  requireValue(v.schemaVersion === 'aos.budget-policy-renewal.gateway-history/v1' && Array.isArray(v.items) && v.items.length <= 5 &&
    (v.nextPage === null || (positive(v.nextPage) && v.nextPage <= 4095 && v.nextPage % 5 === 0)));
  const seen = new Set<string>();
  for (const item of v.items) {
    const r = row(item); operation(r.operation); requireValue(identifier(r.idempotencyKey, 120));
    parseRenewalOperation(r, r.operation, r.idempotencyKey);
    const locator = `${r.operation}/${r.idempotencyKey}`; requireValue(!seen.has(locator)); seen.add(locator);
  }
  return v as RenewalHistory;
}
function identitySnapshot() {
  currentScope(); const t = getTenant(); return JSON.stringify([t.orgId, t.projectId, t.subject, getAuthRevision()]);
}
async function readChecked<T>(path: string, parse: (value: unknown) => T): Promise<T> {
  const identity = identitySnapshot(), base = getApiBase();
  if (path.startsWith(renewalPrefix)) requireValue(base === '/api');
  const result = await apiGetAuthoritative(path);
  requireValue(identitySnapshot() === identity && getApiBase() === base); return parse(result);
}
async function postChecked<T>(path: string, body: unknown, parse: (value: unknown) => T): Promise<T> {
  const identity = identitySnapshot(), base = getApiBase(); requireValue(base === '/api');
  const result = await apiPostUnqueued(path, body, {});
  requireValue(identitySnapshot() === identity && getApiBase() === base); return parse(result);
}
export function readRenewalStatus() { return readChecked(`${renewalPrefix}/status`, parseRenewalStatus); }
export function readRenewalOperation(op: RenewalOperation, key: string) {
  operation(op); requireValue(identifier(key, 120));
  return readChecked(`${renewalPrefix}/requests/${op}/${key}`, value => parseRenewalOperation(value, op, key));
}
export function postRenewalOperation(op: RenewalOperation, value: unknown) {
  const c = parseRenewalCommand(op, value);
  return postChecked(`${renewalPrefix}/${op}`, c, body => parseRenewalOperation(body, op, c.idempotencyKey, c));
}
export function readRenewalChain(proposalId: string) {
  requireValue(identifier(proposalId, 160));
  return readChecked(`${renewalPrefix}/chains/${proposalId}`, value => parseRenewalChain(value, proposalId));
}
export function postRenewalDecisionAndPublish(value: unknown, consumeKey: string) {
  const c = parseRenewalCommand('decide', value) as RenewalDecisionCommand;
  requireValue(c.decision === 'approved' && identifier(consumeKey, 120) && consumeKey !== c.idempotencyKey);
  return postChecked(`${renewalPrefix}/decide-and-publish`, { decisionCommand: c, consumeIdempotencyKey: consumeKey }, body => {
    const result = parseRenewalChain(body, c.proposalId);
    requireValue(result.decisionIdempotencyKey === c.idempotencyKey && result.consumeIdempotencyKey === consumeKey);
    if (result.decision) parseRenewalOperation(result.decision, 'decide', c.idempotencyKey, c);
    return result;
  });
}
export function continueRenewalChain(known: RenewalChain) {
  const c = parseRenewalChain(known, known.proposalId);
  requireValue(c.state === 'decision-not-attempted' || c.state === 'publication-not-attempted');
  return postChecked(`${renewalPrefix}/chains/${c.proposalId}/continue`, { decisionIdempotencyKey: c.decisionIdempotencyKey }, body => {
    const result = parseRenewalChain(body, c.proposalId);
    requireValue(result.decisionIdempotencyKey === c.decisionIdempotencyKey && result.consumeIdempotencyKey === c.consumeIdempotencyKey);
    return result;
  });
}
export function readRenewalHistory(offset = 0) {
  requireValue(Number.isSafeInteger(offset) && offset >= 0 && offset <= 4095 && offset % 5 === 0);
  return readChecked(`${renewalPrefix}/requests${offset === 0 ? '' : `/page/${offset}`}`, parseRenewalHistory);
}

/** Link visible objects; these checks grant no approval or execution permission. */
export function assertRenewalPreparedSource(prepared: RenewalPreparedReceipt, source: RenewalSource): void {
  const s = parseRenewalSource(source, source.sourcePolicy.policyId);
  const p = parsePrepared(row(prepared), prepared.proposal.request.idempotencyKey).proposal;
  const providerMatches = s.sourceProvider !== null &&
    instant(p.sourceProvider.createdAt) === instant(s.sourceProvider.createdAt) &&
    same({ ...p.sourceProvider, createdAt: s.sourceProvider.createdAt }, s.sourceProvider);
  requireValue(s.state === 'ready' && p.sourceHeadVersion === s.sourceHeadVersion && same(p.sourcePolicy, s.sourcePolicy) &&
    same(p.sourceBudget, s.sourceBudget) && providerMatches);
}
/** Display observation at the source read time, never a current execution permit. */
export function renewalTargetWindow(prepared: RenewalPreparedReceipt, source: RenewalSource): Window {
  assertRenewalPreparedSource(prepared, source);
  return windowAt(prepared.proposal.targetActive, instant(source.evaluatedAt));
}
export function assertRenewalDecisionProposal(decision: RenewalDecisionReceipt, prepared: RenewalPreparedReceipt): void {
  const p = parsePrepared(row(prepared), prepared.proposal.request.idempotencyKey);
  const d = parseDecision(row(decision), decision.operation, decision.decisionPayload.command.idempotencyKey);
  requireValue(d.proposalId === p.proposalId && d.proposalHash === p.proposalHash && d.targetActiveHash === p.targetActiveHash &&
    instant(d.decisionPayload.expiresAt) === instant(p.proposal.targetActive.effectiveUntil));
}
export function assertRenewalPublicationProposal(publication: RenewalPublicationReceipt, prepared: RenewalPreparedReceipt): void {
  const p = parsePrepared(row(prepared), prepared.proposal.request.idempotencyKey);
  const r = parsePublication(row(publication), publication.command.idempotencyKey);
  const body = Object.fromEntries(Object.entries(r.policy).filter(([k]) => !metadataKeys.includes(k)));
  requireValue(r.proposalId === p.proposalId && r.proposalHash === p.proposalHash &&
    r.policy.contentHash === p.targetActiveHash && r.headVersionBefore === p.proposal.sourceHeadVersion && same(body, p.proposal.targetActive));
}

export type RenewalReference = { kind: 'operation'; operation: RenewalOperation; key: string; proposalKey: string } |
  { kind: 'chain'; proposalId: string; decisionKey: string; consumeKey: string; proposalKey: string };
export type RenewalRestoredReference = { state: 'none' } | { state: 'invalid' } | { state: 'ready'; ref: RenewalReference };
const recoveryFields = ['budgetRenewalKind', 'budgetRenewalOp', 'budgetRenewalKey', 'budgetRenewalProposalKey',
  'budgetRenewalProposalId', 'budgetRenewalDecisionKey', 'budgetRenewalConsumeKey', 'budgetRenewalAttempted'];
function reference(value: RenewalReference): RenewalReference {
  const r = row(value);
  requireValue(identifier(r.proposalKey, 120));
  if (r.kind === 'operation') {
    exact(r, ['kind', 'operation', 'key', 'proposalKey']); operation(r.operation);
    requireValue(identifier(r.key, 120) && (r.operation !== 'propose' || r.key === r.proposalKey));
  } else {
    exact(r, ['kind', 'proposalId', 'decisionKey', 'consumeKey', 'proposalKey']);
    requireValue(r.kind === 'chain' && identifier(r.proposalId, 160) && identifier(r.decisionKey, 120) &&
      identifier(r.consumeKey, 120) && r.decisionKey !== r.consumeKey);
  }
  return structuredClone(r) as RenewalReference;
}
export function restoreRenewalReference(search: string): RenewalRestoredReference {
  try {
    const params = new URLSearchParams(search), own = [...params.keys()].filter(k => k.startsWith('budgetRenewal'));
    if (own.length === 0) return { state: 'none' };
    requireValue(own.every(k => recoveryFields.includes(k) && params.getAll(k).length === 1));
    requireValue(params.get('budgetRenewalAttempted') === '1');
    const kind = params.get('budgetRenewalKind');
    const expected = ['budgetRenewalKind', 'budgetRenewalProposalKey', 'budgetRenewalAttempted',
      ...(kind === 'operation' ? ['budgetRenewalOp', 'budgetRenewalKey'] : ['budgetRenewalProposalId', 'budgetRenewalDecisionKey', 'budgetRenewalConsumeKey'])];
    requireValue(own.length === expected.length && expected.every(k => params.has(k)));
    const r = kind === 'operation' ? { kind, operation: params.get('budgetRenewalOp'), key: params.get('budgetRenewalKey'),
      proposalKey: params.get('budgetRenewalProposalKey') } : { kind, proposalId: params.get('budgetRenewalProposalId'),
      decisionKey: params.get('budgetRenewalDecisionKey'), consumeKey: params.get('budgetRenewalConsumeKey'), proposalKey: params.get('budgetRenewalProposalKey') };
    return { state: 'ready', ref: reference(r as RenewalReference) };
  } catch { return { state: 'invalid' }; }
}
export function saveRenewalReference(value: RenewalReference): void {
  const r = reference(value), url = new URL(window.location.href);
  for (const k of [...url.searchParams.keys()]) if (k.startsWith('budgetRenewal')) url.searchParams.delete(k);
  const params = url.searchParams;
  params.set('budgetRenewalKind', r.kind); params.set('budgetRenewalProposalKey', r.proposalKey); params.set('budgetRenewalAttempted', '1');
  if (r.kind === 'operation') { params.set('budgetRenewalOp', r.operation); params.set('budgetRenewalKey', r.key); }
  else { params.set('budgetRenewalProposalId', r.proposalId); params.set('budgetRenewalDecisionKey', r.decisionKey); params.set('budgetRenewalConsumeKey', r.consumeKey); }
  window.history.replaceState(window.history.state, '', url.pathname + url.search + url.hash);
  const readback = restoreRenewalReference(window.location.search);
  requireValue(readback.state === 'ready' && same(readback.ref, r));
}
export function clearRenewalReference(): void {
  const url = new URL(window.location.href);
  for (const k of [...url.searchParams.keys()]) if (k.startsWith('budgetRenewal')) url.searchParams.delete(k);
  window.history.replaceState(window.history.state, '', url.pathname + url.search + url.hash);
}
export type RenewalRecovery = { ref: RenewalReference; proposal: RenewalOperationResult;
  prepared: RenewalPreparedReceipt | null; result: RenewalOperationResult | RenewalChain };
export async function readRenewalRecovery(value: RenewalReference): Promise<RenewalRecovery> {
  const r = reference(value), actor = identitySnapshot(), base = getApiBase();
  const proposal = await readRenewalOperation('propose', r.proposalKey);
  const prepared = proposal.receipt && 'proposal' in proposal.receipt ? proposal.receipt : null;
  const result = r.kind === 'chain' ? await readRenewalChain(r.proposalId) : r.operation === 'propose' ? proposal : await readRenewalOperation(r.operation, r.key);
  requireValue(identitySnapshot() === actor && getApiBase() === base);
  if (r.kind === 'chain') {
    const chain = result as RenewalChain;
    requireValue(chain.decisionIdempotencyKey === r.decisionKey && chain.consumeIdempotencyKey === r.consumeKey);
    if (prepared) {
      requireValue(chain.proposalId === prepared.proposalId);
      const d = chain.decision?.receipt, p = chain.publication?.receipt;
      if (d && 'decisionPayload' in d) assertRenewalDecisionProposal(d, prepared);
      if (p && 'policy' in p) assertRenewalPublicationProposal(p, prepared);
    }
  } else if (prepared) {
    const receipt = (result as RenewalOperationResult).receipt;
    if (receipt && 'decisionPayload' in receipt) assertRenewalDecisionProposal(receipt, prepared);
    if (receipt && 'policy' in receipt) assertRenewalPublicationProposal(receipt, prepared);
  }
  return { ref: r, proposal, prepared, result };
}

/** Form validation only; current native facts and authorization are rechecked by B. */
export function renewalProposalCommand(source: RenewalSource, originalKey: string, effectiveFrom: string, effectiveUntil: string): RenewalProposalCommand {
  const s = parseRenewalSource(source, source.sourcePolicy.policyId);
  const c = parseRenewalCommand('propose', { schemaVersion: 1, orgId: 'org-org', projectId: 'dev-project', idempotencyKey: originalKey,
    sourcePolicyId: s.sourcePolicy.policyId, expectedSourceRevision: s.sourcePolicy.revision, expectedHeadVersion: s.sourceHeadVersion,
    expectedSourceHash: s.sourcePolicy.contentHash, effectiveFrom, effectiveUntil }) as RenewalProposalCommand;
  requireValue(s.state === 'ready' && s.sourceBudget && instant(c.effectiveFrom) >= instant(s.sourcePolicy.effectiveUntil) &&
    instant(c.effectiveFrom) >= instant(s.sourceBudget.effectiveFrom) && instant(c.effectiveUntil) <= instant(s.sourceBudget.effectiveUntil) &&
    instant(c.effectiveUntil) > instant(s.evaluatedAt));
  return c;
}
