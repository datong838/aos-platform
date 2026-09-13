import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import html from '../../../../../bundles/solutions/ecommerce-growth/frontend/index.html?raw';

const script = html.match(/<script>([\s\S]*?)<\/script>/)![1];
const identity = { installationId: '11111111-1111-4111-8111-111111111111', generation: '22222222-2222-4222-8222-222222222222', executionEpoch: 3 };
const nonce = 'a'.repeat(48);
const scope = { orgId: 'org-org', projectId: 'dev-project' };
const ref = { resourceType: 'BusinessInvestigationCaseRevision', resourceId: 'case-1', revision: 1, contentHash: 'sha256:' + 'a'.repeat(64) };
function boot(changes: Record<string, string> = {}) {
  document.body.innerHTML = html.replace(/<script>[\s\S]*?<\/script>/, '');
  const listeners = new Map<string, (event: any) => void>();
  const parent = { postMessage: vi.fn() };
  const port = { onmessage: null as null | ((event: any) => void), start: vi.fn(), close: vi.fn(), postMessage: vi.fn() };
  const window = { parent, location: { hash: '#' + new URLSearchParams({ aosNonce: nonce, installationId: identity.installationId,
    generation: identity.generation, executionEpoch: String(identity.executionEpoch), initialRoute: '/workshop/analyst', ...changes }) },
    addEventListener: (name: string, fn: (event: any) => void) => listeners.set(name, fn),
    removeEventListener: (name: string) => listeners.delete(name) };
  // Execute only the checked-in page script against a controlled transport.
  new Function('window', 'document', 'URLSearchParams', 'setTimeout', 'clearTimeout', script)(
    window, document, URLSearchParams, setTimeout, clearTimeout);
  const connect = (override = {}, source = parent) => listeners.get('message')?.({ source,
    data: { version: 1, type: 'aos:connected', nonce, ...identity, ...override }, ports: [port] });
  const send = (result: unknown, ok = true) => port.onmessage?.({ data: { version: 1, type: 'response',
    requestId: port.postMessage.mock.calls.at(-1)![0].requestId, ok, result } });
  return { parent, port, connect, send, listeners };
}
function result(cases: unknown[] = []) {
  return { schemaVersion: 'aos.runtime-ui-read-status/v1', tenant: scope, state: 'succeeded', result: {
    schemaVersion: 'aos.analyst-workspace-view/v1', tenant: scope, executionAllowed: false,
    cutoffAt: '2026-09-13T12:00:00Z', cases, caseCount: cases.length, runCount: 0, truncated: false } };
}
const button = () => document.querySelector('button')!;

describe('signed analyst page', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => { vi.clearAllTimers(); vi.useRealTimers(); document.body.replaceChildren(); });
  it('uses the bootstrap handshake then one bounded read, with no in-flight duplicate', () => {
    const page = boot();
    expect(page.parent.postMessage).toHaveBeenCalledWith({ version: 1, type: 'aos:hello', nonce, ...identity }, '*');
    page.connect(); button().click();
    expect(page.port.postMessage).toHaveBeenCalledTimes(1);
    expect(page.port.postMessage.mock.calls[0][0]).toMatchObject({ type: 'read', ...identity, sequence: 1,
      operationId: 'analyst_workspace_view_v1', input: { caseLimit: 20, runLimit: 5 } });
    page.send(result());
    expect(document.body.textContent).toContain('当前没有可展示的经营事项');
    button().click(); expect(page.port.postMessage.mock.calls[1][0].sequence).toBe(2);
  });
  it('renders sourced titles as text and never HTML', () => {
    const page = boot(); page.connect();
    page.send(result([{ title: '<img src=x onerror=alert(1)>', lifecycle: 'ACTIVE', analysisType: 'structure', caseRef: ref, runs: [] }]));
    expect(document.querySelector('#results')!.textContent).toContain('<img src=x onerror=alert(1)>');
    expect(document.querySelector('#results img')).toBeNull();
    expect(document.querySelector('pre')!.textContent).toContain(ref.contentHash);
  });
  it('ignores other windows and refuses wrong parent identity without a read', () => {
    const page = boot(); page.connect({}, {} as any);
    expect(page.port.postMessage).not.toHaveBeenCalled();
    page.connect({ generation: identity.installationId });
    expect(button().disabled).toBe(true);
    expect(page.port.postMessage).not.toHaveBeenCalled();
  });
  it('rejects an invalid bootstrap without contacting parent', () => {
    const page = boot({ initialRoute: '/workshop/customer' });
    expect(page.parent.postMessage).not.toHaveBeenCalled();
    expect(document.body.textContent).toContain('启动信息不完整');
  });
  it('continues only after an explicit click when the host has no result', () => {
    const page = boot(); page.connect(); page.send(null, false);
    expect(button().textContent).toBe('继续查看本次读取');
    vi.advanceTimersByTime(80000); expect(page.port.postMessage).toHaveBeenCalledTimes(1);
    button().click(); expect(page.port.postMessage).toHaveBeenCalledTimes(2);
  });
  it('closes on timeout without resending and ignores late data', () => {
    const page = boot(); page.connect(); const late = page.port.onmessage!;
    vi.advanceTimersByTime(90000);
    expect(page.port.close).toHaveBeenCalledOnce(); button().click();
    expect(page.port.postMessage).toHaveBeenCalledTimes(1);
    late({ data: { version: 1, type: 'response', requestId: 'analyst-read-1', ok: true, result: result() } });
    expect(document.querySelector('#results')!.children.length).toBe(0);
  });
  it('closes on page exit and malformed results without retaining old content', () => {
    const page = boot(); page.connect(); page.send(result());
    page.listeners.get('pagehide')?.({});
    expect(page.port.close).toHaveBeenCalledOnce();
    expect(document.querySelector('#results')!.children.length).toBe(0);
    const next = boot(); next.connect(); next.send({ ...result(), tenant: { ...scope, orgId: 'other' } });
    expect(next.port.close).toHaveBeenCalledOnce(); expect(button().disabled).toBe(true);
  });
});
