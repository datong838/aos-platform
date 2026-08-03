import { describe, expect, it } from "vitest";

import {
  ASSET_CONTROL_ERROR_STATUS_MEANINGS,
  ASSET_CONTROL_HEADER_CONTRACT,
  ASSET_CONTROL_OPERATIONS,
} from "./operations";

describe("asset-control M2-B operation contract", () => {
  it("freezes the 11 unique operation ids and paths", () => {
    const operations = Object.values(ASSET_CONTROL_OPERATIONS);

    expect(operations).toHaveLength(11);
    expect(new Set(operations.map((operation) => operation.operationId)).size).toBe(11);
    expect(
      new Set(
        operations.map(
          (operation) => `${operation.method} ${operation.pathTemplate}`,
        ),
      ).size,
    ).toBe(11);
  });

  it("requires idempotency for commands and If-Match for state actions", () => {
    const operations = Object.values(ASSET_CONTROL_OPERATIONS);
    const idempotentCommands = operations
      .filter((operation) => operation.requiresIdempotencyKey)
      .map((operation) => operation.operationId);
    const conditionalActions = operations
      .filter((operation) => operation.requiresIfMatch)
      .map((operation) => operation.operationId);

    expect(idempotentCommands).toEqual([
      "resolve_bundle_composition",
      "create_bundle_installation",
      "submit_bundle_installation",
      "approve_bundle_installation",
      "reject_bundle_installation",
      "apply_bundle_installation",
      "verify_bundle_installation",
      "rollback_bundle_installation",
    ]);
    expect(conditionalActions).toEqual([
      "submit_bundle_installation",
      "approve_bundle_installation",
      "reject_bundle_installation",
      "apply_bundle_installation",
      "verify_bundle_installation",
      "rollback_bundle_installation",
    ]);
  });

  it("freezes strong revision validators and stable error meanings", () => {
    expect(ASSET_CONTROL_HEADER_CONTRACT).toEqual({
      idempotencyKey: {
        name: "Idempotency-Key",
        minLength: 1,
        maxLength: 160,
      },
      ifMatch: { name: "If-Match", pattern: '^"[1-9][0-9]*"$' },
      etag: { name: "ETag", pattern: '^"[1-9][0-9]*"$' },
    });
    expect(ASSET_CONTROL_ERROR_STATUS_MEANINGS).toEqual({
      400: "invalid_request",
      401: "unauthenticated",
      403: "forbidden",
      404: "not_visible_or_missing",
      409: "state_or_idempotency_conflict",
      412: "etag_precondition_failed",
      428: "if_match_required",
      500: "server_error",
    });
  });

  it("does not advertise ETag on composition or list responses", () => {
    expect(ASSET_CONTROL_OPERATIONS.resolveComposition.returnsEtag).toBe(false);
    expect(ASSET_CONTROL_OPERATIONS.getCompositionLock.returnsEtag).toBe(false);
    expect(ASSET_CONTROL_OPERATIONS.listInstallations.returnsEtag).toBe(false);

    for (const operation of Object.values(ASSET_CONTROL_OPERATIONS).filter(
      (item) => item.operationId.includes("installation") && item.operationId !== "list_bundle_installations",
    )) {
      expect(operation.returnsEtag).toBe(true);
    }
  });
});
