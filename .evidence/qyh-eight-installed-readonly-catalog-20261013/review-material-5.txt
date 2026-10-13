import { describe, expect, it, vi } from 'vitest';
import { EcommerceWorkshopClient } from '../../apps/web/src/api/ecommerceWorkshop/client';
import evidence from './native-readonly-result.json';
const installed = evidence.modules;
const empty = { ...installed, items: [], count: 0 };
const ok = (data: unknown) => new Response(JSON.stringify(data), { status: 200 });
const options = { getBaseUrl: () => 'http://api.test', getAuthHeaders: () => ({'X-Org-Id':'org-org','X-Project-Id':'dev-project'}) };
describe('installed readonly discovery', () => {
  it('empty original catalog loads actual eight disabled installed modules', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(ok(empty)).mockResolvedValueOnce(ok(installed));
    const result = await new EcommerceWorkshopClient({...options, fetch}).listModules();
    expect(result.count).toBe(8);
    expect(result.items.every(x => x.readiness === 'disabled')).toBe(true);
    expect(fetch.mock.calls[1][0]).toBe('http://api.test/v1/ecommerce-workshop/installed-readonly-modules');
  });
  it('existing nonempty catalog is preserved without a second request', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(ok(installed));
    expect((await new EcommerceWorkshopClient({...options, fetch}).listModules()).count).toBe(8);
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it('rejects cross tenant installed response', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(ok(empty)).mockResolvedValueOnce(ok({...installed,tenant:{orgId:'dev-org',projectId:'dev-project'}}));
    await expect(new EcommerceWorkshopClient({...options, fetch}).listModules()).rejects.toThrow();
  });
});
