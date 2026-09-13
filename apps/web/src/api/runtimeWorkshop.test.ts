import { describe, expect, it } from 'vitest';
import { parseRuntimeWorkshopCatalog } from './runtimeWorkshop';

import { tenant, fixture } from './runtimeWorkshop.testFixtures';

describe('runtime resource catalog', () => {
  it('retains exact resource identity', () => {
    const result = parseRuntimeWorkshopCatalog(fixture(), tenant);
    expect(result.items[0].executionEpoch).toBe(3);
    expect(result.items[0].resourceOnly).toBe(true);
  });
  it.each(['tenant','duplicate','hash','route','epoch','permission'])('rejects %s drift', (drift) => {
    const value = fixture();
    if (drift === 'tenant') value.tenant = { ...tenant, orgId: 'dev-org' };
    if (drift === 'duplicate') { value.items.push(value.items[0]); value.count++; }
    if (drift === 'hash') value.items[0].ui.signedResourceUrl += '&contentHash=other';
    if (drift === 'route') value.items[0].ui.initialRoute = '/workshop/other';
    if (drift === 'epoch') value.items[0].executionEpoch = 0;
    if (drift === 'permission') value.items[0].resourceOnly = false;
    expect(() => parseRuntimeWorkshopCatalog(value, tenant)).toThrow();
  });
});
