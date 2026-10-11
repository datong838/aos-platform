import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { assetControlClient } from "../../api/assetControl/client";
import type { InstallationListResponse, RuntimeInstallation } from "../../api/assetControl/types";
import { WorkshopInstallationDiagnosis } from "./WorkshopInstallationDiagnosis";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const id = "ccdcb0f0-1040-4bc6-aa0c-d045f5689813";
const list: InstallationListResponse = { items: [{ installationId: id, displayName: "栖月汇八工作台", state: "approved", currentRevision: 3, activeRevision: null, previousActiveRevision: null, etagVersion: 3, createdAt: "2026-09-27T00:00:00Z", updatedAt: "2026-09-27T00:00:00Z" }], total: 1, limit: 5, offset: 0 };
const runtime: RuntimeInstallation = { installationId: id, installationRevision: 3, installationEtag: 3, installationState: "approved", effectiveState: "not_prepared", binding: null, currentOperation: null, ui: null, allowedActions: ["runtime-apply"], reasons: [], preparationExecutable: false };
let host: HTMLDivElement; let root: Root;
beforeEach(() => { host = document.createElement("div"); document.body.append(host); root = createRoot(host); vi.spyOn(assetControlClient, "listInstallations").mockResolvedValue(list); vi.spyOn(assetControlClient, "getRuntimeInstallation").mockResolvedValue(runtime); });
afterEach(() => { act(() => root.unmount()); host.remove(); vi.restoreAllMocks(); });
async function render(identity = "org-org:dev-project:user:1") { await act(async () => root.render(<MemoryRouter><WorkshopInstallationDiagnosis key={identity} /></MemoryRouter>)); }

it("shows approved installation and verified absence of runtime preparation without activation controls", async () => {
  await render();
  expect(host.textContent).toContain("栖月汇八工作台");
  expect(host.textContent).toContain("已批准");
  expect(host.textContent).toContain("运行资源尚未准备");
  expect(host.querySelector('a[href="/apollo/assets"]')).not.toBeNull();
  expect(assetControlClient.listInstallations).toHaveBeenCalledWith({ limit: 5, offset: 0 });
  expect(host.textContent).not.toContain("启用运行实例");
});
it("does not turn a failed list read into an uninstalled claim", async () => {
  vi.mocked(assetControlClient.listInstallations).mockRejectedValue(new Error("offline"));
  await render();
  expect(host.textContent).toContain("安装状态尚未核验");
  expect(host.textContent).not.toContain("未安装");
  expect(assetControlClient.getRuntimeInstallation).not.toHaveBeenCalled();
});
it("clears old scope and rejects its late response after identity remount", async () => {
  let finish!: (value: InstallationListResponse) => void;
  vi.mocked(assetControlClient.listInstallations).mockImplementationOnce(() => new Promise(resolve => { finish = resolve; })).mockResolvedValueOnce({ items: [], total: 0, limit: 5, offset: 0 });
  await render("orgA"); await render("orgB");
  await act(async () => finish(list));
  expect(host.textContent).not.toContain("栖月汇八工作台");
  expect(host.textContent).toContain("当前账号没有可见安装记录");
  expect(assetControlClient.getRuntimeInstallation).not.toHaveBeenCalled();
});
it("rejects runtime summary from a different installation revision", async () => {
  vi.mocked(assetControlClient.getRuntimeInstallation).mockResolvedValue({ ...runtime, installationRevision: 2 });
  await render();
  expect(host.textContent).toContain("运行状态尚未核验");
  expect(host.textContent).not.toContain("运行资源尚未准备");
});
it("keeps runtime read failure unknown while preserving the verified installation label", async () => {
  vi.mocked(assetControlClient.getRuntimeInstallation).mockRejectedValue(new Error("denied"));
  await render();
  expect(host.textContent).toContain("已批准");
  expect(host.textContent).toContain("运行状态尚未核验");
  expect(host.textContent).not.toContain("运行资源尚未准备");
});
