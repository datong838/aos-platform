import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PipelineAdmissionPanel } from "./PipelineAdmissionPanel";
import { useJsonGet } from "./shared";

vi.mock("../../api/tenant", () => ({
  getTenant: () => ({ orgId: "org-org", projectId: "dev-project", subject: "operator" }),
  getAuthRevision: () => 0,
}));
vi.mock("./shared", () => ({ useJsonGet: vi.fn() }));

describe("source selection product readiness", () => {
  let host: HTMLDivElement;
  let root: Root;
  beforeEach(() => {
    host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
  });
  afterEach(() => { act(() => root.unmount()); host.remove(); vi.clearAllMocks(); });
  async function render() {
    await act(async () => root.render(<MemoryRouter><PipelineAdmissionPanel pipelineId="P01" /></MemoryRouter>));
  }

  it("shows an actionable source-registration blocker but no approval action", async () => {
    vi.mocked(useJsonGet).mockReturnValue({
      data: { pipelineId: "P01", formallyRegistered: true, sourceId: "source-one",
        sourceConfigurationRevision: null, graphRevision: null, ready: false,
        blockers: ["SOURCE_CONFIGURATION_CHANGED"], nextAction: "REGISTER_SOURCE" },
      err: null, loading: false, reload: vi.fn(), setData: vi.fn(), setErr: vi.fn(),
    });
    await render();
    expect(useJsonGet).toHaveBeenCalledWith(
      "/v1/pipelines/P01/source-selection-readiness", { authoritative: true });
    expect(host.textContent).toContain("来源配置不存在或已变化");
    expect(host.querySelector('a[href="/data"]')).not.toBeNull();
    expect(Array.from(host.querySelectorAll("button")).map(button => button.textContent))
      .toEqual(["刷新当前条件"]);
  });

  it("fails closed when the current read is unavailable", async () => {
    vi.mocked(useJsonGet).mockReturnValue({
      data: null, err: "offline", loading: false, reload: vi.fn(),
      setData: vi.fn(), setErr: vi.fn(),
    });
    await render();
    expect(host.textContent).toContain("当前条件未核清，不能提交审批");
    expect(host.querySelectorAll("a")).toHaveLength(0);
  });

  it("distinguishes approved installation from active runtime without approval action", async () => {
    vi.mocked(useJsonGet).mockReturnValue({
      data: { pipelineId: "P01", formallyRegistered: false, sourceId: null,
        sourceConfigurationRevision: null, graphRevision: null,
        installationId: "ccdcb0f0-1040-4bc6-aa0c-d045f5689813",
        installationActive: false, ready: false,
        blockers: ["PIPELINE_NOT_FORMALLY_REGISTERED", "INSTALLATION_NOT_ACTIVE"],
        nextAction: "REGISTER_PIPELINE" },
      err: null, loading: false, reload: vi.fn(), setData: vi.fn(), setErr: vi.fn(),
    });
    await render();
    expect(host.textContent).toContain("已批准不等于可运行");
    expect(host.textContent).toContain("尚未完成正式登记");
    expect(host.querySelector('a[href="/data/pipelines"]')).not.toBeNull();
    expect(Array.from(host.querySelectorAll("button")).map(button => button.textContent))
      .toEqual(["刷新当前条件"]);
  });
});
