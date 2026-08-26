import { describe, expect, it, vi } from "vitest";
import { EcommerceInvestigationClient } from "./client";

const tenant = { orgId: "org-org", projectId: "dev-project" };
describe("EcommerceInvestigationClient", () => {
  it("只发出 canonical Case/Run GET 且不提交 tenant", async () => {
    const fetch = vi.fn().mockImplementation(async () => new Response(JSON.stringify({ tenant, items: [], count: 0 }), { status: 200, headers: { "Content-Type": "application/json" } }));
    const client = new EcommerceInvestigationClient({ fetch, getBaseUrl: () => "http://aos.test", getAuthHeaders: () => ({ Authorization: "Bearer test" }) });
    await client.listCases(); await client.listRuns("case:1");
    expect(fetch).toHaveBeenNthCalledWith(1, "http://aos.test/v1/ecommerce/investigations/cases?limit=200", expect.objectContaining({ method: "GET" }));
    expect(fetch).toHaveBeenNthCalledWith(2, "http://aos.test/v1/ecommerce/investigations/cases/case%3A1/runs?limit=200", expect.objectContaining({ method: "GET" }));
    expect(JSON.stringify(fetch.mock.calls)).not.toContain("org-org");
  });
  it("在网络前拒绝非法 Case ID", async () => {
    const fetch = vi.fn(); const client = new EcommerceInvestigationClient({ fetch });
    await expect(client.listRuns("../other")).rejects.toThrow(/caseId 无效/); expect(fetch).not.toHaveBeenCalled();
  });
});
