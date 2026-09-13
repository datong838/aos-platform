import type { RuntimeConfigurationRef } from './types';

export interface ConfigurationSourceRef { authority: string; id: string; revision: number; hash: string; }
export interface ConfigurationStageTarget { installationId: string; installationEtag: number; generation: string; bindingRevision: number; }
export interface ConfigurationSourceCatalog {
  target: ConfigurationStageTarget | null; installationRevision: number;
  roles: { label: string; ref: ConfigurationSourceRef }[];
  policies: { label: string; ref: ConfigurationSourceRef }[];
  rolesHasMore: boolean; policiesHasMore: boolean;
}
export interface ConfigurationStageRequest {
  schemaVersion: 'aos.runtime-configuration-stage/v1'; action: 'stage-configuration';
  target: ConfigurationStageTarget; roleRefs: ConfigurationSourceRef[];
  policyRef: ConfigurationSourceRef; previousRef: RuntimeConfigurationRef | null;
}
export interface ConfigurationStageReceipt {
  schemaVersion: 'aos.runtime-configuration-stage-status/v1';
  tenant: { orgId: string; projectId: string }; requestId: string; requestHash: string;
  state: 'requested' | 'succeeded' | 'rejected' | 'expired'; revision: number; deadline: string;
  result?: RuntimeConfigurationRef | null; failureCode?: string | null;
}
const roleAuthority = 'aip.responsibility_plan_revision';
const policyAuthority = 'aip.runtime_policy_revision';
function check(ok: unknown): asserts ok { if (!ok) throw new Error('配置协议校验失败，请重新读取'); }
function record(value: unknown, fields: string[]): Record<string, unknown> {
  check(value && typeof value === 'object' && !Array.isArray(value));
  const item = value as Record<string, unknown>;
  check(Object.keys(item).length === fields.length && fields.every(key => Object.hasOwn(item, key)));
  return item;
}
function positive(value: unknown) { check(Number.isSafeInteger(value) && Number(value) > 0); }
function text(value: unknown, max = 500): asserts value is string { check(typeof value === 'string' && value.length > 0 && value.length <= max && value === value.trim() && !value.includes('\0')); }
function uuid(value: unknown) { check(typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(value)); }
function hash(value: unknown) { check(typeof value === 'string' && /^sha256:[0-9a-f]{64}$/.test(value)); }
function target(value: unknown) {
  const item = record(value, ['installationId', 'installationEtag', 'generation', 'bindingRevision']);
  uuid(item.installationId); uuid(item.generation); positive(item.installationEtag); positive(item.bindingRevision);
}
function source(value: unknown, authority: string) {
  const item = record(value, ['authority', 'id', 'revision', 'hash']);
  check(item.authority === authority); text(item.id); positive(item.revision); hash(item.hash);
}
function configurationRef(value: unknown) {
  const item = record(value, ['configurationId', 'revision', 'hash']);
  uuid(item.configurationId); positive(item.revision); hash(item.hash);
}
export function parseConfigurationSources(value: unknown): ConfigurationSourceCatalog {
  const item = record(value, ['target', 'installationRevision', 'roles', 'policies', 'rolesHasMore', 'policiesHasMore']);
  positive(item.installationRevision); if (item.target !== null) target(item.target);
  check(typeof item.rolesHasMore === 'boolean' && typeof item.policiesHasMore === 'boolean');
  for (const [field, authority] of [['roles', roleAuthority], ['policies', policyAuthority]]) {
    const choices = item[field!]; check(Array.isArray(choices) && choices.length <= 50);
    const seen = new Set<string>();
    for (const value of choices) {
      const choice = record(value, ['label', 'ref']); text(choice.label); source(choice.ref, authority!);
      const ref = choice.ref as ConfigurationSourceRef; check(!seen.has(ref.id)); seen.add(ref.id);
    }
    if (item.target === null) check(choices.length === 0 && !item[field + 'HasMore']);
  }
  return value as ConfigurationSourceCatalog;
}
export function serializeConfigurationStage(value: ConfigurationStageRequest): ConfigurationStageRequest {
  const item = record(value, ['schemaVersion', 'action', 'target', 'roleRefs', 'policyRef', 'previousRef']);
  check(item.schemaVersion === 'aos.runtime-configuration-stage/v1' && item.action === 'stage-configuration');
  target(item.target); source(item.policyRef, policyAuthority);
  check(Array.isArray(item.roleRefs) && item.roleRefs.length > 0 && item.roleRefs.length <= 64);
  const seen = new Set<string>();
  for (const ref of item.roleRefs) { source(ref, roleAuthority); check(!seen.has(ref.id)); seen.add(ref.id); }
  if (item.previousRef !== null) configurationRef(item.previousRef);
  check(new TextEncoder().encode(JSON.stringify(value)).length <= 65536);
  return value;
}
export function parseConfigurationStageReceipt(value: unknown, expectedTenant: { orgId: string; projectId: string }, status: boolean, expectedId?: string): ConfigurationStageReceipt {
  const fields = ['schemaVersion', 'tenant', 'requestId', 'requestHash', 'state', 'revision', 'deadline'];
  const item = record(value, status ? [...fields, 'result', 'failureCode'] : fields);
  check(item.schemaVersion === 'aos.runtime-configuration-stage-status/v1');
  const tenant = record(item.tenant, ['orgId', 'projectId']);
  check(tenant.orgId === expectedTenant.orgId && tenant.projectId === expectedTenant.projectId);
  uuid(item.requestId); hash(item.requestHash); positive(item.revision);
  if (expectedId) check(item.requestId === expectedId);
  check(['requested', 'succeeded', 'rejected', 'expired'].includes(String(item.state)));
  text(item.deadline); check(/T.*(?:Z|[+-]\d\d:\d\d)$/.test(item.deadline) && Number.isFinite(Date.parse(item.deadline)));
  if (status) {
    check((item.state === 'succeeded') === (item.result !== null));
    check((item.state === 'rejected' || item.state === 'expired') === (item.failureCode !== null));
    if (item.result !== null) configurationRef(item.result);
    if (item.failureCode !== null) check(typeof item.failureCode === 'string' && /^[A-Z][A-Z0-9_]{0,79}$/.test(item.failureCode));
  }
  return value as ConfigurationStageReceipt;
}
