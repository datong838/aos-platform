import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiGetAuthoritative, apiPostUnqueued } from "../../api/client";
import { AnalystMethodPage } from "./AnalystMethodPage";

vi.mock("../../api/client", () => ({ apiGetAuthoritative: vi.fn(), apiPostUnqueued: vi.fn() }));
vi.mock("../../api/tenant", () => ({ getTenant: () => ({ orgId: "org-org", projectId: "dev-project" }) }));

describe("AnalystMethodPage", () => {
  let host: HTMLDivElement;
  let root: Root;
  beforeEach(() => {
    localStorage.clear(); vi.clearAllMocks();
    host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host);
  });
  afterEach(() => { act(() => root.unmount()); host.remove(); localStorage.clear(); });

  const button = (name: string) => Array.from(host.querySelectorAll("button"))
    .find((item) => item.textContent?.includes(name))!;
  const render = async () => { await act(async () => root.render(<MemoryRouter><AnalystMethodPage /></MemoryRouter>)); };

  it("requires authoritative current read before any write and freezes unknown outcome", async () => {
    vi.mocked(apiGetAuthoritative).mockRejectedValueOnce({ status: 404, message: "not found" })
      .mockResolvedValueOnce(null);
    vi.mocked(apiPostUnqueued).mockRejectedValueOnce(new Error("connection lost"));
    await render();
    expect(button("提交正式方法版本").disabled).toBe(true);
    await act(async () => { button("读取当前正式版本").click(); });
    expect(button("提交正式方法版本").disabled).toBe(false);
    await act(async () => { button("提交正式方法版本").click(); });
    expect(apiPostUnqueued).toHaveBeenCalledTimes(1);
    const [path, body, headers] = vi.mocked(apiPostUnqueued).mock.calls[0]!;
    expect(path).toBe("/v1/ecommerce/analyst/methods");
    expect(body).toMatchObject({ methodId: "sales-weapon-descriptive-snapshot", expectedVersion: 0,
      algorithm: "descriptive_snapshot_v1", insightKind: "observation" });
    expect(headers).toHaveProperty("Idempotency-Key");
    expect(button("提交正式方法版本").disabled).toBe(true);
    expect(host.textContent).toContain("禁止重发");
    await act(async () => { button("按回执只读对账").click(); });
    expect(apiPostUnqueued).toHaveBeenCalledTimes(1);
    expect(host.textContent).toContain("保持冻结");
  });

  it("rejects mismatched tenant on current read", async () => {
    vi.mocked(apiGetAuthoritative).mockResolvedValueOnce({ tenant: { orgId: "dev-org", projectId: "dev-project" },
      methodId: "sales-weapon-descriptive-snapshot", revision: 1, contentHash: "a".repeat(64),
      name: "wrong", description: "wrong", minSourceItems: 1,
      maxSourceAgeSeconds: 86400, limitations: ["wrong"] });
    await render();
    await act(async () => { button("读取当前正式版本").click(); });
    expect(button("提交正式方法版本").disabled).toBe(true);
    expect(host.textContent).toContain("租户或方法 ID 不一致");
    expect(apiPostUnqueued).not.toHaveBeenCalled();
  });
});
