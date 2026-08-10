import { describe, expect, it, vi } from "vitest";
import { AipClient } from "./client";
import { AipClientError } from "./errors";

const headers = { Authorization: "Bearer test", "X-Org-Id": "org-org", "X-Project-Id": "dev-project" };
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function client(fetch: typeof globalThis.fetch) {
  return new AipClient({ fetch, getBaseUrl: () => "https://aos.test/", getAuthHeaders: () => headers });
}

describe("AIP-0 dedicated client", () => {
  it("uses canonical auth scope headers without putting scope in the body", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () => response({ items: [] }));
    await client(fetch).request("listDrafts");
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe("https://aos.test/v1/aip/drafts");
    expect(new Headers(init?.headers).get("X-Org-Id")).toBe("org-org");
    expect(init?.body).toBeUndefined();
  });

  it("rejects client-supplied scope before fetch", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>();
    await expect(client(fetch).request("tripCircuit", { body: { orgId: "other", failureRate: 0.1 } })).rejects.toThrow(/must not contain/);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("preserves structured errors and marks disconnected mutation unknown", async () => {
    const denied = vi.fn<typeof globalThis.fetch>(async () => response({ code: "AIP_SCOPE_FORBIDDEN", message: "denied", details: null, traceId: "trace-1" }, 403));
    const error = await client(denied).request("listTools").catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(AipClientError);
    expect(error).toMatchObject({ status: 403, body: { code: "AIP_SCOPE_FORBIDDEN", traceId: "trace-1" }, outcomeUnknown: false });

    const disconnected = vi.fn<typeof globalThis.fetch>(async () => { throw new TypeError("Failed to fetch"); });
    const unknown = await client(disconnected).request("approveDraft", { params: { draft_id: "d-1" }, body: {} }).catch((caught: unknown) => caught);
    expect(unknown).toMatchObject({ status: 0, outcomeUnknown: true });
  });
});

