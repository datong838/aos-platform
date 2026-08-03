import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  INSTALLATION_DETAIL_FIXTURE,
  INSTALLATION_DRAFT_FIXTURE,
} from "../../../api/assetControl/installationFixtures";
import type { InstallationResponse } from "../../../api/assetControl/types";
import { InstallationActionDialog } from "./InstallationActionDialog";
import type { InstallationAction } from "./installationActions";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

function installationInState(state: InstallationResponse["state"]): InstallationResponse {
  const installation = structuredClone(INSTALLATION_DRAFT_FIXTURE);
  installation.state = state;
  installation.current.state = state;
  return installation;
}

describe("InstallationActionDialog", () => {
  let host: HTMLDivElement;
  let root: Root;
  beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); });

  async function render(action: InstallationAction, installation = installationInState("submitted"), pending = false) {
    const onConfirm = vi.fn();
    await act(async () => root.render(
      <InstallationActionDialog action={action} installation={installation} pending={pending} onCancel={vi.fn()} onConfirm={onConfirm} />,
    ));
    return onConfirm;
  }

  it("approve 只展示四个 hash，确认回调不携带 hash", async () => {
    const installation = installationInState("submitted");
    const onConfirm = await render("approve", installation);
    const hashSection = host.querySelector('[aria-label="批准 hash 只读确认"]');
    expect(hashSection?.querySelectorAll("code")).toHaveLength(4);
    expect(hashSection?.querySelector("input")).toBeNull();
    expect(host.querySelector(`input[value="${installation.current.lockHash}"]`)).toBeNull();

    const confirm = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent?.includes("确认批准"));
    const acknowledgement = host.querySelector<HTMLInputElement>('input[type="checkbox"]');
    if (!confirm || !acknowledgement) throw new Error("approve controls missing");
    expect(confirm.disabled).toBe(true);
    await act(async () => acknowledgement.click());
    expect(confirm.disabled).toBe(false);
    await act(async () => confirm.click());
    expect(onConfirm).toHaveBeenCalledWith({ action: "approve" });
  });

  it("reject/rollback 只回传 trim 后的合法 reason，并拒绝控制字符", async () => {
    const onConfirm = await render("rollback", structuredClone(INSTALLATION_DETAIL_FIXTURE));
    const textarea = host.querySelector<HTMLTextAreaElement>('textarea[aria-label="回滚原因"]');
    const confirm = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent?.includes("确认回滚"));
    if (!textarea || !confirm) throw new Error("rollback controls missing");
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set?.call(textarea, "  价格恢复  ");
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
      textarea.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(confirm.disabled).toBe(false);
    await act(async () => confirm.click());
    expect(onConfirm).toHaveBeenCalledWith({ action: "rollback", reason: "价格恢复" });

    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set?.call(textarea, "第一行\n第二行");
      textarea.dispatchEvent(new Event("input", { bubbles: true }));
      textarea.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(confirm.disabled).toBe(true);
    expect(host.textContent).toContain("不能包含控制字符");
  });

  it.each(["submit", "apply", "verify"] as const)("%s 无输入且只回传动作", async (action) => {
    const onConfirm = await render(action, installationInState(action === "submit" ? "draft" : action === "apply" ? "approved" : "applied"));
    expect(host.querySelector("textarea")).toBeNull();
    const confirm = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.classList.contains("btn-primary"));
    if (!confirm) throw new Error("confirm missing");
    await act(async () => confirm.click());
    expect(onConfirm).toHaveBeenCalledWith({ action });
  });

  it("pending 禁止确认、取消和表单输入", async () => {
    await render("rollback", structuredClone(INSTALLATION_DETAIL_FIXTURE), true);
    expect(Array.from(host.querySelectorAll<HTMLButtonElement>("button")).every((button) => button.disabled)).toBe(true);
    expect(host.querySelector<HTMLTextAreaElement>("textarea")?.disabled).toBe(true);
  });
});
