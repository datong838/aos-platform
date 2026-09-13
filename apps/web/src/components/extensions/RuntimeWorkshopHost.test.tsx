import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { parseRuntimeWorkshopCatalog } from '../../api/runtimeWorkshop';
import { fixture, tenant } from '../../api/runtimeWorkshop.testFixtures';
import { setTenant, setAccessToken } from '../../api/tenant';
import { RuntimeReadPending } from '../../api/runtimeWorkshopRead';
import type { ExtensionHostProps } from './ExtensionHost';
import { RuntimeWorkshopHost } from './RuntimeWorkshopHost';

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let props: ExtensionHostProps;
vi.mock('./ExtensionHost', () => ({ ExtensionHost: (value: ExtensionHostProps) => {
  props = value;
  return <div data-testid="frame">{value.spec ? 'ready' : 'closed'}</div>;
} }));
let root: Root, host: HTMLDivElement;
beforeEach(() => {
  setTenant({ ...tenant, subject: 'reader', roles: ['reader'] }); setAccessToken(null);
  host = document.createElement('div'); document.body.append(host); root = createRoot(host);
});
afterEach(() => { act(() => root.unmount()); host.remove(); });
function entry() {
  const value = fixture();
  value.items[0].module.moduleId = 'ecommerce.analyst';
  value.items[0].moduleRef.bundleId = 'solution.ecommerce.growth';
  const parsed = parseRuntimeWorkshopCatalog(value, tenant).items[0];
  parsed.ui.readOperationClaims = ['analyst_workspace_view_v1'];
  return parsed;
}
function port() {
  let id: string | null = null;
  const receipt = { schemaVersion: 'aos.runtime-ui-read-status/v1' as const, tenant,
    requestId: '33333333-3333-4333-8333-333333333333', requestHash: `sha256:${'b'.repeat(64)}`,
    state: 'requested' as const, revision: 1, deadline: new Date(Date.now() + 60_000).toISOString() };
  return { get requestId() { return id; },
    submit: vi.fn(async () => { id = receipt.requestId; return receipt; }),
    wait: vi.fn(async () => ({ ...receipt, state: 'succeeded' as const, revision: 3,
      completedAt: new Date().toISOString(), result: { caseCount: 0 }, resultHash: `sha256:${'c'.repeat(64)}`, failureCode: null })),
  };
}
it('uses fixed reads and resumes pending with the same port', async () => {
  const read = port(); read.wait.mockRejectedValueOnce(new RuntimeReadPending('accepted-request'));
  const factory = vi.fn(() => read);
  await act(async () => root.render(<RuntimeWorkshopHost entry={entry()} isCurrent={() => true} navigate={vi.fn()} createRead={factory} />));
  await act(async () => { await expect(props.onRead!('analyst_workspace_view_v1', {})).rejects.toThrow(); });
  await act(async () => { expect((await props.onRead!('analyst_workspace_view_v1', {}) as { state: string }).state).toBe('succeeded'); });
  expect(factory).toHaveBeenCalledTimes(1);
  expect(read.submit).toHaveBeenCalledTimes(1);
  expect(read.wait).toHaveBeenCalledTimes(2);
  await expect(props.onRead!('publish', {})).rejects.toThrow();
  await expect(props.onRead!('analyst_workspace_view_v1', { sql: 'SELECT secret' })).rejects.toThrow();
  expect(props.onCommand).toBeUndefined();
});
it('never repeats a submit with unknown outcome', async () => {
  const read = port(); read.submit.mockRejectedValue(new Error('unknown'));
  const factory = vi.fn(() => read);
  await act(async () => root.render(<RuntimeWorkshopHost entry={entry()} isCurrent={() => true} navigate={vi.fn()} createRead={factory} />));
  await act(async () => { await expect(props.onRead!('analyst_workspace_view_v1', {})).rejects.toThrow(); });
  await act(async () => { await expect(props.onRead!('analyst_workspace_view_v1', {})).rejects.toThrow(); });
  expect(read.submit).toHaveBeenCalledTimes(1);
  expect(factory).toHaveBeenCalledTimes(1);
});
it.each(['binding', 'installation', 'auth'])('closes old reads after %s changes', async change => {
  const signals: AbortSignal[] = [];
  const factory = vi.fn((_entry, options) => { signals.push(options.signal); return port(); });
  const value = entry();
  const render = () => root.render(<RuntimeWorkshopHost entry={value} isCurrent={() => true} navigate={vi.fn()} createRead={factory} />);
  await act(async () => render());
  await act(async () => { await props.onRead!('analyst_workspace_view_v1', {}); });
  if (change === 'binding') { value.bindingRevision++; await act(async () => render()); }
  if (change === 'installation') { value.installationRevision++; await act(async () => render()); }
  if (change === 'auth') await act(async () => setAccessToken('replacement'));
  expect(signals[0].aborted).toBe(true);
  if (change === 'auth') expect(host.textContent).toContain('closed');
});
