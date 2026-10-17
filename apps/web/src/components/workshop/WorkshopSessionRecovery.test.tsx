import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { getAccessToken, setAccessToken, setTenant, tenantAuthHeaders } from "../../api/tenant";
import { WORKSHOP_SESSION_REJECTED, reportWorkshopSessionRejection, workshopSessionIdentity } from "../../api/ecommerceWorkshop/sessionRecovery";
import { WorkshopSessionRecovery } from "./WorkshopSessionRecovery";
import { MemoryRouter } from "react-router-dom";
import { EcommerceWorkshopClient } from "../../api/ecommerceWorkshop/client";
import { EcommerceWorkshopCatalogProvider } from "./EcommerceWorkshopCatalogContext";
import { EcommerceWorkshopHost } from "./EcommerceWorkshopHost";
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("explicit workshop login recovery", () => {
  let host: HTMLDivElement; let root: Root;
  beforeEach(() => { sessionStorage.clear(); setTenant({ orgId: "org-org", projectId: "dev-project", workspaceName: "test" }); setAccessToken("test-ui-current"); host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
  afterEach(() => { act(() => root.unmount()); host.remove(); setAccessToken(null); vi.restoreAllMocks(); });
  function mount() { act(() => root.render(<><WorkshopSessionRecovery /><input aria-label="未保存输入" defaultValue="保留中的合作条件" /></>)); }
  function reject() { act(() => reportWorkshopSessionRejection(401, tenantAuthHeaders(), workshopSessionIdentity())); }

  it("preserves mounted input and token until the user explicitly chooses login", () => {
    const fetch = vi.spyOn(globalThis, "fetch"); mount(); const input = host.querySelector("input")!;
    input.value = "刚修改未保存的条件"; reject();
    expect(host.textContent).toContain("登录状态需要重新确认"); expect(host.textContent).toContain("未保存");
    expect(host.querySelector("input")).toBe(input); expect(input.value).toBe("刚修改未保存的条件"); expect(getAccessToken()).toBe("test-ui-current"); expect(fetch).not.toHaveBeenCalled();
    act(() => host.querySelector("button")!.click()); expect(getAccessToken()).toBeNull(); expect(fetch).not.toHaveBeenCalled();
  });

  it("clears the advisory on a newer login and rejects old identity events", () => {
    mount(); const old = workshopSessionIdentity(); reject();
    act(() => setAccessToken("test-ui-new"));
    act(() => window.dispatchEvent(new CustomEvent(WORKSHOP_SESSION_REJECTED, { detail: old })));
    expect(host.querySelector("button")).toBeNull(); expect(getAccessToken()).toBe("test-ui-new");
  });

  it("ignores another tenant and malformed event details", () => {
    mount();
    for (const detail of [null, {}, { ...workshopSessionIdentity(), orgId: "dev-org" }]) act(() => window.dispatchEvent(new CustomEvent(WORKSHOP_SESSION_REJECTED, { detail })));
    expect(host.querySelector("button")).toBeNull(); expect(getAccessToken()).toBe("test-ui-current");
  });

  it("a delayed click cannot clear a newer session before React commits the notice removal", () => {
    mount(); reject(); const button = host.querySelector("button")!;
    act(() => { setAccessToken("test-ui-new"); button.click(); });
    expect(getAccessToken()).toBe("test-ui-new");
  });

  it.each([401, 403])("Host keeps%s refusal and offers login only for authentication rejection", async (status) => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ code: "REJECTED", message: "test refusal" }), { status }));
    const client = new EcommerceWorkshopClient({ fetch });
    await act(async () => root.render(<MemoryRouter initialEntries={["/workshop/operations"]}><EcommerceWorkshopCatalogProvider client={client}><EcommerceWorkshopHost /></EcommerceWorkshopCatalogProvider></MemoryRouter>));
    expect(fetch).toHaveBeenCalledTimes(1); expect(getAccessToken()).toBe("test-ui-current");
    expect(host.textContent).toContain(status === 401 ? "当前身份认证未通过" : "没有访问权限");
    expect(host.textContent?.includes("重新登录")).toBe(status === 401);
  });
});
