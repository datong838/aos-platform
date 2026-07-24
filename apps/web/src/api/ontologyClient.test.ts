import { afterEach, describe, expect, it, vi } from "vitest";
import { setTenant, setAccessToken, clearAccessToken, DEFAULT_TENANT } from "./tenant";

vi.mock("@aos/ontology-sdk", () => ({
  createOntologyClient: vi.fn((opts: Record<string, unknown>) => opts),
}));

vi.mock("./apiBase", () => ({
  getApiBase: () => "http://127.0.0.1:8080",
}));

describe("getOntologyClient", () => {
  afterEach(() => {
    setTenant({ ...DEFAULT_TENANT });
    clearAccessToken();
    vi.resetModules();
  });

  it("passes tenant and token into SDK", async () => {
    setTenant({ orgId: "acme", projectId: "ws-1", workspaceName: "W1" });
    setAccessToken("tok-xyz");
    const { createOntologyClient } = await import("@aos/ontology-sdk");
    const { getOntologyClient } = await import("./ontologyClient");
    const opts = getOntologyClient() as unknown as {
      baseUrl: string;
      token: string;
      orgId: string;
      projectId: string;
    };
    expect(createOntologyClient).toHaveBeenCalled();
    expect(opts.baseUrl).toBe("http://127.0.0.1:8080");
    expect(opts.token).toBe("tok-xyz");
    expect(opts.orgId).toBe("acme");
    expect(opts.projectId).toBe("ws-1");
  });
});
