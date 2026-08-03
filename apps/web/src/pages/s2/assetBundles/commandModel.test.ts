import { describe, expect, it } from "vitest";
import type { AssetControlError } from "../../../api/assetControl/errors";
import type { IdempotentCommand } from "../../../api/assetControl/idempotency";
import type { StoredCompositionLock } from "../../../api/assetControl/types";
import {
  beginCommand,
  canCreateInstallation,
  compositionLocksEqual,
  failCommand,
  initialCommandState,
  markCommandInputChanged,
  reconcileCommand,
  succeedCommand,
} from "./commandModel";

const command = { idempotencyKey: "idem-1" } as unknown as Readonly<IdempotentCommand>;

const lock = {
  compositionId: "composition-1",
  revision: 7,
  payload: {
    requested: [],
    platformApiVersion: "v1",
    platformRelease: "2026.08",
    environment: "prod",
    registrySnapshotHash: null,
    currentInstallationRef: null,
    resolvedAssets: [],
    permissionDiff: [],
    migrationPlan: [],
    contributionDiff: [],
  },
  lockHash: "a".repeat(64),
  permissionDiffHash: "b".repeat(64),
  migrationPlanHash: "c".repeat(64),
  contributionDiffHash: "d".repeat(64),
  createdAt: "2026-08-03T00:00:00Z",
} as unknown as StoredCompositionLock;

describe("commandModel", () => {
  it("keeps command lifecycle separate and gates create on a current verified lock", () => {
    const idle = initialCommandState<StoredCompositionLock>(3);
    const running = beginCommand(idle, command, 3);
    const reconciling = reconcileCommand(running, lock);
    const succeeded = succeedCommand(reconciling, lock, 3);

    expect(running.phase).toBe("running");
    expect(reconciling.phase).toBe("reconciling");
    expect(canCreateInstallation(succeeded, 3)).toBe(true);

    const stale = markCommandInputChanged(succeeded, 4);
    expect(stale.stale).toBe(true);
    expect(stale.command).toBeNull();
    expect(canCreateInstallation(stale, 4)).toBe(false);
  });

  it("only permits same-command retry for an unknown outcome", () => {
    const running = beginCommand(initialCommandState(0), command, 0);
    const unknown = failCommand(running, error({
      kind: "network",
      outcomeUnknown: true,
      retryable: true,
      requiresRefresh: true,
    }));

    expect(unknown.phase).toBe("unknown_outcome");
    expect(unknown.command).toBe(command);
    expect(unknown.canRetrySameCommand).toBe(true);

    const conflict = failCommand(running, error({ kind: "conflict", isConflict: true }));
    expect(conflict.phase).toBe("conflict");
    expect(conflict.command).toBeNull();
    expect(conflict.canRetrySameCommand).toBe(false);
  });

  it("compares the complete resolve and persisted lock without depending on object key order", () => {
    const reordered = {
      ...lock,
      payload: { ...lock.payload },
    };
    expect(compositionLocksEqual(lock, reordered)).toBe(true);
    expect(
      compositionLocksEqual(lock, {
        ...reordered,
        lockHash: "sha256:different",
      } as StoredCompositionLock),
    ).toBe(false);
    expect(
      compositionLocksEqual(lock, {
        ...reordered,
        payload: { ...reordered.payload, resolvedAssets: [{ assetId: "unexpected" }] },
      } as unknown as StoredCompositionLock),
    ).toBe(false);
  });
});

function error(overrides: Partial<AssetControlError>): AssetControlError {
  return {
    name: "AssetControlError",
    message: "failed",
    kind: "unknown",
    status: null,
    code: null,
    recovery: "none",
    isConflict: false,
    requiresRefresh: false,
    retryable: false,
    outcomeUnknown: false,
    failureClosed: true,
    ...overrides,
  } as AssetControlError;
}
