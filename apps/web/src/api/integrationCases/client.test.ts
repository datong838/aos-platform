import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setConnectivity } from "../../lib/offlineStore";
import { IntegrationCaseClient } from "./client";
import { IntegrationCaseClientError, normalizeIntegrationCaseError } from "./errors";
import {
  CASE_ID,
  CURRENT_CASE_DETAIL_FIXTURE,
  CURRENT_CASE_LIST_FIXTURE,
  INSTALLATION_ID,
  REFERENCE_CASE_LIST_FIXTURE,
  REFERENCE_CASE_DETAIL_FIXTURE,
  SNAPSHOT_FIXTURE,
  TIMELINE_FIXTURE,
} from "./fixtures";
import {
  createIntegrationCaseCommand,
  integrationCaseIdempotencyKeyFor,
  type IntegrationCaseIdempotencyKey,
} from "./idempotency";

const BASE_URL = "https://aos.example.test/";
const AUTH_HEADERS = {
  Authorization: "Bearer test-token",
  "X-Org-Id": "org-test",
  "X-Project-Id": "project-test",
};

function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

function makeClient(fetch: typeof globalThis.fetch): IntegrationCaseClient {
  return new IntegrationCaseClient({
    fetch,
    getBaseUrl: () => BASE_URL,
    getAuthHeaders: () => AUTH_HEADERS,
  });
}

function commandOptions() {
  return { idempotencyKey: integrationCaseIdempotencyKeyFor(createIntegrationCaseCommand()) };
}

beforeEach(() => setConnectivity("online", "integration-case-client-test"));
afterEach(() => {
  setConnectivity("unknown", "integration-case-client-test-cleanup");
  vi.restoreAllMocks();
});

describe("M4-1 integration case SDK client", () => {
  it("lists one explicit scope with validated paging and canonical tenant/auth headers", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () => jsonResponse(CURRENT_CASE_LIST_FIXTURE));
    const client = makeClient(fetch);
    await expect(client.listCases({ scope: "current", limit: 20, offset: 5 })).resolves.toEqual(CURRENT_CASE_LIST_FIXTURE);
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe(`${BASE_URL.replace(/\/$/, "")}/v1/integration-cases?limit=20&offset=5&scope=current`);
    const headers = new Headers(init?.headers);
    expect(init?.method).toBe("GET");
    expect(headers.get("Authorization")).toBe("Bearer test-token");
    expect(headers.get("X-Org-Id")).toBe("org-test");
    expect(headers.get("X-Project-Id")).toBe("project-test");
  });

  it("fails closed if the list response crosses the requested scope", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () => jsonResponse(REFERENCE_CASE_LIST_FIXTURE));
    const error = await makeClient(fetch).listCases({ scope: "current" }).catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(IntegrationCaseClientError);
    expect(error).toMatchObject({ body: { code: "INVALID_SUCCESS_RESPONSE" }, mutation: false });
  });

  it("creates a case with one exact body, idempotency key and matching strong ETag", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () => jsonResponse(CURRENT_CASE_DETAIL_FIXTURE, 201, { ETag: '"3"' }));
    const client = makeClient(fetch);
    const options = commandOptions();
    const body = { installationId: INSTALLATION_ID, overlayRevision: "overlay-7", displayName: "Current commerce case" };
    await expect(client.createCase(body, options)).resolves.toEqual(CURRENT_CASE_DETAIL_FIXTURE);
    const [, init] = fetch.mock.calls[0];
    expect(JSON.parse(String(init?.body))).toEqual(body);
    const headers = new Headers(init?.headers);
    expect(headers.get("Idempotency-Key")).toBe(options.idempotencyKey);
    expect(headers.has("If-Match")).toBe(false);
  });

  it("rejects a reference projection returned from the current-only create command", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () => jsonResponse(REFERENCE_CASE_DETAIL_FIXTURE, 201, { ETag: '"1"' }));
    const error = await makeClient(fetch).createCase({
      installationId: INSTALLATION_ID,
      overlayRevision: "overlay-7",
      displayName: "Current commerce case",
    }, commandOptions()).catch((caught: unknown) => caught);
    expect(error).toMatchObject({
      body: { code: "INVALID_SUCCESS_RESPONSE", message: "create response must be a current case" },
      mutation: true,
    });
    expect(normalizeIntegrationCaseError(error)).toMatchObject({
      code: "INVALID_SUCCESS_RESPONSE",
      outcomeUnknown: true,
      requiresRefresh: true,
    });
  });

  it("gets detail with case binding and a matching response ETag", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () => jsonResponse(CURRENT_CASE_DETAIL_FIXTURE, 200, { ETag: '"3"' }));
    await expect(makeClient(fetch).getCase(CASE_ID)).resolves.toEqual(CURRENT_CASE_DETAIL_FIXTURE);
    expect(fetch.mock.calls[0][0]).toBe(`${BASE_URL.replace(/\/$/, "")}/v1/integration-cases/${CASE_ID}`);
  });

  it("creates a snapshot with empty body, stable key, strong If-Match and response ETag", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () => jsonResponse(SNAPSHOT_FIXTURE, 201, { ETag: '"3"' }));
    const client = makeClient(fetch);
    const options = { ...commandOptions(), etagVersion: 2 };
    await expect(client.createEvidenceSnapshot(CASE_ID, options)).resolves.toEqual(SNAPSHOT_FIXTURE);
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe(`${BASE_URL.replace(/\/$/, "")}/v1/integration-cases/${CASE_ID}/evidence-snapshots`);
    expect(JSON.parse(String(init?.body))).toEqual({});
    const headers = new Headers(init?.headers);
    expect(headers.get("Idempotency-Key")).toBe(options.idempotencyKey);
    expect(headers.get("If-Match")).toBe('"2"');
  });

  it("lists the bound timeline with validated paging", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () => jsonResponse(TIMELINE_FIXTURE));
    await expect(makeClient(fetch).listTimeline(CASE_ID, { limit: 50, offset: 0 })).resolves.toEqual(TIMELINE_FIXTURE);
    expect(fetch.mock.calls[0][0]).toBe(`${BASE_URL.replace(/\/$/, "")}/v1/integration-cases/${CASE_ID}/timeline?limit=50&offset=0`);
  });

  it("rejects invalid scope, paging, UUID, body, key and ETag before fetch", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>();
    const client = makeClient(fetch);
    await expect(client.listCases({ scope: "mixed" as never })).rejects.toThrow(/scope/);
    await expect(client.listCases({ scope: "current", limit: 101 })).rejects.toThrow(/limit/);
    await expect(client.getCase("NOT-A-UUID")).rejects.toThrow(/canonical lowercase UUID/);
    await expect(client.createCase({ installationId: INSTALLATION_ID, overlayRevision: "overlay-7", displayName: "Case", stage: "production_active" } as never, commandOptions())).rejects.toThrow(/extra=stage/);
    await expect(client.createCase({ installationId: INSTALLATION_ID, overlayRevision: "overlay-7", displayName: "Case" }, { idempotencyKey: " bad " as IntegrationCaseIdempotencyKey })).rejects.toThrow(/idempotencyKey/);
    await expect(client.createEvidenceSnapshot(CASE_ID, { ...commandOptions(), etagVersion: 0 })).rejects.toThrow(/positive/);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("stops both writes before fetch while offline", async () => {
    setConnectivity("offline", "integration-case-client-test");
    const fetch = vi.fn<typeof globalThis.fetch>();
    const client = makeClient(fetch);
    const create = await client.createCase({ installationId: INSTALLATION_ID, overlayRevision: "overlay-7", displayName: "Case" }, commandOptions()).catch((error: unknown) => error);
    const snapshot = await client.createEvidenceSnapshot(CASE_ID, { ...commandOptions(), etagVersion: 3 }).catch((error: unknown) => error);
    expect(fetch).not.toHaveBeenCalled();
    for (const error of [create, snapshot]) {
      expect(normalizeIntegrationCaseError(error)).toMatchObject({ kind: "offline_mutation_disabled", outcomeUnknown: false });
    }
  });

  it("rejects malformed success and mismatched ETag without accepting facts", async () => {
    const drifted = { ...CURRENT_CASE_DETAIL_FIXTURE, computedStage: "live" };
    const fetch = vi.fn<typeof globalThis.fetch>(async () => jsonResponse(drifted, 200, { ETag: '"3"' }));
    const malformed = await makeClient(fetch).getCase(CASE_ID).catch((error: unknown) => error);
    expect(malformed).toMatchObject({ body: { code: "INVALID_SUCCESS_RESPONSE" } });

    fetch.mockResolvedValueOnce(jsonResponse(CURRENT_CASE_DETAIL_FIXTURE, 200, { ETag: '"4"' }));
    const mismatch = await makeClient(fetch).getCase(CASE_ID).catch((error: unknown) => error);
    expect(mismatch).toMatchObject({ body: { code: "INVALID_SUCCESS_RESPONSE", message: "response ETag does not match body etagVersion" } });
  });

  it.each([403, 404, 409, 422, 428, 500])("preserves structured HTTP %i errors", async (status) => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () => jsonResponse({
      code: status === 422 ? "EVIDENCE_REFERENCE_INVALID" : `CODE_${status}`,
      message: "closed",
      details: { status },
      traceId: `trace-${status}`,
    }, status));
    const error = await makeClient(fetch).getCase(CASE_ID).catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(IntegrationCaseClientError);
    const normalized = normalizeIntegrationCaseError(error);
    expect(normalized.status).toBe(status);
    expect(normalized.failureClosed).toBe(true);
    if (status === 404) expect(normalized).toMatchObject({ code: "NOT_VISIBLE_OR_MISSING", details: null });
  });

  it("marks only a disconnected write as outcome unknown", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () => { throw new TypeError("Failed to fetch"); });
    const client = makeClient(fetch);
    const read = normalizeIntegrationCaseError(await client.getCase(CASE_ID).catch((error: unknown) => error));
    const write = normalizeIntegrationCaseError(await client.createEvidenceSnapshot(CASE_ID, { ...commandOptions(), etagVersion: 3 }).catch((error: unknown) => error));
    expect(read).toMatchObject({ outcomeUnknown: false, recovery: "retry_read" });
    expect(write).toMatchObject({ outcomeUnknown: true, recovery: "retry_same_command", requiresRefresh: true });
  });
});
