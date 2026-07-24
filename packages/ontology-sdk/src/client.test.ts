import { afterEach, describe, expect, it, vi } from "vitest";
import { createOntologyClient, OntologyApiError } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("createOntologyClient", () => {
  it("lists objects with org/project headers", async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      expect(url).toBe("http://127.0.0.1:8080/v1/objects/WorkOrder");
      const h = new Headers(init?.headers);
      expect(h.get("Authorization")).toBe("Bearer tok-1");
      expect(h.get("X-Org-Id")).toBe("dev-org");
      expect(h.get("X-Project-Id")).toBe("dev-project");
      return new Response(JSON.stringify({ items: [{ id: "wo-1" }] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

    const client = createOntologyClient({
      baseUrl: "http://127.0.0.1:8080",
      token: "tok-1",
      orgId: "dev-org",
      projectId: "dev-project",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    const res = await client.listObjects("WorkOrder");
    expect(res.items[0]?.id).toBe("wo-1");
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("creates draft via POST", async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      expect(init?.method).toBe("POST");
      expect(JSON.parse(String(init?.body))).toMatchObject({
        objectType: "WorkOrder",
        objectId: "wo-1",
      });
      return new Response(JSON.stringify({ id: "dr-1", status: "proposed" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });

    const client = createOntologyClient({
      baseUrl: "http://api",
      token: "Bearer x",
      orgId: "o",
      projectId: "p",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    const d = await client.createDraft({
      objectType: "WorkOrder",
      objectId: "wo-1",
      title: "from sdk",
    });
    expect(d.id).toBe("dr-1");
  });

  it("appends branch query", async () => {
    const fetchMock = vi.fn(async (url: string) => {
      expect(url).toBe("http://api/v1/objects/WorkOrder?branch=main");
      return new Response(JSON.stringify({ items: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    const client = createOntologyClient({
      baseUrl: "http://api",
      token: "t",
      orgId: "o",
      projectId: "p",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });
    await client.listObjects("WorkOrder", { branch: "main" });
  });

  it("approveDraft sends idempotency and conflict headers", async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => {
      expect(init?.method).toBe("POST");
      const h = new Headers(init?.headers);
      expect(h.get("Idempotency-Key")).toBe("ui-approve-dr-1");
      expect(h.get("X-Allow-Conflicts")).toBe("true");
      return new Response(JSON.stringify({ objectId: "wo-1", lineageId: "ln-1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    const client = createOntologyClient({
      baseUrl: "http://api",
      token: "t",
      orgId: "o",
      projectId: "p",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });
    const r = await client.approveDraft("dr-1", {
      idempotencyKey: "ui-approve-dr-1",
      allowConflicts: true,
    });
    expect(r.objectId).toBe("wo-1");
  });

  it("putObject with branch", async () => {
    const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
      expect(url).toBe("http://api/v1/objects/WorkOrder/wo-1?branch=feat");
      expect(init?.method).toBe("PUT");
      return new Response(JSON.stringify({ id: "wo-1" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    const client = createOntologyClient({
      baseUrl: "http://api",
      token: "t",
      orgId: "o",
      projectId: "p",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });
    await client.putObject("WorkOrder", "wo-1", { props: { title: "x" } }, { branch: "feat" });
  });

  it("maps HTTP errors", async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ code: "FORBIDDEN", message: "nope" }), {
        status: 403,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const client = createOntologyClient({
      baseUrl: "http://api",
      token: "t",
      orgId: "o",
      projectId: "p",
      fetchImpl: fetchMock as unknown as typeof fetch,
    });

    await expect(client.getObject("WorkOrder", "x")).rejects.toMatchObject({
      name: "OntologyApiError",
      status: 403,
    } satisfies Partial<OntologyApiError>);
  });
});
