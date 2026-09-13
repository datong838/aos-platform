import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { ConfigurationStagePanel } from './ConfigurationStagePanel';
import { assetControlClient } from '../../../api/assetControl/client';
import { setAccessToken } from '../../../api/tenant';
import type { RuntimeInstallation } from '../../../api/assetControl/types';
import type { ConfigurationStageReceipt } from '../../../api/assetControl/configurationStaging';
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const id = '22222222-2222-4222-8222-222222222222';
const hash = 'sha256:' + 'a'.repeat(64);
const runtime: RuntimeInstallation = { installationId: id, installationRevision: 1, installationEtag: 1, installationState: 'active', effectiveState: 'disabled', currentOperation: null, ui: null, allowedActions: ['configure'], reasons: [], binding: { generation: id, installationRevision: 1, profileRef: 'python', configRef: null, executionEpoch: 1, desiredState: 'disabled', observedState: 'disabled', enabled: false, operationFence: false, revision: 1 } };
const role = { authority: 'aip.responsibility_plan_revision', id: 'role', revision: 1, hash };
const policy = { ...role, authority: 'aip.runtime_policy_revision', id: 'policy' };
const catalog = { target: { installationId: id, installationEtag: 1, generation: id, bindingRevision: 1 }, installationRevision: 1, roles: [{ label: '职责', ref: role }], policies: [{ label: '策略', ref: policy }], rolesHasMore: false, policiesHasMore: false, submissionConfigured: true };
const receipt: ConfigurationStageReceipt = { schemaVersion: 'aos.runtime-configuration-stage-status/v1', tenant: { orgId: 'org-org', projectId: 'dev-project' }, requestId: id, requestHash: hash, state: 'succeeded', revision: 2, deadline: '2026-09-14T01:00:00Z', result: { configurationId: id, revision: 1, hash }, failureCode: null };
describe('configuration stage product flow', () => {
  let host: HTMLDivElement, root: Root;
  const registered = vi.fn();
  beforeEach(() => {
    host = document.createElement('div'); root = createRoot(host); registered.mockClear();
    vi.spyOn(assetControlClient, 'getConfigurationSources').mockResolvedValue(catalog);
  });
  afterEach(async () => { await act(async () => root.unmount()); vi.restoreAllMocks(); vi.useRealTimers(); setAccessToken(null); });
  async function render(value = runtime) { await act(async () => root.render(<ConfigurationStagePanel state={{ data: value, status: 'ready', stale: false, refreshing: false, error: null, reload: vi.fn() }} offline={false} blocked={false} onRegistered={registered} />)); }
  function button(label: string) { return [...host.querySelectorAll('button')].find(item => item.textContent === label)!; }
  async function choose() { await act(async () => { for (const select of host.querySelectorAll('select')) { select.value = select.options[1]!.value; select.dispatchEvent(new Event('change', { bubbles: true })); } }); }
  it('keeps sources visible but prevents submission when the channel is unconfigured', async () => {
    vi.mocked(assetControlClient.getConfigurationSources).mockResolvedValue({ ...catalog, submissionConfigured: false });
    const post = vi.spyOn(assetControlClient, 'stageConfiguration');
    await render(); await choose();
    expect(host.textContent).toContain('配置登记服务尚未启用');
    expect(button('登记所选配置').disabled).toBe(true);
    await act(async () => button('登记所选配置').click());
    expect(post).not.toHaveBeenCalled();
    expect(host.querySelectorAll('select option').length).toBe(4);
  });
  it('never reposts an unknown outcome; looks up original key and refreshes registered choices', async () => {
    const post = vi.spyOn(assetControlClient, 'stageConfiguration').mockRejectedValue(new Error('lost response'));
    const find = vi.spyOn(assetControlClient, 'findConfigurationStage').mockResolvedValue(receipt);
    await render(); await choose();
    await act(async () => { button('登记所选配置').click(); button('登记所选配置').click(); });
    expect(post).toHaveBeenCalledTimes(1); expect(button('登记所选配置').disabled).toBe(true);
    const key = post.mock.calls[0]![1]; expect(host.textContent).toContain(key);
    await act(async () => button('查询原请求结果').click());
    expect(find).toHaveBeenCalledWith(key); expect(post).toHaveBeenCalledTimes(1); expect(registered).toHaveBeenCalledTimes(1);
    expect(host.textContent).toContain('配置已登记');
  });
  it('ignores a late success after identity changes', async () => {
    let resolve!: (value: ConfigurationStageReceipt) => void;
    vi.spyOn(assetControlClient, 'stageConfiguration').mockImplementation(() => new Promise(done => { resolve = done; }));
    await render(); await choose(); await act(async () => button('登记所选配置').click());
    const oldText = host.querySelector('code')!.textContent;
    await act(async () => setAccessToken('new-identity'));
    await act(async () => resolve(receipt));
    expect(host.textContent).not.toContain(oldText); expect(registered).not.toHaveBeenCalled();
  });
  it('does not submit choices for a changed binding revision', async () => {
    const post = vi.spyOn(assetControlClient, 'stageConfiguration');
    await render(); await choose(); await render({ ...runtime, binding: { ...runtime.binding!, revision: 2 } });
    expect(button('登记所选配置').disabled).toBe(true);
    await act(async () => button('登记所选配置').click()); expect(post).not.toHaveBeenCalled();
  });
  it.each(['rejected', 'expired'] as const)('shows %s without claiming registered', async state => {
    vi.spyOn(assetControlClient, 'stageConfiguration').mockResolvedValue({ ...receipt, state: 'requested', result: undefined, failureCode: undefined });
    const get = vi.spyOn(assetControlClient, 'getConfigurationStage').mockResolvedValue({ ...receipt, state, result: null, failureCode: 'CONFIGURATION_REJECTED' });
    await render(); await choose(); await act(async () => button('登记所选配置').click());
    await act(async () => button('查询原请求结果').click());
    expect(get).toHaveBeenCalledWith(id); expect(registered).not.toHaveBeenCalled();
    expect(host.textContent).toContain(state === 'expired' ? '登记已过期' : '登记被拒绝');
  });
  it('automatically reads a known receipt and refreshes choices without resubmitting', async () => {
    vi.useFakeTimers();
    const post = vi.spyOn(assetControlClient, 'stageConfiguration').mockResolvedValue({ ...receipt, state: 'requested', result: undefined, failureCode: undefined });
    const get = vi.spyOn(assetControlClient, 'getConfigurationStage').mockResolvedValue(receipt);
    await render(); await choose(); await act(async () => button('登记所选配置').click());
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    expect(get).toHaveBeenCalledTimes(1); expect(registered).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(60000); });
    expect(get).toHaveBeenCalledTimes(1); expect(post).toHaveBeenCalledTimes(1);
  });
  it('bounds unknown-result polling and never creates a replacement key', async () => {
    vi.useFakeTimers();
    const post = vi.spyOn(assetControlClient, 'stageConfiguration').mockRejectedValue(new Error('lost'));
    const find = vi.spyOn(assetControlClient, 'findConfigurationStage').mockRejectedValue(new Error('unavailable'));
    await render(); await choose(); await act(async () => button('登记所选配置').click());
    await act(async () => { await vi.advanceTimersByTimeAsync(120000); });
    expect(find).toHaveBeenCalledTimes(10); expect(post).toHaveBeenCalledTimes(1);
    expect(new Set(find.mock.calls.map(call => call[0])).size).toBe(1);
    expect(host.textContent).toContain('自动查询已暂停');
  });
  it('stops automatic queries when the identity changes', async () => {
    vi.useFakeTimers();
    vi.spyOn(assetControlClient, 'stageConfiguration').mockRejectedValue(new Error('lost'));
    const find = vi.spyOn(assetControlClient, 'findConfigurationStage').mockResolvedValue(receipt);
    await render(); await choose(); await act(async () => button('登记所选配置').click());
    await act(async () => setAccessToken('changed-before-poll'));
    await act(async () => { await vi.advanceTimersByTimeAsync(60000); });
    expect(find).not.toHaveBeenCalled();
  });

  it('does not overlap queries when readback is slow', async () => {
    vi.useFakeTimers();
    vi.spyOn(assetControlClient, 'stageConfiguration').mockRejectedValue(new Error('lost'));
    let resolve!: (value: ConfigurationStageReceipt) => void;
    const find = vi.spyOn(assetControlClient, 'findConfigurationStage').mockImplementation(() => new Promise(done => { resolve = done; }));
    await render(); await choose(); await act(async () => button('登记所选配置').click());
    await act(async () => { await vi.advanceTimersByTimeAsync(30000); });
    expect(find).toHaveBeenCalledTimes(1); expect(button('查询原请求结果').disabled).toBe(true);
    expect(host.textContent).toContain(`原登记安装：${id}`);
    await act(async () => resolve(receipt)); expect(registered).toHaveBeenCalledTimes(1);
  });

});
