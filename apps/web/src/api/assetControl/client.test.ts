import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setConnectivity } from "../../lib/offlineStore";
import {
  AssetControlClient,
  AssetControlClientError,
  type InstallationActionOptions,
} from "./client";
import { normalizeAssetControlError } from "./errors";
import { createIdempotentCommand, idempotencyKeyFor } from "./idempotency";
import { REGISTRY_BUNDLE_LIST_FIXTURE } from "./registryFixtures";
import type { CompositionRequest, CreateInstallationRequest } from "./types";

const BASE_URL = "https://aos.example.test";
const INSTALLATION_ID = "11111111-1111-4111-8111-111111111111";

function jsonResponse(
  payload: unknown,
  status = 200,
  headers: Record<string, string> = {},
): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

function commandOptions(): InstallationActionOptions {
  return {
    idempotencyKey: idempotencyKeyFor(createIdempotentCommand()),
    etagVersion: 1,
  };
}

function makeClient(fetch: typeof globalThis.fetch): AssetControlClient {
  return new AssetControlClient({
    fetch,
    getBaseUrl: () => `${BASE_URL}/`,
    getAuthHeaders: () => ({
      Authorization: "Bearer test-token",
      "X-Org-Id": "org-test",
      "X-Project-Id": "project-test",
    }),
  });
}

beforeEach(() => setConnectivity("online", "asset-control-test"));
afterEach(() => {
  setConnectivity("unknown", "asset-control-test-cleanup");
  vi.restoreAllMocks();
});

describe("M3-1 asset-control SDK adapter", () => {
  it("loads Registry through the frozen parser and canonical auth headers", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () =>
      jsonResponse(REGISTRY_BUNDLE_LIST_FIXTURE),
    );
    const client = makeClient(fetch);

    await expect(client.listRegistryBundles()).resolves.toEqual(
      REGISTRY_BUNDLE_LIST_FIXTURE,
    );
    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe(`${BASE_URL}/v1/asset-bundles`);
    expect(init?.method).toBe("GET");
    const headers = new Headers(init?.headers);
    expect(headers.get("Authorization")).toBe("Bearer test-token");
    expect(headers.get("X-Org-Id")).toBe("org-test");
    expect(headers.get("X-Project-Id")).toBe("project-test");
  });

  it("encodes composition paths and sends resolve with one command key", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () =>
      jsonResponse({ compositionId: "c-1" }, 201),
    );
    const client = makeClient(fetch);
    const request: CompositionRequest = {
      requested: [],
      platformApiVersion: "1.0.0",
      platformRelease: "2026.08",
      environment: "dev",
    };
    const idempotencyKey = idempotencyKeyFor(createIdempotentCommand());

    await client.resolveComposition(request, { idempotencyKey });
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe(`${BASE_URL}/v1/bundle-compositions:resolve`);
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual(request);
    const headers = new Headers(init?.headers);
    expect(headers.get("Idempotency-Key")).toBe(idempotencyKey);
    expect(headers.has("If-Match")).toBe(false);

    fetch.mockResolvedValueOnce(jsonResponse({ compositionId: "c-1" }));
    await client.getCompositionLock("a/b", 3);
    expect(fetch.mock.calls[1][0]).toBe(
      `${BASE_URL}/v1/bundle-compositions/a%2Fb/locks/3`,
    );
  });

  it("builds installation list query and rejects invalid paging before fetch", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () =>
      jsonResponse({ items: [], total: 0, limit: 20, offset: 5 }),
    );
    const client = makeClient(fetch);

    await client.listInstallations({ state: "submitted", limit: 20, offset: 5 });
    expect(fetch.mock.calls[0][0]).toBe(
      `${BASE_URL}/v1/bundle-installations?state=submitted&limit=20&offset=5`,
    );
    expect(() => client.listInstallations({ limit: 101 })).toThrow("limit must be <= 100");
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it("requires a matching strong ETag for create, get and action responses", async () => {
    const installation = { etagVersion: 2 };
    const fetch = vi.fn<typeof globalThis.fetch>(async () =>
      jsonResponse(installation, 200, { ETag: '"2"' }),
    );
    const client = makeClient(fetch);
    const createBody: CreateInstallationRequest = {
      compositionId: "11111111-1111-4111-8111-111111111110",
      lockRevision: 1,
      overlayRevision: "overlay-1",
      displayName: "Dry install",
    };
    const createKey = idempotencyKeyFor(createIdempotentCommand());

    await client.createInstallation(createBody, { idempotencyKey: createKey });
    await client.getInstallation(INSTALLATION_ID);
    await client.submitInstallation(INSTALLATION_ID, commandOptions());

    const createHeaders = new Headers(fetch.mock.calls[0][1]?.headers);
    expect(createHeaders.get("Idempotency-Key")).toBe(createKey);
    expect(createHeaders.has("If-Match")).toBe(false);
    const actionHeaders = new Headers(fetch.mock.calls[2][1]?.headers);
    expect(actionHeaders.get("If-Match")).toBe('"1"');
    expect(JSON.parse(String(fetch.mock.calls[2][1]?.body))).toEqual({});

    fetch.mockResolvedValueOnce(jsonResponse(installation, 200, { ETag: '"3"' }));
    await expect(client.getInstallation(INSTALLATION_ID)).rejects.toThrow(
      "installation ETag does not match etagVersion",
    );
  });

  it("sends the six action bodies and canonical headers without changing the key", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () =>
      jsonResponse({ etagVersion: 2 }, 200, { ETag: '"2"' }),
    );
    const client = makeClient(fetch);
    const options = commandOptions();
    const approve = {
      lockHash: "sha256:lock" as const,
      permissionDiffHash: "sha256:permission" as const,
      migrationPlanHash: "sha256:migration" as const,
      contributionDiffHash: "sha256:contribution" as const,
    };

    await client.submitInstallation(INSTALLATION_ID, options);
    await client.approveInstallation(INSTALLATION_ID, approve, options);
    await client.rejectInstallation(INSTALLATION_ID, { reason: "reject" }, options);
    await client.applyInstallation(INSTALLATION_ID, options);
    await client.verifyInstallation(INSTALLATION_ID, options);
    await client.rollbackInstallation(INSTALLATION_ID, { reason: "rollback" }, options);

    expect(fetch.mock.calls.map(([url]) => String(url).split("/").at(-1))).toEqual([
      "submit",
      "approve",
      "reject",
      "apply",
      "verify",
      "rollback",
    ]);
    expect(fetch.mock.calls.map(([, init]) => JSON.parse(String(init?.body)))).toEqual([
      {},
      approve,
      { reason: "reject" },
      {},
      {},
      { reason: "rollback" },
    ]);
    for (const [, init] of fetch.mock.calls) {
      const headers = new Headers(init?.headers);
      expect(headers.get("Idempotency-Key")).toBe(options.idempotencyKey);
      expect(headers.get("If-Match")).toBe('"1"');
    }
  });

  it("stops offline mutations before fetch and preserves known non-execution", async () => {
    setConnectivity("offline", "asset-control-test");
    const fetch = vi.fn<typeof globalThis.fetch>(async () => jsonResponse({}));
    const client = makeClient(fetch);

    const error = await client
      .submitInstallation(INSTALLATION_ID, commandOptions())
      .catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(AssetControlClientError);
    expect(fetch).not.toHaveBeenCalled();
    expect(normalizeAssetControlError(error)).toMatchObject({
      kind: "offline_mutation_disabled",
      outcomeUnknown: false,
      retryable: false,
      failureClosed: true,
    });
  });

  it("normalizes canonical conflicts and network uncertainty", async () => {
    const conflictFetch = vi.fn<typeof globalThis.fetch>(async () =>
      jsonResponse(
        { code: "ETAG_MISMATCH", message: "stale", details: null, traceId: "t-1" },
        412,
      ),
    );
    const conflictClient = makeClient(conflictFetch);
    const conflict = await conflictClient
      .submitInstallation(INSTALLATION_ID, commandOptions())
      .catch((caught: unknown) => caught);
    expect(normalizeAssetControlError(conflict)).toMatchObject({
      status: 412,
      isConflict: true,
      requiresRefresh: true,
    });

    const networkClient = makeClient(
      vi.fn<typeof globalThis.fetch>(async () => {
        throw new TypeError("Failed to fetch");
      }),
    );
    const network = await networkClient
      .submitInstallation(INSTALLATION_ID, commandOptions())
      .catch((caught: unknown) => caught);
    expect(normalizeAssetControlError(network)).toMatchObject({
      status: 0,
      outcomeUnknown: true,
      requiresRefresh: true,
    });
  });
});
