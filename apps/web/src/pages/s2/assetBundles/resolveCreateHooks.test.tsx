import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type {
  CompositionRequest,
  InstallationResponse,
  StoredCompositionLock,
} from "../../../api/assetControl/types";
import type { IdempotencyKey } from "../../../api/assetControl/idempotency";
import {
  useResolveCreateCommands,
  type ResolveCreateCommands,
  type ResolveCreateDependencies,
} from "./resolveCreateHooks";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const request = {
  requested: [{ publisher: "aos", id: "commerce", version: "1.0.0" }],
  platformApiVersion: "v1",
  platformRelease: "2026.08",
  environment: "prod",
} satisfies CompositionRequest;

const lock = {
  compositionId: "composition-1",
  revision: 7,
  payload: { request },
  lockHash: "sha256:lock",
  permissionDiffHash: "sha256:permission",
  migrationPlanHash: "sha256:migration",
  contributionDiffHash: "sha256:contribution",
  createdAt: "2026-08-03T00:00:00Z",
} as unknown as StoredCompositionLock;

const installation = {
  installationId: "installation-1",
  displayName: "Commerce",
  state: "draft",
  currentRevision: 1,
  activeRevision: null,
  previousActiveRevision: null,
  etagVersion: 1,
  createdAt: "2026-08-03T00:00:00Z",
  updatedAt: "2026-08-03T00:00:00Z",
} as unknown as InstallationResponse;

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((onResolve, onReject) => {
    resolve = onResolve;
    reject = onReject;
  });
  return { promise, resolve, reject };
}

function networkError() {
  return Object.assign(new Error("network"), {
    status: 0,
    body: { code: "NETWORK", message: "network", details: null, traceId: "trace" },
  });
}

describe("M3-3 resolve/create command hooks", () => {
  let host: HTMLDivElement;
  let root: Root;
  let latest!: ResolveCreateCommands;
  let dependencies: ResolveCreateDependencies;
  let keySequence: number;
  const resolveComposition = vi.fn();
  const getCompositionLock = vi.fn();
  const createInstallation = vi.fn();
  const onCreateSuccess = vi.fn();

  function Probe() {
    latest = useResolveCreateCommands({ dependencies, onCreateSuccess });
    return null;
  }

  async function render() {
    await act(async () => root.render(<Probe />));
  }

  async function resolveSuccessfully() {
    resolveComposition.mockResolvedValueOnce(lock);
    getCompositionLock.mockResolvedValueOnce({ ...lock, payload: { ...lock.payload } });
    await act(async () => {
      expect(await latest.resolve(request)).toBe(true);
    });
  }

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    keySequence = 0;
    resolveComposition.mockReset();
    getCompositionLock.mockReset();
    createInstallation.mockReset();
    onCreateSuccess.mockReset();
    dependencies = {
      createCommand: () => ({
        idempotencyKey: `key-${++keySequence}` as IdempotencyKey,
      }),
      resolveComposition,
      getCompositionLock,
      createInstallation,
    };
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  it("blocks duplicate clicks while running/reconciling and only succeeds after GET equality", async () => {
    const pendingResolve = deferred<StoredCompositionLock>();
    const pendingGet = deferred<StoredCompositionLock>();
    resolveComposition.mockReturnValueOnce(pendingResolve.promise);
    getCompositionLock.mockReturnValueOnce(pendingGet.promise);
    await render();

    let first!: Promise<boolean>;
    await act(async () => {
      first = latest.resolve(request);
      expect(await latest.resolve(request)).toBe(false);
    });
    expect(latest.resolveState.phase).toBe("running");
    expect(resolveComposition).toHaveBeenCalledTimes(1);

    await act(async () => pendingResolve.resolve(lock));
    expect(latest.resolveState.phase).toBe("reconciling");
    await act(async () => expect(await latest.resolve(request)).toBe(false));
    expect(resolveComposition).toHaveBeenCalledTimes(1);

    await act(async () => pendingGet.resolve({ ...lock, payload: { ...lock.payload } }));
    await expect(first).resolves.toBe(true);
    expect(latest.resolveState.phase).toBe("succeeded");
    expect(latest.canCreate).toBe(true);
  });

  it("fails closed when the resolve response differs from the persisted lock", async () => {
    resolveComposition.mockResolvedValueOnce(lock);
    getCompositionLock.mockResolvedValueOnce({ ...lock, lockHash: "sha256:different" });
    await render();

    await act(async () => expect(await latest.resolve(request)).toBe(false));
    expect(latest.resolveState.phase).toBe("error");
    expect(latest.canCreate).toBe(false);
  });

  it("retries an unknown resolve outcome with the same key and gives a new command a new key", async () => {
    resolveComposition
      .mockRejectedValueOnce(networkError())
      .mockResolvedValueOnce(lock)
      .mockResolvedValueOnce(lock);
    getCompositionLock.mockResolvedValue({ ...lock, payload: { ...lock.payload } });
    await render();

    await act(async () => expect(await latest.resolve(request)).toBe(false));
    expect(latest.resolveState.phase).toBe("unknown_outcome");
    await act(async () => expect(await latest.retryResolve()).toBe(true));
    await act(async () => expect(await latest.resolve(request)).toBe(true));

    const keys = resolveComposition.mock.calls.map((call) => call[1].idempotencyKey);
    expect(keys).toEqual(["key-1", "key-1", "key-2"]);
  });

  it("marks a verified lock stale after input changes and ignores an obsolete in-flight response", async () => {
    await render();
    await resolveSuccessfully();

    act(() => expect(latest.markInputChanged()).toBe(true));
    expect(latest.inputRevision).toBe(1);
    expect(latest.resolveState.stale).toBe(true);
    expect(latest.canCreate).toBe(false);

    const pending = deferred<StoredCompositionLock>();
    resolveComposition.mockReturnValueOnce(pending.promise);
    let obsolete!: Promise<boolean>;
    await act(async () => {
      obsolete = latest.resolve(request);
    });
    act(() => expect(latest.markInputChanged()).toBe(true));
    await act(async () => pending.resolve(lock));
    await expect(obsolete).resolves.toBe(false);
    expect(getCompositionLock).toHaveBeenCalledTimes(1);
    expect(latest.inputRevision).toBe(2);
    expect(latest.canCreate).toBe(false);
  });

  it("creates only from the current verified lock, retries unknown outcome with the same key, and calls success callback", async () => {
    await render();
    expect(await latest.create({ overlayRevision: "overlay-1", displayName: "Commerce" })).toBe(false);
    await resolveSuccessfully();

    createInstallation
      .mockRejectedValueOnce(networkError())
      .mockResolvedValueOnce(installation);
    await act(async () =>
      expect(
        await latest.create({ overlayRevision: "overlay-1", displayName: "Commerce" }),
      ).toBe(false),
    );
    expect(latest.createState.phase).toBe("unknown_outcome");
    expect(latest.markInputChanged()).toBe(false);

    await act(async () => expect(await latest.retryCreate()).toBe(true));
    expect(createInstallation).toHaveBeenCalledTimes(2);
    expect(createInstallation.mock.calls[0][0]).toEqual({
      compositionId: lock.compositionId,
      lockRevision: lock.revision,
      overlayRevision: "overlay-1",
      displayName: "Commerce",
    });
    expect(createInstallation.mock.calls[0][1].idempotencyKey).toBe("key-2");
    expect(createInstallation.mock.calls[1][1].idempotencyKey).toBe("key-2");
    expect(onCreateSuccess).toHaveBeenCalledWith(installation);
  });
});
