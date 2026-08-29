// @vitest-environment jsdom
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const { apiGet, apiPatch } = vi.hoisted(() => ({ apiGet: vi.fn(), apiPatch: vi.fn() }));
vi.mock("../api/client", () => ({ apiGet, apiPatch }));

import { MyProfilePage } from "./MyProfilePage";

describe("MyProfilePage current truth", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => {
    apiGet.mockResolvedValue({
      subject: "user:dev",
      profile: { displayName: "本机开发者", email: "", phone: "", title: "本机 Bearer 登录账号" },
    });
    host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
  });
  afterEach(async () => { await act(async () => root.unmount()); host.remove(); vi.clearAllMocks(); });

  it("净化鉴权术语且只有修改后才允许保存", async () => {
    await act(async () => root.render(createElement(MemoryRouter, null, createElement(MyProfilePage))));
    await act(async () => void await Promise.resolve());

    const title = host.querySelector<HTMLInputElement>('input[aria-label="职务"]')!;
    const save = Array.from(host.querySelectorAll<HTMLButtonElement>("button")).find((button) => button.textContent === "保存")!;
    expect(title.value).toBe("本机登录账号");
    expect(host.textContent).not.toContain("Bearer");
    expect(save.disabled).toBe(true);
    expect(apiPatch).not.toHaveBeenCalled();

    await act(async () => {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value")!.set!;
      setter.call(title, "运营负责人");
      title.dispatchEvent(new Event("input", { bubbles: true }));
    });
    expect(save.disabled).toBe(false);
  });
});
