import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiGetAuthoritative, apiPostUnqueued } from "../../api/client";
import { PipelineRegistrationPanel } from "./PipelineRegistrationPanel";

vi.mock("../../api/client", () => ({ apiGetAuthoritative: vi.fn(), apiPostUnqueued: vi.fn() }));
vi.mock("../../api/tenant", () => ({
  getTenant: () => ({ orgId: "org-org", projectId: "dev-project", subject: "operator" }),
  getAuthRevision: () => 0,
}));

describe("first pipeline registration", () => {
  let host: HTMLDivElement;
  let root: Root;
  const source = { id: "file-source", name: "Approved file", configurationRevision: "11111111-1111-4111-8111-111111111111" };

  beforeEach(() => {
    localStorage.clear(); vi.clearAllMocks();
    host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
  });
  afterEach(() => { act(() => root.unmount()); host.remove(); localStorage.clear(); });
  async function render() {
    await act(async () => root.render(<MemoryRouter><PipelineRegistrationPanel onRegistered={vi.fn()} /></MemoryRouter>));
  }
  function button(label: string) {
    return Array.from(host.querySelectorAll("button")).find(item => item.textContent?.includes(label)) as HTMLButtonElement;
  }
  async function fill() {
    await act(async () => button("新建管道").click());
    const values = [["select", "file-source"], ["input[aria-label='管道 ID']", "first-pipeline"],
      ["input[aria-label='管道名称']", "首条管道"]] as const;
    for (const [selector, value] of values) {
      await act(async () => {
        const input = host.querySelector(selector) as HTMLInputElement | HTMLSelectElement;
        const prototype = input instanceof HTMLSelectElement ? HTMLSelectElement.prototype : HTMLInputElement.prototype;
        Object.getOwnPropertyDescriptor(prototype, "value")!.set!.call(input, value);
        input.dispatchEvent(new Event(input instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }));
      });
    }
  }

  it("offers only a source-management link with no current source", async () => {
    vi.mocked(apiGetAuthoritative).mockResolvedValue({ items: [] });
    await render();
    expect(host.textContent).toContain("当前没有可用的正式来源");
    expect(host.querySelector('a[href="/data"]')).not.toBeNull();
    expect(button("登记管道配置")).toBeUndefined();
    expect(apiPostUnqueued).not.toHaveBeenCalled();
  });

  it("freezes a lost response and reconciles only the original receipt", async () => {
    vi.mocked(apiGetAuthoritative).mockResolvedValue({ items: [source] });
    vi.mocked(apiPostUnqueued).mockRejectedValue(new Error("connection lost"));
    await render();
    await fill();
    await act(async () => button("登记管道配置").click());
    expect(apiPostUnqueued).toHaveBeenCalledTimes(1);
    expect(host.textContent).toContain("禁止再次提交");
    const [path, body, headers] = vi.mocked(apiPostUnqueued).mock.calls[0]!;
    expect(path).toBe("/v1/pipeline-registrations");
    expect(body).toMatchObject({ pipelineId: "first-pipeline", sourceId: "file-source",
      sourceConfigurationRevision: source.configurationRevision });
    const key = (headers as Record<string, string>)["Idempotency-Key"];
    expect(key).toBeTruthy();
    vi.mocked(apiGetAuthoritative).mockRejectedValueOnce(new Error("not found"));
    await act(async () => button("只读核对原回执").click());
    expect(apiGetAuthoritative).toHaveBeenLastCalledWith(
      `/v1/pipeline-registrations/first-pipeline/receipt?key=${encodeURIComponent(key)}`);
    expect(apiPostUnqueued).toHaveBeenCalledTimes(1);
    expect(host.textContent).toContain("保持冻结");
  });
});
