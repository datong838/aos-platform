import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AssetControlClient } from "../../../api/assetControl/client";
import type { IdempotencyKey } from "../../../api/assetControl/idempotency";
import type {
  InstallationResponse,
  InstallationState,
  StoredCompositionLock,
} from "../../../api/assetControl/types";
import { setConnectivity } from "../../../lib/offlineStore";
import {
  useInstallationActionCommands,
  type InstallationActionCommands,
  type InstallationActionDependencies,
} from "./installationActionHooks";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((onResolve, onReject) => {
    resolve = onResolve;
    reject = onReject;
  });
  return { promise, resolve, reject };
}

describe("M3-4 installation action controller", () => {
  let host: HTMLDivElement;
  let root: Root;
  let latest!: InstallationActionCommands;
  let displayed: InstallationResponse;
  let subject: string;
  let roles: string[];
  let dependencies: InstallationActionDependencies;
  let keySequence: number;
  const getInstallation = vi.fn();
  const getCompositionLock = vi.fn();
  const buildApproveRequest = vi.fn(buildApproveFromLock);
  const submitInstallation = vi.fn();
  const approveInstallation = vi.fn();
  const rejectInstallation = vi.fn();
  const applyInstallation = vi.fn();
  const verifyInstallation = vi.fn();
  const rollbackInstallation = vi.fn();
  const onSuccess = vi.fn();
  const onReconciled = vi.fn();

  function Probe() {
    latest = useInstallationActionCommands({
      installation: displayed,
      principal: { subject, roles },
      dependencies,
      onSuccess,
      onReconciled,
    });
    return null;
  }

  beforeEach(() => {
    setConnectivity("online", "installation-action-cumulative-test");
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    displayed = record("submitted");
    subject = "reviewer";
    roles = ["asset-install-approver"];
    keySequence = 0;
    for (const mock of [
      getInstallation,
      getCompositionLock,
      submitInstallation,
      approveInstallation,
      rejectInstallation,
      applyInstallation,
      verifyInstallation,
      rollbackInstallation,
      onSuccess,
      onReconciled,
    ]) {
      mock.mockReset();
    }
    buildApproveRequest.mockReset().mockImplementation(buildApproveFromLock);
    dependencies = {
      createCommand: () => ({
        idempotencyKey: `key-${++keySequence}` as IdempotencyKey,
      }),
      getInstallation,
      getCompositionLock,
      buildApproveRequest,
      submitInstallation,
      approveInstallation,
      rejectInstallation,
      applyInstallation,
      verifyInstallation,
      rollbackInstallation,
    };
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
    setConnectivity("unknown", "installation-action-cumulative-test-cleanup");
  });

  async function render() {
    await act(async () => root.render(<Probe />));
  }

  it("fails closed before reading when state, role, or subject is not eligible", async () => {
    roles = ["developer"];
    await render();
    expect(latest.availability.approve).toMatchObject({
      allowed: false,
      reason: "role_denied",
    });
    await act(async () => expect(await latest.execute("approve")).toBe(false));
    expect(getInstallation).not.toHaveBeenCalled();

    subject = "requester";
    roles = ["admin"];
    await act(async () => root.render(<Probe />));
    expect(latest.availability.reject.reason).toBe("maker_checker");
  });

  it.each([
    ["submit", "draft", "submitted", "developer"],
    ["reject", "submitted", "rejected", "asset-install-approver"],
    ["apply", "approved", "applied", "asset-installer"],
    ["verify", "applied", "active", "asset-installer"],
  ] as const)(
    "routes %s through the single controller with the current ETag",
    async (action, fromState, toState, role) => {
      displayed = record(fromState, 4, 6);
      roles = [role];
      const successor = record(toState, 5, 7);
      getInstallation
        .mockResolvedValueOnce(displayed)
        .mockResolvedValueOnce(successor);
      const actionMock = {
        submit: submitInstallation,
        reject: rejectInstallation,
        apply: applyInstallation,
        verify: verifyInstallation,
      }[action];
      actionMock.mockResolvedValueOnce(successor);
      await render();

      await act(async () =>
        expect(
          await latest.execute(
            action,
            action === "reject" ? { reason: " not approved " } : undefined,
          ),
        ).toBe(true),
      );

      if (action === "reject") {
        expect(actionMock).toHaveBeenCalledWith(
          displayed.installationId,
          { reason: "not approved" },
          { idempotencyKey: "key-1", etagVersion: 6 },
        );
      } else {
        expect(actionMock).toHaveBeenCalledWith(displayed.installationId, {
          idempotencyKey: "key-1",
          etagVersion: 6,
        });
      }
      expect(latest.state.data).toBe(successor);
    },
  );

  it("advances the full lifecycle with a fresh command key and the latest ETag at every step", async () => {
    const draft = record("draft", 1, 1);
    const submitted = record("submitted", 2, 2);
    const approved = record("approved", 3, 3);
    const applied = record("applied", 4, 4);
    const active = record("active", 5, 5);
    const rolledBack = record("rolled_back", 6, 6);
    displayed = draft;
    subject = "requester";
    roles = ["asset-installer"];
    getCompositionLock.mockResolvedValue(lock());
    await render();

    getInstallation.mockResolvedValueOnce(draft).mockResolvedValueOnce(submitted);
    submitInstallation.mockResolvedValueOnce(submitted);
    await act(async () => expect(await latest.execute("submit")).toBe(true));

    displayed = submitted;
    subject = "approver";
    roles = ["asset-install-approver"];
    await act(async () => root.render(<Probe />));
    getInstallation.mockResolvedValueOnce(submitted).mockResolvedValueOnce(approved);
    approveInstallation.mockResolvedValueOnce(approved);
    await act(async () => expect(await latest.execute("approve")).toBe(true));

    displayed = approved;
    subject = "installer";
    roles = ["asset-installer"];
    await act(async () => root.render(<Probe />));
    getInstallation.mockResolvedValueOnce(approved).mockResolvedValueOnce(applied);
    applyInstallation.mockResolvedValueOnce(applied);
    await act(async () => expect(await latest.execute("apply")).toBe(true));

    displayed = applied;
    await act(async () => root.render(<Probe />));
    getInstallation.mockResolvedValueOnce(applied).mockResolvedValueOnce(active);
    verifyInstallation.mockResolvedValueOnce(active);
    await act(async () => expect(await latest.execute("verify")).toBe(true));

    displayed = active;
    await act(async () => root.render(<Probe />));
    getInstallation.mockResolvedValueOnce(active).mockResolvedValueOnce(rolledBack);
    rollbackInstallation.mockResolvedValueOnce(rolledBack);
    await act(async () =>
      expect(await latest.execute("rollback", { reason: "unsafe" })).toBe(true),
    );

    expect(submitInstallation.mock.calls[0][1]).toEqual({
      idempotencyKey: "key-1",
      etagVersion: 1,
    });
    expect(approveInstallation.mock.calls[0][2]).toEqual({
      idempotencyKey: "key-2",
      etagVersion: 2,
    });
    expect(applyInstallation.mock.calls[0][1]).toEqual({
      idempotencyKey: "key-3",
      etagVersion: 3,
    });
    expect(verifyInstallation.mock.calls[0][1]).toEqual({
      idempotencyKey: "key-4",
      etagVersion: 4,
    });
    expect(rollbackInstallation.mock.calls[0][2]).toEqual({
      idempotencyKey: "key-5",
      etagVersion: 5,
    });
    expect(getInstallation).toHaveBeenCalledTimes(10);
    expect(onSuccess.mock.calls.map(([value]) => value.state)).toEqual([
      "submitted",
      "approved",
      "applied",
      "active",
      "rolled_back",
    ]);
    expect(latest.state).toMatchObject({
      phase: "succeeded",
      data: rolledBack,
      mutationConfirmed: true,
      attempt: null,
    });
  });

  it("uses one controller to block cross-actions and builds approve from GET current plus GET lock", async () => {
    const preflight = deferred<InstallationResponse>();
    const current = record("submitted", 4, 6);
    const approved = record("approved", 5, 7);
    getInstallation
      .mockReturnValueOnce(preflight.promise)
      .mockResolvedValueOnce(approved);
    getCompositionLock.mockResolvedValueOnce(lock());
    approveInstallation.mockResolvedValueOnce(approved);
    await render();

    let command!: Promise<boolean>;
    act(() => {
      command = latest.execute("approve");
    });
    await act(async () => expect(await latest.execute("reject", { reason: "no" })).toBe(false));
    expect(latest.state.phase).toBe("reconciling");

    await act(async () => preflight.resolve(current));
    await act(async () => expect(await command).toBe(true));
    expect(getCompositionLock).toHaveBeenCalledWith(
      current.current.compositionId,
      current.current.lockRevision,
    );
    expect(buildApproveRequest).toHaveBeenCalledWith(current, expect.any(Object));
    expect(approveInstallation).toHaveBeenCalledWith(
      current.installationId,
      {
        lockHash: current.current.lockHash,
        permissionDiffHash: current.current.permissionDiffHash,
        migrationPlanHash: current.current.migrationPlanHash,
        contributionDiffHash: current.current.contributionDiffHash,
      },
      { idempotencyKey: "key-1", etagVersion: 6 },
    );
    expect(getInstallation).toHaveBeenCalledTimes(2);
    expect(latest.state).toMatchObject({
      phase: "succeeded",
      mutationConfirmed: true,
      attempt: null,
    });
    expect(onSuccess).toHaveBeenCalledWith(approved);
  });

  it("requires a new confirmation when the preflight GET changes revision or hashes", async () => {
    displayed = record("submitted", 4, 6);
    const refreshed = record("submitted", 5, 7);
    getInstallation.mockResolvedValueOnce(refreshed);
    await render();

    await act(async () => expect(await latest.execute("approve")).toBe(false));

    expect(getCompositionLock).not.toHaveBeenCalled();
    expect(approveInstallation).not.toHaveBeenCalled();
    expect(latest.state).toMatchObject({
      phase: "conflict",
      reconciliation: "diverged",
      data: refreshed,
      attempt: null,
    });
    expect(onReconciled).toHaveBeenCalledWith(refreshed);
  });

  it.each([
    [409, "actual backend stale-CAS response"],
    [412, "compatibility-only simulated response"],
  ] as const)(
    "reads after %s (%s), clears the old key, and uses a new key for a new command",
    async (status, _responseContract) => {
    const source = record("submitted", 4, 6);
    const refreshed = record("submitted", 4, 7);
    const approved = record("approved", 5, 8);
    getInstallation
      .mockResolvedValueOnce(source)
      .mockResolvedValueOnce(refreshed)
      .mockResolvedValueOnce(refreshed)
      .mockResolvedValueOnce(approved);
    getCompositionLock.mockResolvedValue(lock());
    approveInstallation
      .mockRejectedValueOnce(
        apiError(status, status === 409 ? "REVISION_CONFLICT" : "ETAG_MISMATCH"),
      )
      .mockResolvedValueOnce(approved);
    await render();

    await act(async () => expect(await latest.execute("approve")).toBe(false));
    expect(latest.state).toMatchObject({
      phase: "conflict",
      attempt: null,
      canRecoverUnknown: false,
      data: refreshed,
    });
    expect(onReconciled).toHaveBeenCalledWith(refreshed);
    expect(await latest.recoverUnknown()).toBe(false);

    displayed = refreshed;
    await act(async () => root.render(<Probe />));
    await act(async () => expect(await latest.execute("approve")).toBe(true));
    expect(approveInstallation.mock.calls.map((call) => call[2].idempotencyKey)).toEqual([
      "key-1",
      "key-2",
    ]);
    expect(approveInstallation.mock.calls[1][2].etagVersion).toBe(7);
    },
  );

  it("keeps the full unknown attempt and confirms an exact event before replaying", async () => {
    displayed = record("active", 5, 8);
    subject = "installer";
    roles = ["asset-installer"];
    const successor = record("rolled_back", 6, 9, {
      fromRevision: 5,
      toRevision: 6,
      fromState: "active",
      toState: "rolled_back",
      actor: "installer",
      reason: "unsafe",
      evidenceType: "rollback",
    });
    getInstallation
      .mockResolvedValueOnce(displayed)
      .mockResolvedValueOnce(successor);
    rollbackInstallation.mockRejectedValueOnce(networkError());
    await render();

    await act(async () =>
      expect(await latest.execute("rollback", { reason: " unsafe " })).toBe(false),
    );
    expect(latest.state.phase).toBe("unknown_outcome");
    expect(latest.state.attempt).toMatchObject({
      action: "rollback",
      body: { reason: "unsafe" },
      source: { currentRevision: 5, etagVersion: 8 },
    });
    await act(async () => expect(await latest.execute("rollback", { reason: "again" })).toBe(false));

    await act(async () => expect(await latest.recoverUnknown()).toBe(true));
    expect(rollbackInstallation).toHaveBeenCalledTimes(1);
    expect(latest.state).toMatchObject({
      phase: "succeeded",
      reconciliation: "confirmed",
      attempt: null,
    });
  });

  it("recovers an unknown outcome by GET, replaying the exact envelope, then GET again", async () => {
    displayed = record("active", 5, 8);
    subject = "installer";
    roles = ["asset-installer"];
    const successor = record("rolled_back", 6, 9, {
      fromRevision: 5,
      toRevision: 6,
      fromState: "active",
      toState: "rolled_back",
      actor: "installer",
      reason: "unsafe",
      evidenceType: "rollback",
    });
    getInstallation
      .mockResolvedValueOnce(displayed)
      .mockResolvedValueOnce(displayed)
      .mockResolvedValueOnce(successor);
    rollbackInstallation
      .mockRejectedValueOnce(apiError(500, "SERVER_ERROR"))
      .mockResolvedValueOnce(successor);
    await render();

    await act(async () =>
      expect(await latest.execute("rollback", { reason: "unsafe" })).toBe(false),
    );
    await act(async () => expect(await latest.recoverUnknown()).toBe(true));

    expect(rollbackInstallation).toHaveBeenCalledTimes(2);
    expect(rollbackInstallation.mock.calls[0][1]).toEqual({ reason: "unsafe" });
    expect(rollbackInstallation.mock.calls[1][1]).toEqual({ reason: "unsafe" });
    expect(rollbackInstallation.mock.calls.map((call) => call[2])).toEqual([
      { idempotencyKey: "key-1", etagVersion: 8 },
      { idempotencyKey: "key-1", etagVersion: 8 },
    ]);
    expect(getInstallation).toHaveBeenCalledTimes(3);
    expect(onSuccess).toHaveBeenCalledWith(successor);
  });

  it("recovers an unknown step with the same envelope, then continues with a new key and ETag", async () => {
    const applied = record("applied", 4, 4);
    const active = record("active", 5, 5, {
      fromRevision: 4,
      toRevision: 5,
      fromState: "applied",
      toState: "active",
      actor: "installer",
      reason: null,
      evidenceType: "verification",
    });
    const rolledBack = record("rolled_back", 6, 6, {
      fromRevision: 5,
      toRevision: 6,
      fromState: "active",
      toState: "rolled_back",
      actor: "installer",
      reason: "unsafe",
      evidenceType: "rollback",
    });
    displayed = applied;
    subject = "installer";
    roles = ["asset-installer"];
    getInstallation
      .mockResolvedValueOnce(applied)
      .mockResolvedValueOnce(applied)
      .mockResolvedValueOnce(active)
      .mockResolvedValueOnce(active)
      .mockResolvedValueOnce(rolledBack);
    verifyInstallation
      .mockRejectedValueOnce(networkError())
      .mockResolvedValueOnce(active);
    rollbackInstallation.mockResolvedValueOnce(rolledBack);
    await render();

    await act(async () => expect(await latest.execute("verify")).toBe(false));
    expect(latest.state).toMatchObject({
      phase: "unknown_outcome",
      canRecoverUnknown: true,
    });
    await act(async () => expect(await latest.recoverUnknown()).toBe(true));

    displayed = active;
    await act(async () => root.render(<Probe />));
    await act(async () =>
      expect(await latest.execute("rollback", { reason: "unsafe" })).toBe(true),
    );

    expect(verifyInstallation.mock.calls.map((call) => call[1])).toEqual([
      { idempotencyKey: "key-1", etagVersion: 4 },
      { idempotencyKey: "key-1", etagVersion: 4 },
    ]);
    expect(rollbackInstallation).toHaveBeenCalledWith(
      active.installationId,
      { reason: "unsafe" },
      { idempotencyKey: "key-2", etagVersion: 5 },
    );
    expect(getInstallation).toHaveBeenCalledTimes(5);
    expect(latest.state).toMatchObject({
      phase: "succeeded",
      data: rolledBack,
      attempt: null,
      mutationConfirmed: true,
    });
  });

  it("turns a diverged unknown recovery into conflict without replaying", async () => {
    displayed = record("active", 5, 8);
    subject = "installer";
    roles = ["asset-installer"];
    const diverged = record("rolled_back", 7, 10, {
      fromRevision: 6,
      toRevision: 7,
      fromState: "active",
      toState: "rolled_back",
      actor: "another-installer",
      reason: "other command",
    });
    getInstallation
      .mockResolvedValueOnce(displayed)
      .mockResolvedValueOnce(diverged);
    rollbackInstallation.mockRejectedValueOnce(networkError());
    await render();

    await act(async () =>
      expect(await latest.execute("rollback", { reason: "unsafe" })).toBe(false),
    );
    await act(async () => expect(await latest.recoverUnknown()).toBe(false));

    expect(rollbackInstallation).toHaveBeenCalledTimes(1);
    expect(latest.state).toMatchObject({
      phase: "conflict",
      reconciliation: "diverged",
      attempt: null,
      data: diverged,
    });
    expect(onReconciled).toHaveBeenCalledWith(diverged);
  });

  it("does not lose the attempt when the explicit recovery GET fails", async () => {
    displayed = record("active", 5, 8);
    subject = "installer";
    roles = ["asset-installer"];
    getInstallation
      .mockResolvedValueOnce(displayed)
      .mockRejectedValueOnce(networkError());
    rollbackInstallation.mockRejectedValueOnce(networkError());
    await render();

    await act(async () =>
      expect(await latest.execute("rollback", { reason: "unsafe" })).toBe(false),
    );
    const originalAttempt = latest.state.attempt;
    await act(async () => expect(await latest.recoverUnknown()).toBe(false));
    expect(latest.state).toMatchObject({
      phase: "unknown_outcome",
      canRecoverUnknown: true,
      reconciliation: "unavailable",
    });
    expect(latest.state.attempt).toBe(originalAttempt);
    expect(rollbackInstallation).toHaveBeenCalledTimes(1);
  });

  it("keeps wrong-role, self-approval, and offline commands at zero transport POSTs", async () => {
    const transport = vi.fn();
    const offlineClient = new AssetControlClient({
      fetch: transport,
      getBaseUrl: () => "http://asset-control.test",
      getAuthHeaders: () => ({}),
    });

    roles = ["developer"];
    await render();
    await act(async () => expect(await latest.execute("approve")).toBe(false));

    subject = "requester";
    roles = ["asset-install-approver"];
    await act(async () => root.render(<Probe />));
    await act(async () => expect(await latest.execute("approve")).toBe(false));
    expect(getInstallation).not.toHaveBeenCalled();
    expect(approveInstallation).not.toHaveBeenCalled();

    displayed = record("draft", 1, 1);
    roles = ["developer"];
    dependencies = {
      ...dependencies,
      submitInstallation: (installationId, options) =>
        offlineClient.submitInstallation(installationId, options),
    };
    getInstallation.mockResolvedValueOnce(displayed);
    setConnectivity("offline", "installation-action-cumulative-test");
    await act(async () => root.render(<Probe />));
    await act(async () => expect(await latest.execute("submit")).toBe(false));

    expect(getInstallation).toHaveBeenCalledTimes(1);
    expect(transport).not.toHaveBeenCalled();
    expect(submitInstallation).not.toHaveBeenCalled();
    expect(latest.state).toMatchObject({
      phase: "error",
      error: { kind: "offline_mutation_disabled" },
      attempt: null,
      mutationConfirmed: false,
    });
  });
});

function apiError(status: number, code: string) {
  return Object.assign(new Error(code), {
    status,
    body: { code, message: code, details: null, traceId: `trace-${status}` },
  });
}

function networkError() {
  return apiError(0, "NETWORK");
}

function record(
  state: InstallationState,
  currentRevision = 4,
  etagVersion = 6,
  event?: {
    fromRevision: number;
    toRevision: number;
    fromState: InstallationState;
    toState: InstallationState;
    actor: string;
    reason: string | null;
    evidenceType?: "dry_apply" | "verification" | "rollback";
  },
): InstallationResponse {
  return {
    installationId: "11111111-1111-4111-8111-111111111111",
    displayName: "Commerce",
    state,
    currentRevision,
    activeRevision: state === "active" ? currentRevision : null,
    previousActiveRevision: null,
    etagVersion,
    current: {
      installationId: "11111111-1111-4111-8111-111111111111",
      revision: currentRevision,
      parentRevision: currentRevision === 1 ? null : currentRevision - 1,
      state,
      compositionId: "22222222-2222-4222-8222-222222222222",
      lockRevision: 3,
      lockHash: "sha256:lock",
      permissionDiffHash: "sha256:permission",
      migrationPlanHash: "sha256:migration",
      contributionDiffHash: "sha256:contribution",
      overlayRevision: "overlay-1",
      requestedBy: "requester",
      decisionId: null,
      createdAt: "2026-08-03T00:00:00Z",
    },
    decision: null,
    events: event
      ? [{
          sequence: 1,
          evidence: event.evidenceType
            ? {
                type: event.evidenceType,
                evidenceRef: "evidence://server-generated",
                evidenceHash: "sha256:evidence",
                status: "valid" as const,
                observedAt: "2026-08-03T00:00:00Z",
              }
            : null,
          createdAt: "2026-08-03T00:00:00Z",
          ...event,
        }]
      : [],
    createdAt: "2026-08-03T00:00:00Z",
    updatedAt: "2026-08-03T00:00:00Z",
  };
}

function lock(): StoredCompositionLock {
  return {
    compositionId: "22222222-2222-4222-8222-222222222222",
    revision: 3,
    payload: {} as StoredCompositionLock["payload"],
    lockHash: "sha256:lock",
    permissionDiffHash: "sha256:permission",
    migrationPlanHash: "sha256:migration",
    contributionDiffHash: "sha256:contribution",
    createdAt: "2026-08-03T00:00:00Z",
  };
}

function buildApproveFromLock(
  installation: InstallationResponse,
  currentLock: StoredCompositionLock,
) {
  if (
    currentLock.compositionId !== installation.current.compositionId ||
    currentLock.revision !== installation.current.lockRevision ||
    currentLock.lockHash !== installation.current.lockHash ||
    currentLock.permissionDiffHash !== installation.current.permissionDiffHash ||
    currentLock.migrationPlanHash !== installation.current.migrationPlanHash ||
    currentLock.contributionDiffHash !== installation.current.contributionDiffHash
  ) {
    throw new Error("lock mismatch");
  }
  return {
    lockHash: currentLock.lockHash,
    permissionDiffHash: currentLock.permissionDiffHash,
    migrationPlanHash: currentLock.migrationPlanHash,
    contributionDiffHash: currentLock.contributionDiffHash,
  };
}
