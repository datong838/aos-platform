import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { apiGetAuthoritative, apiPostUnqueued } from '../../api/client';
import { NetworkProposalCreationPanel, restoreNetworkReference } from './NetworkProposalCreationPanel';

vi.mock('../../api/client', () => ({ apiGetAuthoritative: vi.fn(), apiPostUnqueued: vi.fn() }));
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const input = { policyId: 'policy-1', revision: '1', expectedHeadVersion: '0' };
const build = () => ({ body: { policyId: 'policy-1', revision: 1 }, expectedHeadVersion: 0 });
function button(host: HTMLElement, name: string) {
  return [...host.querySelectorAll<HTMLButtonElement>('button')].find(b => b.textContent === name)!;
}
async function expiry(host: HTMLElement) {
  const date = new Date(Date.now()+5*60_000);
  const local = new Date(date.getTime()-date.getTimezoneOffset()*60_000).toISOString().slice(0, 16);
  await act(async () => {
    const field = host.querySelector('input')!;
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(field, local);
    field.dispatchEvent(new Event('input', { bubbles: true }));
  });
}
describe('network proposal creation product', () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => {
    vi.resetAllMocks(); window.history.replaceState(null, '', '/aip/model-runtime');
    host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host);
  });
  afterEach(() => { act(() => root.unmount()); host.remove(); });
  async function mount(value = input) {
    await act(async () => root.render(<NetworkProposalCreationPanel input={value} buildCandidate={build} />));
  }
  it('queries first, never resubmits unknown and preserves only safe URL references', async () => {
    vi.mocked(apiGetAuthoritative).mockResolvedValueOnce({ status: 'not_attempted' }).mockResolvedValue({ status: 'unresolved' });
    vi.mocked(apiPostUnqueued).mockRejectedValue(new Error('response lost'));
    await mount(); await expiry(host);
    expect(button(host, '提交审批提案').disabled).toBe(true);
    await act(async () => button(host, '查询原创建请求').click());
    expect(button(host, '提交审批提案').disabled).toBe(false);
    await act(async () => { button(host, '提交审批提案').click(); button(host, '提交审批提案').click(); });
    expect(apiPostUnqueued).toHaveBeenCalledTimes(1);
    expect(button(host, '提交审批提案').disabled).toBe(true);
    await act(async () => button(host, '查询原创建请求').click());
    expect(apiPostUnqueued).toHaveBeenCalledTimes(1);
    expect(restoreNetworkReference(window.location.search)).toEqual(input);
    expect(window.location.search).not.toContain('expires');
    expect(apiPostUnqueued).toHaveBeenCalledWith('/v1/aip/runtime-guard-policies/networks/proposal-intent',
      { candidate: build().body, expiresAt: expect.any(String) }, { 'If-Match': '0' });
  });
  it('refresh restores references but cannot create before authoritative query', async () => {
    vi.mocked(apiGetAuthoritative).mockResolvedValue({ status: 'unresolved' });
    await mount();
    await act(async () => button(host, '查询原创建请求').click());
    const restored = restoreNetworkReference(window.location.search);
    act(() => root.unmount()); root = createRoot(host);
    await mount({ ...input, ...restored }); await expiry(host);
    expect(button(host, '提交审批提案').disabled).toBe(true);
    await act(async () => button(host, '查询原创建请求').click());
    expect(button(host, '提交审批提案').disabled).toBe(true);
    expect(apiPostUnqueued).not.toHaveBeenCalled();
  });
  it('observed links to the canonical inbox without activation', async () => {
    vi.mocked(apiGetAuthoritative).mockResolvedValue({ status: 'observed', proposalId: 'proposal/1' });
    await mount();
    await act(async () => button(host, '查询原创建请求').click());
    expect(host.querySelector('a')?.getAttribute('href')).toBe('/aip/drafts?proposal=proposal%2F1');
    expect(host.textContent).toContain('不表示批准或生效');
    expect(apiPostUnqueued).not.toHaveBeenCalled();
  });
  it('candidate changes and identity events discard late responses', async () => {
    let resolve!: (value: unknown) => void;
    vi.mocked(apiGetAuthoritative).mockImplementation(() => new Promise(r => { resolve = r; }));
    await mount();
    await act(async () => button(host, '查询原创建请求').click());
    await mount({ ...input, policyId: 'policy-2' });
    await act(async () => resolve({ status: 'observed', proposalId: 'stale' }));
    expect(host.querySelector('a')).toBeNull();
    await act(async () => button(host, '查询原创建请求').click());
    await act(async () => window.dispatchEvent(new Event('aos-auth-updated')));
    await act(async () => resolve({ status: 'not_attempted' }));
    await expiry(host);
    expect(button(host, '提交审批提案').disabled).toBe(true);
  });
  it('malformed query and post not_attempted fail closed', async () => {
    vi.mocked(apiGetAuthoritative).mockResolvedValueOnce({ status: 'observed' }).mockResolvedValue({ status: 'not_attempted' });
    vi.mocked(apiPostUnqueued).mockResolvedValue({ status: 'not_attempted' });
    await mount(); await expiry(host);
    await act(async () => button(host, '查询原创建请求').click());
    expect(button(host, '提交审批提案').disabled).toBe(true);
    await act(async () => button(host, '查询原创建请求').click());
    await act(async () => button(host, '提交审批提案').click());
    expect(button(host, '提交审批提案').disabled).toBe(true);
    expect(host.textContent).toContain('查询原请求');
  });
});
