import { getApiBase } from './apiBase';
import { getAccessToken, getAuthRevision, getTenant, tenantAuthHeaders } from './tenant';
import type { RuntimeWorkshopEntry } from './runtimeWorkshop';

type State = 'requested' | 'claimed' | 'succeeded' | 'denied' | 'failed' | 'expired';
type Tenant = { orgId: string; projectId: string };
export type RuntimeReadReceipt = {
  schemaVersion: 'aos.runtime-ui-read-status/v1'; tenant: Tenant;
  requestId: string; requestHash: string; state: State; revision: number; deadline: string;
};
export type RuntimeReadStatus = RuntimeReadReceipt & {
  completedAt: string | null; result: Record<string, unknown> | null;
  resultHash: string | null; failureCode: string | null;
};
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const hash = /^sha256:[0-9a-f]{64}$/;
const states = ['requested', 'claimed', 'succeeded', 'denied', 'failed', 'expired'];
const failures = ['READ_ACCESS_REVOKED', 'READ_FAILED', 'READ_RESULT_INVALID', 'READ_OUTCOME_UNKNOWN',
  'READ_DEADLINE_EXPIRED', 'READ_RUNTIME_CHANGED', 'READ_ADMISSION_DENIED'];
const invalid = () => new Error('工作台读取响应无效，请刷新当前工作台。');
const identityKey = () => { const t = getTenant(); return JSON.stringify([t.orgId, t.projectId, t.subject, t.roles, getAuthRevision()]); };
function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw invalid();
  return value as Record<string, unknown>;
}
function timestamp(value: unknown): value is string {
  return typeof value === 'string' && /T.*(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value));
}
function sameKeys(value: Record<string, unknown>, keys: string[]) {
  if (Object.keys(value).length !== keys.length || keys.some(key => !(key in value))) throw invalid();
}
function parse(value: unknown, tenant: Tenant, expected?: RuntimeReadReceipt): RuntimeReadReceipt | RuntimeReadStatus {
  const v = object(value), scope = object(v.tenant);
  const keys = ['schemaVersion', 'tenant', 'requestId', 'requestHash', 'state', 'revision', 'deadline'];
  sameKeys(v, expected ? [...keys, 'completedAt', 'result', 'resultHash', 'failureCode'] : keys);
  if (v.schemaVersion !== 'aos.runtime-ui-read-status/v1' || scope.orgId !== tenant.orgId || scope.projectId !== tenant.projectId
      || typeof v.requestId !== 'string' || !uuid.test(v.requestId) || typeof v.requestHash !== 'string' || !hash.test(v.requestHash)
      || typeof v.state !== 'string' || !states.includes(v.state) || !Number.isSafeInteger(v.revision) || Number(v.revision) < 1
      || !timestamp(v.deadline)) throw invalid();
  if (!expected) return v as RuntimeReadReceipt;
  if (v.requestId !== expected.requestId || v.requestHash !== expected.requestHash || Number(v.revision) < expected.revision
      || Date.parse(v.deadline) !== Date.parse(expected.deadline)) throw invalid();
  const pending = v.state === 'requested' || v.state === 'claimed';
  if (pending ? v.completedAt !== null : !timestamp(v.completedAt)) throw invalid();
  if (v.state === 'succeeded') {
    const result = object(v.result), resultTenant = object(result.tenant);
    if (v.failureCode !== null || typeof v.resultHash !== 'string' || !hash.test(v.resultHash)
        || result.schemaVersion !== 'aos.analyst-workspace-view/v1' || result.executionAllowed !== false
        || resultTenant.orgId !== tenant.orgId || resultTenant.projectId !== tenant.projectId
        || !timestamp(result.cutoffAt) || !Array.isArray(result.cases) || result.caseCount !== result.cases.length
        || result.cases.length > 50 || !Number.isSafeInteger(result.runCount) || Number(result.runCount) < 0
        || Number(result.runCount) > 500 || typeof result.truncated !== 'boolean'
        || new TextEncoder().encode(JSON.stringify(result)).length > 900000) throw invalid();
  } else if (v.result !== null || v.resultHash !== null
      || (pending ? v.failureCode !== null : typeof v.failureCode !== 'string' || !failures.includes(v.failureCode))) throw invalid();
  return v as RuntimeReadStatus;
}

export class RuntimeReadPending extends Error {
  constructor(readonly requestId: string) {
    super('本次读取尚未取得结果，可以继续查看同一请求。');
  }
}

/** A transport session, never an authority decision or a package instance. */
export class RuntimeWorkshopRead {
  private readonly key = crypto.randomUUID();
  private readonly identity = identityKey();
  private readonly token = getAccessToken();
  private readonly base = getApiBase();
  private readonly tenant: Tenant;
  private readonly request: Record<string, unknown>;
  private submitted = false;
  private polling = false;
  private receipt: RuntimeReadReceipt | null = null;

  constructor(entry: RuntimeWorkshopEntry, private readonly options: { isCurrent: () => boolean; signal: AbortSignal },
              limits: { caseLimit?: number; runLimit?: number } = {}) {
    const { orgId, projectId, subject } = getTenant();
    if (!subject || !orgId || !projectId || entry.module.moduleId !== 'ecommerce.analyst'
        || entry.moduleRef.bundleId !== 'solution.ecommerce.growth' || entry.module.route !== '/workshop/analyst'
        || !entry.ui.readOperationClaims.includes('analyst_workspace_view_v1')
        || entry.ui.initialRoute !== entry.module.route || !entry.ui.routeClaims.includes(entry.module.route)
        || !hash.test(entry.ui.resourceHash) || !uuid.test(entry.installationId) || !uuid.test(entry.generation)
        || [entry.installationRevision, entry.executionEpoch, entry.bindingRevision].some(n => !Number.isSafeInteger(n) || n < 1)) throw invalid();
    const caseLimit = limits.caseLimit ?? 20, runLimit = limits.runLimit ?? 5;
    if (Object.keys(limits).some(key => !['caseLimit', 'runLimit'].includes(key))
        || !Number.isSafeInteger(caseLimit) || caseLimit < 1 || caseLimit > 50
        || !Number.isSafeInteger(runLimit) || runLimit < 1 || runLimit > 10) throw invalid();
    this.tenant = { orgId, projectId };
    this.request = { schemaVersion: 'aos.runtime-ui-read-request/v1', operationId: 'analyst_workspace_view_v1',
      moduleId: 'ecommerce.analyst', caseLimit, runLimit, target: { installationId: entry.installationId,
        installationRevision: entry.installationRevision, generation: entry.generation, executionEpoch: entry.executionEpoch,
        bindingRevision: entry.bindingRevision, route: entry.module.route, resourceHash: entry.ui.resourceHash } };
    this.current();
  }
  get requestId(): string | null { return this.receipt?.requestId ?? null; }

  private current() {
    if (this.options.signal.aborted || !this.options.isCurrent() || identityKey() !== this.identity
        || getAccessToken() !== this.token || getApiBase() !== this.base) throw new Error('当前账号或工作台已变化，旧读取已停止。');
  }
  private async http(method: 'POST' | 'GET', suffix: string, timeoutMs: number): Promise<unknown> {
    this.current();
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let stop = () => {};
    const interrupted = new Promise<never>((_, reject) => {
      stop = () => { controller.abort(); reject(new Error('读取已停止。')); };
      this.options.signal.addEventListener('abort', stop, { once: true });
      timer = setTimeout(() => {
        controller.abort();
        reject(this.requestId ? new RuntimeReadPending(this.requestId) : new Error('提交结果尚不明确，本次不会自动重复提交。'));
      }, timeoutMs);
    });
    try {
      const value = await Promise.race([interrupted, (async () => {
        const response = await fetch(`${this.base}/v1/runtime-workshop/reads${suffix}`, {
          method, cache: 'no-store', signal: controller.signal,
          headers: { ...tenantAuthHeaders(), ...(method === 'POST' ? { 'Idempotency-Key': this.key } : {}) },
          ...(method === 'POST' ? { body: JSON.stringify(this.request) } : {}),
        });
        if (!response.ok) throw new Error('读取条件未满足，请检查当前工作台状态。');
        return response.json();
      })()]);
      this.current();
      return value;
    } catch (error) {
      if (error instanceof RuntimeReadPending) throw error;
      throw new Error(method === 'POST' ? '未取得提交确认，本次不会自动重复提交。' : '本次读取未完成，请检查当前工作台状态。');
    } finally {
      clearTimeout(timer);
      this.options.signal.removeEventListener('abort', stop);
    }
  }

  async submit(): Promise<RuntimeReadReceipt> {
    this.current();
    if (this.submitted) throw new Error('本次读取已提交，请继续查看原请求。');
    this.submitted = true;
    const receipt = parse(await this.http('POST', '', 10_000), this.tenant);
    this.current();
    this.receipt = receipt;
    return { ...receipt, tenant: { ...receipt.tenant } };
  }

  async wait(): Promise<RuntimeReadStatus> {
    this.current();
    if (!this.receipt || this.polling) throw new Error('当前没有可继续查看的请求。');
    this.polling = true;
    const until = Date.now() + 60_000;
    try {
      while (Date.now() < until) {
        this.current();
        const value = parse(await this.http('GET', `/${this.receipt.requestId}`, Math.min(10_000, until - Date.now())),
          this.tenant, this.receipt) as RuntimeReadStatus;
        this.current();
        this.receipt = { ...value, tenant: { ...value.tenant } };
        if (value.state !== 'requested' && value.state !== 'claimed') return value;
        await this.pause(Math.min(2_000, Math.max(0, until - Date.now())));
      }
      throw new RuntimeReadPending(this.receipt.requestId);
    } finally { this.polling = false; }
  }

  private pause(ms: number) {
    return new Promise<void>((resolve, reject) => {
      const stop = () => { clearTimeout(timer); this.options.signal.removeEventListener('abort', stop); reject(new Error('读取已停止。')); };
      const timer = setTimeout(() => { this.options.signal.removeEventListener('abort', stop); resolve(); }, ms);
      this.options.signal.addEventListener('abort', stop, { once: true });
      if (this.options.signal.aborted) stop();
    });
  }
}
