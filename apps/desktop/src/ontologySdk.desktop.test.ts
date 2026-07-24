/**
 * 150 · 桌面同构：须能经 @aos-web 适配层解析 ontology-sdk（≥ Web）
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import { setAccessToken, clearAccessToken, setTenant, DEFAULT_TENANT } from "@aos-web/api/tenant";
import { setApiBase } from "@aos-web/api/apiBase";

describe("desktop ontology-sdk wiring", () => {
  afterEach(() => {
    clearAccessToken();
    setTenant({ ...DEFAULT_TENANT });
    setApiBase("http://127.0.0.1:8080");
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("getOntologyClient resolves and lists objects with tenant headers", async () => {
    setApiBase("http://127.0.0.1:8080");
    setAccessToken("desk-tok");
    setTenant({ orgId: "desk-org", projectId: "desk-ws", workspaceName: "Desk" });

    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      expect(url).toBe("http://127.0.0.1:8080/v1/objects/WorkOrder");
      const h = new Headers(init?.headers);
      expect(h.get("Authorization")).toBe("Bearer desk-tok");
      expect(h.get("X-Org-Id")).toBe("desk-org");
      expect(h.get("X-Project-Id")).toBe("desk-ws");
      return new Response(JSON.stringify({ items: [{ id: "wo-1" }] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const { getOntologyClient } = await import("@aos-web/api/ontologyClient");
    const { createOntologyClient } = await import("@aos/ontology-sdk");
    expect(typeof createOntologyClient).toBe("function");

    const res = await getOntologyClient().listObjects("WorkOrder");
    expect(res.items[0]?.id).toBe("wo-1");
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});
