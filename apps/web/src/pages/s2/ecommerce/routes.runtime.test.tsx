import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { RuntimeWorkshopCatalogProvider } from '../../../components/extensions/RuntimeWorkshopCatalog';
import { EcommerceWorkshopCatalogProvider } from '../../../components/workshop/EcommerceWorkshopCatalogContext';
import { InstalledModuleNavigation } from '../../../components/workshop/InstalledModuleNavigation';
import { workshopCatalogFixture, workshopModuleFixture } from '../../../components/workshop/workshopTestFixtures';
import { fixture, tenant } from '../../../api/runtimeWorkshop.testFixtures';
import { parseRuntimeWorkshopCatalog } from '../../../api/runtimeWorkshop';
import { setTenant } from '../../../api/tenant';
import { EcommerceWorkshopEntryRoute } from './routes';

vi.mock('../../../components/extensions/RuntimeWorkshopHost', () => ({ RuntimeWorkshopHost: () => <div data-testid="signed-host" /> }));
vi.mock('../../../components/workshop/EcommerceWorkshopHost', () => ({ EcommerceWorkshopHost: (props: { onCatalogReload?: () => void }) => <div data-testid="legacy-host"><button data-testid="reload-all" onClick={props.onCatalogReload}>重新读取目录</button></div> }));
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let host: HTMLDivElement, root: Root;
beforeEach(() => { setTenant({ ...tenant, subject: 'reader' }); host = document.createElement('div'); document.body.append(host); root = createRoot(host); });
afterEach(() => { act(() => root.unmount()); host.remove(); });
async function render(kind: 'runtime' | 'legacy' | 'conflict' | 'failed' | 'unknown-legacy' | 'empty') {
  const raw = fixture();
  raw.items[0].module.moduleId = 'ecommerce.analyst';
  raw.items[0].moduleRef.bundleId = 'solution.ecommerce.growth';
  const runtime = parseRuntimeWorkshopCatalog(raw, tenant);
  if (kind === 'legacy' || kind === 'empty') { runtime.items = []; runtime.count = 0; }
  const legacy = workshopCatalogFixture({ items: ['legacy', 'conflict'].includes(kind)
    ? [workshopModuleFixture({ moduleId: 'ecommerce.analyst', route: '/workshop/analyst', legacyRoutes: [] })] : [] });
  const runtimeClient = vi.fn(async () => { if (kind === 'failed') throw new Error('unavailable'); return runtime; });
  const legacyClient = { listModules: vi.fn(() => kind === 'unknown-legacy' ? new Promise<typeof legacy>(() => {}) : Promise.resolve(legacy)) };
  await act(async () => root.render(<MemoryRouter initialEntries={['/workshop/analyst']}>
    <RuntimeWorkshopCatalogProvider client={runtimeClient}>
      <EcommerceWorkshopCatalogProvider client={legacyClient}>
        <InstalledModuleNavigation /><EcommerceWorkshopEntryRoute />
      </EcommerceWorkshopCatalogProvider>
    </RuntimeWorkshopCatalogProvider>
  </MemoryRouter>));
  return { runtimeClient, legacyClient };
}
it('routes a declared runtime page to the signed host and shows its navigation', async () => {
  await render('runtime');
  expect(host.querySelector('[data-testid="signed-host"]')).not.toBeNull();
  expect(host.querySelector('[data-testid="legacy-host"]')).toBeNull();
  expect(host.querySelector('a[href="/workshop/analyst"]')?.textContent).toContain('经营参谋');
});
it('preserves an existing legacy page when no runtime page claims it', async () => {
  await render('legacy');
  expect(host.querySelector('[data-testid="legacy-host"]')).not.toBeNull();
  expect(host.querySelector('[data-testid="signed-host"]')).toBeNull();
});
it.each(['conflict', 'failed', 'unknown-legacy'] as const)('loads neither host when %s', async kind => {
  await render(kind);
  expect(host.querySelector('[data-testid="signed-host"]')).toBeNull();
  expect(host.querySelector('[data-testid="legacy-host"]')).toBeNull();
  expect(host.querySelector('[role="status"], [role="alert"]')).not.toBeNull();
});

it('refreshes both catalogs from the main empty-state action', async () => {
  const { runtimeClient, legacyClient } = await render('empty');
  await act(async () => host.querySelector<HTMLButtonElement>('[data-testid="reload-all"]')!.click());
  expect(runtimeClient).toHaveBeenCalledTimes(2);
  expect(legacyClient.listModules).toHaveBeenCalledTimes(2);
});
