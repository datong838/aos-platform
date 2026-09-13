import { describe, expect, it } from 'vitest';
import { parseConfigurationSources, serializeConfigurationStage, parseConfigurationStageReceipt } from './configurationStaging';
const id = '22222222-2222-4222-8222-222222222222';
const hash = 'sha256:' + 'a'.repeat(64);
const role = { authority: 'aip.responsibility_plan_revision', id: 'role', revision: 1, hash };
const policy = { ...role, authority: 'aip.runtime_policy_revision', id: 'policy' };
const target = { installationId: id, installationEtag: 1, generation: id, bindingRevision: 1 };
const catalog = { target, installationRevision: 1, roles: [{ label: '职责', ref: role }], policies: [{ label: '策略', ref: policy }], rolesHasMore: false, policiesHasMore: false };
const tenant = { orgId: 'org-org', projectId: 'dev-project' };
const receipt = { schemaVersion: 'aos.runtime-configuration-stage-status/v1', tenant, requestId: id, requestHash: hash, state: 'requested', revision: 1, deadline: '2026-09-14T01:00:00Z', result: null, failureCode: null };
describe('configuration stage contracts', () => {
  it('retains exact candidates and denies source bodies, duplicates and wrong authorities', () => {
    expect(parseConfigurationSources(catalog)).toEqual(catalog);
    for (const value of [{ ...catalog, roles: [...catalog.roles, ...catalog.roles] }, { ...catalog, policyBody: {} }, { ...catalog, roles: catalog.policies }, { ...catalog, target: null }]) expect(() => parseConfigurationSources(value)).toThrow();
  });
  it('only accepts explicit source requests, without client identity or budget overrides', () => {
    const request = { schemaVersion: 'aos.runtime-configuration-stage/v1' as const, action: 'stage-configuration' as const, target, roleRefs: [role], policyRef: policy, previousRef: null };
    expect(serializeConfigurationStage(request)).toEqual(request);
    expect(() => serializeConfigurationStage({ ...request, roleRefs: [role, role] })).toThrow();
    expect(() => serializeConfigurationStage({ ...request, subject: 'owner' } as typeof request)).toThrow();
  });
  it('rejects cross tenant and mismatched ID, terminal shape and unzoned deadline', () => {
    expect(parseConfigurationStageReceipt(receipt, tenant, true, id)).toEqual(receipt);
    for (const value of [{ ...receipt, tenant: { ...tenant, orgId: 'dev-org' } }, { ...receipt, state: 'succeeded' }, { ...receipt, state: 'expired' }, { ...receipt, deadline: '2026-09-14T01:00:00' }]) expect(() => parseConfigurationStageReceipt(value, tenant, true)).toThrow();
    expect(() => parseConfigurationStageReceipt(receipt, tenant, true, 'other')).toThrow();
  });
});

it('uses POST once and read-only original-key recovery without putting the key in the URL', async () => {
  const { AssetControlClient } = await import('./client');
  const { getTenant } = await import('../tenant');
  const { createIdempotentCommand } = await import('./idempotency');
  const { vi } = await import('vitest');
  const replies = [{ ...receipt, tenant: { orgId: getTenant().orgId, projectId: getTenant().projectId } }];
  const fetch = vi.fn().mockRejectedValueOnce(new Error('response lost')).mockResolvedValueOnce(new Response(JSON.stringify(replies[0]), { status: 200, headers: { 'Content-Type': 'application/json' } }));
  const client = new AssetControlClient({ fetch, getBaseUrl: () => 'https://aos.example.test' });
  const key = createIdempotentCommand().idempotencyKey;
  await expect(client.stageConfiguration({ schemaVersion: 'aos.runtime-configuration-stage/v1', action: 'stage-configuration', target, roleRefs: [role], policyRef: policy, previousRef: null }, key)).rejects.toThrow();
  await client.findConfigurationStage(key);
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(fetch.mock.calls.map(call => call[1].method)).toEqual(['POST', 'GET']);
  expect(fetch.mock.calls[1]![0]).toContain('/configuration-requests/lookup');
  for (const [url, init] of fetch.mock.calls) {
    expect(url).not.toContain(key); expect(new Headers(init.headers).get('Idempotency-Key')).toBe(key);
  }
});
