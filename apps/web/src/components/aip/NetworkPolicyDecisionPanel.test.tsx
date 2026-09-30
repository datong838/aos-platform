import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NetworkPolicyDecisionPanel } from "./NetworkPolicyDecisionPanel";
import { type NetworkDecisionSdk } from "../../api/aipActions/networkDecision";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const proposal = { id: "p-1", version: 1, proposalHash: "a".repeat(64), status: "drafted" as const,
  expiresAt: "2027-08-12T00:00:00Z", payload: { candidate: { policyId: "network-1", revision: 1,
    allowedHosts: ["api.agnes-ai.cn"], allowedPorts: [443], tlsRequired: true,
    egressPolicyRef: { assetId: "egress-1", revision: 2, contentHash: "b".repeat(64) } } } };
function button(host: HTMLElement, text: string) {
  const b = [...host.querySelectorAll<HTMLButtonElement>("button")].find(b => b.textContent?.includes(text));
  if (!b) throw new Error("missing button "+text);
  return b;
}
async function reason(host: HTMLElement) {
  const input = host.querySelector('input')!;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, '核对精确策略');
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });
}
describe("network policy decision panel", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { host = document.createElement('div'); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });
  it("unknown blocks a second submission and refresh only queries the original request", async () => {
    const sdk = { inquire: vi.fn().mockResolvedValueOnce({ status: 'not_attempted' }).mockResolvedValue({ status: 'unresolved' }),
      submit: vi.fn().mockRejectedValue(new Error('disconnected')) } as unknown as NetworkDecisionSdk;
    await act(async () => root.render(<NetworkPolicyDecisionPanel proposal={proposal} disabled={false} sdk={sdk} onObserved={() => {}} />));
    await reason(host);
    expect(button(host, '批准网络策略').disabled).toBe(false);
    await act(async () => button(host, '批准网络策略').click());
    expect(button(host, '批准网络策略').disabled).toBe(true);
    await act(async () => button(host, '查询原审批请求').click());
    expect(sdk.submit).toHaveBeenCalledTimes(1);
    expect(sdk.inquire).toHaveBeenCalledTimes(2);
    expect(host.textContent).toContain('结果尚未确认');
    expect(host.textContent).toContain('api.agnes-ai.cn');
  });
  it("remount queries server attempt and never resubmits", async () => {
    const sdk = { inquire: vi.fn().mockResolvedValue({ status: 'unresolved' }), submit: vi.fn() } as unknown as NetworkDecisionSdk;
    await act(async () => root.render(<NetworkPolicyDecisionPanel proposal={proposal} disabled={false} sdk={sdk} onObserved={() => {}} />));
    await reason(host);
    expect(button(host, '批准网络策略').disabled).toBe(true);
    act(() => root.unmount());
    root = createRoot(host);
    await act(async () => root.render(<NetworkPolicyDecisionPanel proposal={proposal} disabled={false} sdk={sdk} onObserved={() => {}} />));
    expect(sdk.inquire).toHaveBeenCalledTimes(2);
    expect(button(host, '批准网络策略').disabled).toBe(true);
    expect(sdk.submit).not.toHaveBeenCalled();
  });
  it("observed decision refreshes authoritative detail without claiming activation", async () => {
    const sdk = { inquire: vi.fn().mockResolvedValue({ status: 'not_attempted' }),
      submit: vi.fn().mockResolvedValue({ status: 'observed', eventId: 'event-1', decision: 'approved' }) } as unknown as NetworkDecisionSdk;
    const observed = vi.fn();
    await act(async () => root.render(<NetworkPolicyDecisionPanel proposal={proposal} disabled={false} sdk={sdk} onObserved={observed} />));
    await reason(host);
    await act(async () => button(host, '批准网络策略').click());
    expect(observed).toHaveBeenCalledTimes(1);
    expect(host.textContent).toContain('event-1');
    expect(host.textContent).toContain('批准不代表已生效');
    expect(button(host, '批准网络策略').disabled).toBe(true);
  });
  it("late response after identity switch cannot authorize or refresh the prior proposal", async () => {
    let resolve!: (x: unknown) => void;
    const sdk = { inquire: vi.fn().mockImplementation(() => new Promise(r => { resolve = r; })), submit: vi.fn() } as unknown as NetworkDecisionSdk;
    const observed = vi.fn();
    await act(async () => root.render(<NetworkPolicyDecisionPanel proposal={proposal} disabled={false} sdk={sdk} onObserved={observed} />));
    await act(async () => window.dispatchEvent(new Event('aos-auth-updated')));
    await act(async () => resolve({ status: 'observed', eventId: 'e', decision: 'approved' }));
    expect(observed).not.toHaveBeenCalled();
    expect(host.textContent).toContain('身份已变化');
    expect(sdk.submit).not.toHaveBeenCalled();
  });
});
