import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EcommerceWorkshopClient } from "./client";
import { getAccessToken, getAuthRevision, getTenant, setAccessToken, setTenant } from "../tenant";
import { WORKSHOP_SESSION_REJECTED } from "./sessionRecovery";

const reads = ["getTaskCockpitCore", "getOperationsView", "getContentCampaignView", "getCreatorGrowthView", "getMediaStudioView", "getAnalystView", "getPriceGovernanceView", "getCustomerView"] as const;
const failure = (status = 401) => new Response(JSON.stringify({ code: "AUTH_INVALID", message: "rejected" }), { status });
describe("workshop current-session read rejection", () => {
  const notice = vi.fn();
  beforeEach(() => { sessionStorage.clear(); setTenant({ orgId: "org-org", projectId: "dev-project", workspaceName: "test" }); setAccessToken("test-current-session"); notice.mockClear(); window.addEventListener(WORKSHOP_SESSION_REJECTED, notice); });
  afterEach(() => { window.removeEventListener(WORKSHOP_SESSION_REJECTED, notice); setAccessToken(null); vi.restoreAllMocks(); });

  it.each(reads)("%s keeps401 refusal and issues only an identity advisory", async (method) => {
    const fetch = vi.fn().mockResolvedValue(failure());
    const client = new EcommerceWorkshopClient({ fetch });
    await expect(client[method]()).rejects.toMatchObject({ status: 401 });
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][1].method).toBe("GET");
    expect(notice).toHaveBeenCalledTimes(1);
    expect(notice.mock.calls[0][0].detail).toEqual({ authRevision: getAuthRevision(), orgId: "org-org", projectId: "dev-project" });
    expect(JSON.stringify(notice.mock.calls[0][0].detail)).not.toContain("test-current-session");
    expect(getAccessToken()).toBe("test-current-session");
  });

  it.each([403, 500])("does not turn %s into a login demand", async (status) => {
    const client = new EcommerceWorkshopClient({ fetch: vi.fn().mockResolvedValue(failure(status)) });
    await expect(client.getOperationsView()).rejects.toMatchObject({ status });
    expect(notice).not.toHaveBeenCalled();
    expect(getAccessToken()).toBe("test-current-session");
  });

  it.each(["login", "tenant"])("ignores a late401 after changing %s", async (change) => {
    let finish!: (value: Response) => void;
    const fetch = vi.fn(() => new Promise<Response>(resolve => { finish = resolve; }));
    const result = new EcommerceWorkshopClient({ fetch }).getOperationsView();
    const rejected = expect(result).rejects.toMatchObject({ status: 401 });
    if (change === "login") setAccessToken("test-new-session");
    else setTenant({ orgId: "dev-org" });
    finish(failure()); await rejected;
    expect(notice).not.toHaveBeenCalled(); expect(fetch).toHaveBeenCalledTimes(1);
    expect(getAccessToken()).toBe(change === "login" ? "test-new-session" : "test-current-session");
  });

  it("never treats a POST refusal as permission to replay or reauthenticate", async () => {
    const fetch = vi.fn().mockResolvedValue(failure());
    const client = new EcommerceWorkshopClient({ fetch });
    await expect(client.executeCreatorInternalWorkflow({ command: "create", purpose: "outreach_batch", title: "测试合作目标", summary: "仅测试拒绝处理" }, "test-rejected-create")).rejects.toMatchObject({ status: 401 });
    expect(fetch).toHaveBeenCalledTimes(1); expect(fetch.mock.calls[0][1].method).toBe("POST"); expect(notice).not.toHaveBeenCalled();
  });

  it("does not advertise login for a different custom request credential", async () => {
    const client = new EcommerceWorkshopClient({ fetch: vi.fn().mockResolvedValue(failure()), getAuthHeaders: () => ({ Authorization: "Bearer other-test", "X-Org-Id": getTenant().orgId, "X-Project-Id": getTenant().projectId }) });
    await expect(client.getOperationsView()).rejects.toMatchObject({ status: 401 }); expect(notice).not.toHaveBeenCalled();
  });

  it("keeps network failure separate from authentication without retrying", async () => {
    const fetch = vi.fn().mockRejectedValue(new TypeError("test network failure"));
    await expect(new EcommerceWorkshopClient({ fetch }).getOperationsView()).rejects.toMatchObject({ status: 0 });
    expect(notice).not.toHaveBeenCalled(); expect(fetch).toHaveBeenCalledTimes(1);
    expect(getAccessToken()).toBe("test-current-session");
  });

  it("compares the sent header snapshot rather than an externally mutated header object", async () => {
    const headers = { Authorization: "Bearer other-test", "X-Org-Id": "org-org", "X-Project-Id": "dev-project" };
    let finish!: (response: Response) => void;
    const fetch = vi.fn(() => new Promise<Response>(resolve => { finish = resolve; }));
    const result = new EcommerceWorkshopClient({ fetch, getAuthHeaders: () => headers }).getOperationsView();
    const rejected = expect(result).rejects.toMatchObject({ status: 401 });
    headers.Authorization = "Bearer test-current-session"; finish(failure()); await rejected;
    expect(notice).not.toHaveBeenCalled(); expect(fetch).toHaveBeenCalledTimes(1);
  });
});
