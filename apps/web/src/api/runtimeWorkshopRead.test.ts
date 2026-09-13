import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { setTenant, setAccessToken } from './tenant';
import { parseRuntimeWorkshopCatalog } from './runtimeWorkshop';
import { fixture, tenant } from './runtimeWorkshop.testFixtures';
import { RuntimeWorkshopRead, RuntimeReadPending } from './runtimeWorkshopRead';

const requestId = '33333333-3333-4333-8333-333333333333';
let now = Date.now();
const requestHash = `sha256:${'b'.repeat(64)}`;
function entry() {
  const raw = fixture();
  raw.items[0].module.moduleId = 'ecommerce.analyst';
  raw.items[0].moduleRef.bundleId = 'solution.ecommerce.growth';
  const parsed = parseRuntimeWorkshopCatalog(raw, tenant).items[0];
  parsed.ui.readOperationClaims = ['analyst_workspace_view_v1'];
  return parsed;
}
function receipt() {
  return { schemaVersion: 'aos.runtime-ui-read-status/v1', tenant, requestId, requestHash,
    state: 'requested', revision: 1, deadline: new Date(now + 60_000).toISOString() };
}
function status(state = 'succeeded') {
  return { ...receipt(), state, revision: state === 'requested' ? 1 : 3,
    completedAt: state === 'requested' ? null : new Date().toISOString(),
    result: state === 'succeeded' ? { schemaVersion: 'aos.analyst-workspace-view/v1', tenant,
      cutoffAt: new Date().toISOString(), cases: [], caseCount: 0, runCount: 0, truncated: false, executionAllowed: false } : null,
    resultHash: state === 'succeeded' ? `sha256:${'c'.repeat(64)}` : null,
    failureCode: state === 'failed' ? 'READ_OUTCOME_UNKNOWN' : null };
}
const response = (value: unknown) => ({ ok: true, json: async () => JSON.parse(JSON.stringify(value)) });
beforeEach(() => { now = Date.now(); setTenant({ ...tenant, subject: 'reader', roles: ['reader'] }); setAccessToken(null); });
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });
function session(isCurrent = () => true, controller = new AbortController()) {
  return new RuntimeWorkshopRead(entry(), { isCurrent, signal: controller.signal });
}

it('submits once then only queries the original request', async () => {
  const fetch = vi.fn().mockResolvedValueOnce(response(receipt())).mockResolvedValue(response(status()));
  vi.stubGlobal('fetch', fetch);
  const read = session();
  await read.submit();
  await expect(read.submit()).rejects.toThrow();
  expect((await read.wait()).state).toBe('succeeded');
  expect(fetch.mock.calls.map(call => call[1].method)).toEqual(['POST', 'GET']);
  expect(fetch.mock.calls[1][0]).toContain(`/reads/${requestId}`);
  expect(fetch.mock.calls.every(call => call[1].cache === 'no-store')).toBe(true);
});

it('does not resubmit when POST outcome is unknown', async () => {
  const fetch = vi.fn().mockRejectedValue(new Error('private-sentinel'));
  vi.stubGlobal('fetch', fetch);
  const read = session();
  await expect(read.submit()).rejects.not.toThrow('private-sentinel');
  await expect(read.submit()).rejects.toThrow();
  await expect(read.wait()).rejects.toThrow();
  expect(fetch).toHaveBeenCalledTimes(1);
});

it.each(['scope', 'subject', 'token', 'resource', 'abort'])('drops late replies after %s changes', async change => {
  let resolve!: (value: unknown) => void;
  vi.stubGlobal('fetch', vi.fn().mockReturnValue(new Promise(yes => { resolve = yes; })));
  const controller = new AbortController();
  let current = true;
  const read = session(() => current, controller);
  const pending = read.submit();
  if (change === 'scope') setTenant({ orgId: 'dev-org' });
  if (change === 'subject') setTenant({ subject: 'other' });
  if (change === 'token') setAccessToken('different-token');
  if (change === 'resource') current = false;
  if (change === 'abort') controller.abort();
  resolve(response(receipt()));
  await expect(pending).rejects.toThrow();
  expect(read.requestId).toBeNull();
});

it.each(['scope', 'id', 'digest', 'revision', 'result', 'failure'])('rejects result %s drift', async change => {
  const value = status() as Record<string, unknown>;
  if (change === 'scope') value.tenant = { ...tenant, orgId: 'dev-org' };
  if (change === 'id') value.requestId = '44444444-4444-4444-8444-444444444444';
  if (change === 'digest') value.requestHash = `sha256:${'d'.repeat(64)}`;
  if (change === 'revision') value.revision = 0;
  if (change === 'result') (value.result as Record<string, unknown>).executionAllowed = true;
  if (change === 'failure') value.failureCode = 'secret-error';
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(response(receipt())).mockResolvedValueOnce(response(value)));
  const read = session();
  await read.submit();
  await expect(read.wait()).rejects.toThrow();
});

it('retains the same ID across a bounded wait without another POST', async () => {
  vi.useFakeTimers();
  const fetch = vi.fn().mockResolvedValueOnce(response(receipt())).mockResolvedValue(response(status('requested')));
  vi.stubGlobal('fetch', fetch);
  const read = session();
  await read.submit();
  const waiting = read.wait();
  const check = expect(waiting).rejects.toBeInstanceOf(RuntimeReadPending);
  await vi.advanceTimersByTimeAsync(60_001);
  await check;
  fetch.mockResolvedValue(response(status()));
  expect((await read.wait()).state).toBe('succeeded');
  expect(fetch.mock.calls.filter(call => call[1].method === 'POST')).toHaveLength(1);
});

it('does not treat an unknown attempt as success', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(response(receipt())).mockResolvedValueOnce(response(status('failed'))));
  const read = session();
  await read.submit();
  const result = await read.wait();
  expect(result.state).toBe('failed');
  expect(result.result).toBeNull();
});


it('bounds even a network implementation that ignores cancellation', async () => {
  vi.useFakeTimers();
  const fetch = vi.fn().mockReturnValue(new Promise(() => {}));
  vi.stubGlobal('fetch', fetch);
  const read = session();
  const checking = expect(read.submit()).rejects.toThrow('不会自动重复提交');
  await vi.advanceTimersByTimeAsync(10_001);
  await checking;
  await expect(read.submit()).rejects.toThrow();
  expect(fetch).toHaveBeenCalledTimes(1);
});

it('does not allow a caller to redirect the stored request ID', async () => {
  const fetch = vi.fn().mockResolvedValueOnce(response(receipt())).mockResolvedValue(response(status()));
  vi.stubGlobal('fetch', fetch);
  const read = session();
  const accepted = await read.submit();
  accepted.requestId = '44444444-4444-4444-8444-444444444444';
  const result = await read.wait();
  result.requestId = '55555555-5555-4555-8555-555555555555';
  await read.wait();
  expect(fetch.mock.calls.slice(1).every(call => call[0].endsWith('/' + requestId))).toBe(true);
});

it('cancels the polling pause without a second query', async () => {
  vi.useFakeTimers();
  const controller = new AbortController();
  const fetch = vi.fn().mockResolvedValueOnce(response(receipt())).mockResolvedValue(response(status('requested')));
  vi.stubGlobal('fetch', fetch);
  const read = session(() => true, controller);
  await read.submit();
  const checking = expect(read.wait()).rejects.toThrow();
  await vi.advanceTimersByTimeAsync(1);
  controller.abort();
  await checking;
  await vi.advanceTimersByTimeAsync(10_000);
  expect(fetch).toHaveBeenCalledTimes(2);
});


it('does not revive an old session if credentials change and then return', async () => {
  setAccessToken('first-token');
  const read = session();
  setAccessToken('second-token');
  setAccessToken('first-token');
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  await expect(read.submit()).rejects.toThrow();
  expect(fetch).not.toHaveBeenCalled();
});
