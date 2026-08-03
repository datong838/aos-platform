import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setConnectivity } from "../../lib/offlineStore";
import {
  COMPOSITION_REQUEST_FIXTURE,
  STORED_COMPOSITION_LOCK_FIXTURE,
} from "./compositionFixtures";
import {
  AssetControlClient,
  AssetControlClientError,
  type InstallationActionOptions,
} from "./client";
import { normalizeAssetControlError } from "./errors";
import { createIdempotentCommand, idempotencyKeyFor } from "./idempotency";
import {
  INSTALLATION_ACTIVE_FIXTURE,
  INSTALLATION_APPLIED_FIXTURE,
  INSTALLATION_APPROVED_FIXTURE,
  INSTALLATION_REJECTED_FIXTURE,
  INSTALLATION_ROLLED_BACK_FIXTURE,
  INSTALLATION_SUBMITTED_FIXTURE,
} from "./installationActionFixtures";
import {
  INSTALLATION_DETAIL_FIXTURE,
  INSTALLATION_DRAFT_FIXTURE,
} from "./installationFixtures";
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
      jsonResponse(STORED_COMPOSITION_LOCK_FIXTURE, 201),
    );
    const client = makeClient(fetch);
    const request: CompositionRequest = COMPOSITION_REQUEST_FIXTURE;
    const idempotencyKey = idempotencyKeyFor(createIdempotentCommand());

    await client.resolveComposition(request, { idempotencyKey });
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe(`${BASE_URL}/v1/bundle-compositions:resolve`);
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual(request);
    const headers = new Headers(init?.headers);
    expect(headers.get("Idempotency-Key")).toBe(idempotencyKey);
    expect(headers.has("If-Match")).toBe(false);

    fetch.mockResolvedValueOnce(jsonResponse(STORED_COMPOSITION_LOCK_FIXTURE));
    await client.getCompositionLock(STORED_COMPOSITION_LOCK_FIXTURE.compositionId, 3);
    expect(fetch.mock.calls[1][0]).toBe(
      `${BASE_URL}/v1/bundle-compositions/${STORED_COMPOSITION_LOCK_FIXTURE.compositionId}/locks/3`,
    );

    expect(() => client.getCompositionLock("a/b", 3)).toThrow(
      "compositionId must be a canonical lowercase UUID",
    );
    expect(fetch).toHaveBeenCalledTimes(2);
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
    const installation = INSTALLATION_DETAIL_FIXTURE;
    const fetch = vi.fn<typeof globalThis.fetch>(async () =>
      jsonResponse(INSTALLATION_DRAFT_FIXTURE, 201, { ETag: '"1"' }),
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
    fetch.mockResolvedValueOnce(jsonResponse(installation, 200, { ETag: '"5"' }));
    await client.getInstallation(INSTALLATION_ID);
    fetch.mockResolvedValueOnce(jsonResponse(INSTALLATION_SUBMITTED_FIXTURE, 200, { ETag: '"2"' }));
    await client.submitInstallation(INSTALLATION_ID, commandOptions());

    const createHeaders = new Headers(fetch.mock.calls[0][1]?.headers);
    expect(createHeaders.get("Idempotency-Key")).toBe(createKey);
    expect(createHeaders.has("If-Match")).toBe(false);
    const actionHeaders = new Headers(fetch.mock.calls[2][1]?.headers);
    expect(actionHeaders.get("If-Match")).toBe('"1"');
    expect(JSON.parse(String(fetch.mock.calls[2][1]?.body))).toEqual({});

    fetch.mockResolvedValueOnce(jsonResponse(installation, 200, { ETag: '"6"' }));
    await expect(client.getInstallation(INSTALLATION_ID)).rejects.toThrow(
      "installation ETag does not match etagVersion",
    );
  });

  it("sends six exact action bodies with a unique key per new command", async () => {
    const responses = [
      INSTALLATION_SUBMITTED_FIXTURE,
      INSTALLATION_APPROVED_FIXTURE,
      INSTALLATION_REJECTED_FIXTURE,
      INSTALLATION_APPLIED_FIXTURE,
      INSTALLATION_ACTIVE_FIXTURE,
      INSTALLATION_ROLLED_BACK_FIXTURE,
    ];
    let responseIndex = 0;
    const fetch = vi.fn<typeof globalThis.fetch>(async () => {
      const response = responses[responseIndex++];
      return jsonResponse(response, 200, { ETag: `"${response.etagVersion}"` });
    });
    const client = makeClient(fetch);
    const approve = {
      lockHash: INSTALLATION_SUBMITTED_FIXTURE.current.lockHash,
      permissionDiffHash: INSTALLATION_SUBMITTED_FIXTURE.current.permissionDiffHash,
      migrationPlanHash: INSTALLATION_SUBMITTED_FIXTURE.current.migrationPlanHash,
      contributionDiffHash: INSTALLATION_SUBMITTED_FIXTURE.current.contributionDiffHash,
    };
    const etagVersions = [1, 2, 2, 3, 4, 5];
    const options = etagVersions.map((etagVersion) => ({
      idempotencyKey: idempotencyKeyFor(createIdempotentCommand()),
      etagVersion,
    }));

    await client.submitInstallation(INSTALLATION_ID, options[0]);
    await client.approveInstallation(INSTALLATION_ID, approve, options[1]);
    await client.rejectInstallation(INSTALLATION_ID, { reason: "reject" }, options[2]);
    await client.applyInstallation(INSTALLATION_ID, options[3]);
    await client.verifyInstallation(INSTALLATION_ID, options[4]);
    await client.rollbackInstallation(INSTALLATION_ID, { reason: "rollback" }, options[5]);

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
    expect(new Set(options.map((option) => option.idempotencyKey)).size).toBe(6);
    fetch.mock.calls.forEach(([, init], index) => {
      const headers = new Headers(init?.headers);
      expect(headers.get("Idempotency-Key")).toBe(options[index].idempotencyKey);
      expect(headers.get("If-Match")).toBe(`"${etagVersions[index]}"`);
    });
  });

  it("reuses the same command envelope only when retrying that command", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>(async () =>
      jsonResponse(INSTALLATION_SUBMITTED_FIXTURE, 200, { ETag: '"2"' }),
    );
    const client = makeClient(fetch);
    const options = commandOptions();

    await client.submitInstallation(INSTALLATION_ID, options);
    await client.submitInstallation(INSTALLATION_ID, options);

    const envelopes = fetch.mock.calls.map(([, init]) => ({
      body: init?.body,
      idempotencyKey: new Headers(init?.headers).get("Idempotency-Key"),
      ifMatch: new Headers(init?.headers).get("If-Match"),
    }));
    expect(envelopes[1]).toEqual(envelopes[0]);
  });

  it("rejects illegal action UUID, body and ETag before fetch", async () => {
    const fetch = vi.fn<typeof globalThis.fetch>();
    const client = makeClient(fetch);
    const options = commandOptions();
    const approve = {
      lockHash: INSTALLATION_SUBMITTED_FIXTURE.current.lockHash,
      permissionDiffHash: INSTALLATION_SUBMITTED_FIXTURE.current.permissionDiffHash,
      migrationPlanHash: INSTALLATION_SUBMITTED_FIXTURE.current.migrationPlanHash,
      contributionDiffHash: INSTALLATION_SUBMITTED_FIXTURE.current.contributionDiffHash,
    };

    expect(() => client.submitInstallation("NOT-A-UUID", options)).toThrow(/canonical lowercase UUID/);
    expect(() => client.approveInstallation(INSTALLATION_ID, { ...approve, actor: "reviewer" } as never, options)).toThrow(/exactly/);
    expect(() => client.rejectInstallation(INSTALLATION_ID, { reason: " padded " }, options)).toThrow(/normalized/);
    expect(() => client.rollbackInstallation(INSTALLATION_ID, { reason: "" }, options)).toThrow(/normalized/);
    await expect(client.applyInstallation(INSTALLATION_ID, { ...options, etagVersion: 0 })).rejects.toThrow(/positive/);
    expect(fetch).not.toHaveBeenCalled();
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

    for (const status of [409, 503]) {
      const fetch = vi.fn<typeof globalThis.fetch>(async () =>
        jsonResponse(
          { code: status === 503 ? "TRUST_ROOT_UNAVAILABLE" : "REVISION_CONFLICT", message: "closed", details: null, traceId: `t-${status}` },
          status,
        ),
      );
      const caught = await makeClient(fetch)
        .submitInstallation(INSTALLATION_ID, commandOptions())
        .catch((error: unknown) => error);
      expect(normalizeAssetControlError(caught)).toMatchObject(
        status === 409
          ? { status: 409, isConflict: true, requiresRefresh: true }
          : { status: 503, kind: "service_unavailable", retryable: false, outcomeUnknown: false },
      );
    }

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
