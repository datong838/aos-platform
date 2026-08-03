import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  INSTALLATION_DETAIL_FIXTURE,
  INSTALLATION_DRAFT_FIXTURE,
} from "../../../api/assetControl/installationFixtures";
import { InstallationActionPanel, type InstallationActionPanelProps } from "./InstallationActionPanel";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("InstallationActionPanel", () => {
  let host: HTMLDivElement;
  let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });

  const defaults: InstallationActionPanelProps = {
    installation: INSTALLATION_DRAFT_FIXTURE,
    ready: true,
    stale: false,
    refreshing: false,
    offline: false,
    subject: "operator@example.test",
    roles: ["asset-installer"],
    selectedAction: null,
    pendingAction: null,
    onSelectedActionChange: vi.fn(),
    onConfirm: vi.fn(),
  };

  async function render(overrides: Partial<InstallationActionPanelProps> = {}) {
    const props = { ...defaults, onSelectedActionChange: vi.fn(), onConfirm: vi.fn(), ...overrides };
    await act(async () => root.render(<InstallationActionPanel {...props} />));
    return props;
  }

  it("只显示当前状态可达动作，并通过受控 callback 打开", async () => {
    const props = await render();
    const button = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((item) => item.textContent === "提交审批");
    if (!button) throw new Error("submit missing");
    expect(button.disabled).toBe(false);
    await act(async () => button.click());
    expect(props.onSelectedActionChange).toHaveBeenCalledWith("submit");
    expect(host.textContent).not.toContain("批准");
  });

  it("pending、stale、offline 和 maker-checker 均禁用入口", async () => {
    await render({ pendingAction: "submit" });
    expect(host.querySelector<HTMLButtonElement>("button")?.disabled).toBe(true);
    await render({ pendingAction: null, stale: true });
    expect(host.querySelector<HTMLButtonElement>("button")?.disabled).toBe(true);
    await render({ stale: false, offline: true });
    expect(host.querySelector<HTMLButtonElement>("button")?.disabled).toBe(true);

    const submitted = structuredClone(INSTALLATION_DRAFT_FIXTURE);
    submitted.state = "submitted";
    submitted.current.state = "submitted";
    await render({
      installation: submitted,
      offline: false,
      subject: submitted.current.requestedBy,
      roles: ["admin"],
    });
    const decisions = Array.from(host.querySelectorAll<HTMLButtonElement>("button"));
    expect(decisions).toHaveLength(2);
    expect(decisions.every((button) => button.disabled)).toBe(true);
  });

  it("展示服务端 pointer 和最近 evidence，不创建 evidence 输入", async () => {
    await render({ installation: INSTALLATION_DETAIL_FIXTURE });
    expect(host.textContent).toContain("Active revision");
    expect(host.textContent).toContain("verification / valid");
    expect(host.textContent).toContain("evidence://installations/verification.json");
    expect(host.querySelector("input[name*=evidence]")).toBeNull();
    expect(host.querySelector("textarea[name*=evidence]")).toBeNull();
  });

  it("终态不显示动作", async () => {
    const rejected = structuredClone(INSTALLATION_DRAFT_FIXTURE);
    rejected.state = "rejected";
    rejected.current.state = "rejected";
    await render({ installation: rejected });
    expect(host.textContent).toContain("终态，没有可执行动作");
  });

  it("拒绝显示当前状态不可达或已失效的受控 dialog", async () => {
    await render({ selectedAction: "approve" });
    expect(host.querySelector('[role="dialog"]')).toBeNull();
    await render({ selectedAction: "submit", stale: true });
    expect(host.querySelector('[role="dialog"]')).toBeNull();
  });
});
