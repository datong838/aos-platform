import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { afterEach, expect, it, vi } from 'vitest';
import { setTenant } from '../../api/tenant';
import { parseRuntimeWorkshopCatalog, type RuntimeWorkshopCatalog } from '../../api/runtimeWorkshop';
import { fixture, tenant } from '../../api/runtimeWorkshop.testFixtures';
import { RuntimeWorkshopCatalogProvider, useRuntimeWorkshopCatalog } from './RuntimeWorkshopCatalog';
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const cleanup: (() => void)[] = [];
afterEach(() => { cleanup.splice(0).forEach(fn => fn()); vi.useRealTimers(); });
function deferred() {
  let resolve!: (v: RuntimeWorkshopCatalog) => void;
  let reject!: (e: Error) => void;
  const promise = new Promise<RuntimeWorkshopCatalog>((yes,no) => {resolve=yes;reject=no;});
  return {promise,resolve,reject};
}
function Probe() {
  const catalog = useRuntimeWorkshopCatalog();
  return <><output>{catalog.items.length}:{catalog.phase}</output><button onClick={catalog.reload}>reload</button></>;
}
async function setup(client: (signal?: AbortSignal) => Promise<RuntimeWorkshopCatalog>) {
  setTenant(tenant);
  const host=document.createElement('div'); document.body.append(host); const root=createRoot(host);
  cleanup.push(() => {act(() => root.unmount());host.remove();});
  await act(async () => root.render(<RuntimeWorkshopCatalogProvider client={client}><Probe /></RuntimeWorkshopCatalogProvider>));
  return host;
}
it('clears prior entries before refresh and keeps them absent after failure', async () => {
  const pending=deferred();
  const client=vi.fn().mockResolvedValueOnce(parseRuntimeWorkshopCatalog(fixture(),tenant)).mockReturnValueOnce(pending.promise);
  const host=await setup(client);
  expect(host.textContent).toContain('1:ready');
  await act(async () => host.querySelector('button')!.click());
  expect(host.textContent).toContain('0:loading');
  await act(async () => pending.reject(new Error('unavailable')));
  expect(host.textContent).toContain('0:failed');
});
it('rejects late responses after tenant switch', async () => {
  const first=deferred(),second=deferred();
  const host=await setup(vi.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise));
  await act(async () => setTenant({...tenant,orgId:'dev-org'}));
  await act(async () => first.resolve(parseRuntimeWorkshopCatalog(fixture(),tenant)));
  expect(host.textContent).toContain('0:loading');
  await act(async () => second.resolve(parseRuntimeWorkshopCatalog(fixture(),tenant)));
  expect(host.textContent).toContain('0:failed');
});
it('clears cached resources when display lifetime expires', async () => {
  vi.useFakeTimers();
  const next=deferred();
  const host=await setup(vi.fn().mockResolvedValueOnce(parseRuntimeWorkshopCatalog(fixture(),tenant)).mockReturnValueOnce(next.promise));
  expect(host.textContent).toContain('1:ready');
  await act(async () => vi.advanceTimersByTime(60_000));
  expect(host.textContent).toContain('0:loading');
});
