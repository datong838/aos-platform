import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const { apiGet, apiPost, apiDelete } = vi.hoisted(() => ({ apiGet: vi.fn(), apiPost: vi.fn(), apiDelete: vi.fn() }));
vi.mock("../api/client", () => ({ apiGet, apiPost, apiDelete }));

import { WorkspaceMembersPage } from "./WorkspaceMembersPage";

describe("WorkspaceMembersPage current truth", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => {
    apiGet.mockImplementation(async (path: string) => path === "/v1/audit"
      ? { items: [{ id: "a1", action: "org.enter", actorId: "user:dev", ts: "2026-08-07" }] }
      : { items: [{ subject: "user:dev", role: "owner", displayName: "本机开发者", title: "本机登录账号" }] });
    host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
  });
  afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.clearAllMocks(); });

  it("角色中文展示且移除先确认不直接写入", async () => {
    await act(async () => root.render(createElement(MemoryRouter, null, createElement(WorkspaceMembersPage))));
    await act(async () => void await Promise.resolve());
    expect(host.textContent).toContain("负责人");
    expect(host.textContent).not.toContain("alice@acme.example");
    const remove = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "移除")!;
    await act(async () => remove.click());
    expect(host.textContent).toContain("确认移除");
    expect(host.textContent).toContain("取消");
    expect(apiDelete).not.toHaveBeenCalled();
    expect(host.querySelector<HTMLDetailsElement>("details")?.open).toBe(false);
  });
});
