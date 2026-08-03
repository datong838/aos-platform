import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type {
  RegistryBundleDetail,
  RegistryBundleSummary,
  RegistryVersionDetail,
} from "../../../api/assetControl/registry";
import {
  REGISTRY_BUNDLE_DETAIL_FIXTURE,
  REGISTRY_BUNDLE_LIST_FIXTURE,
  REGISTRY_VERSION_DETAIL_FIXTURE,
} from "../../../api/assetControl/registryFixtures";
import type {
  InstallationListResponse,
  InstallationResponse,
} from "../../../api/assetControl/types";
import type { AssetReadState, RegistryBundleSelection } from "./model";

const client = vi.hoisted(() => ({
  listRegistryBundles: vi.fn(),
  getRegistryBundle: vi.fn(),
  getRegistryBundleVersion: vi.fn(),
  listInstallations: vi.fn(),
  getInstallation: vi.fn(),
}));

vi.mock("../../../api/assetControl/client", () => ({
  assetControlClient: client,
}));

import {
  useInstallation,
  useInstallations,
  useRegistryBundle,
  useRegistryBundles,
  useRegistryVersion,
} from "./readHooks";

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

function apiError(status: number, code: string): Error {
  return Object.assign(new Error(code), {
    status,
    body: { code, message: code, details: null, traceId: `trace-${status}` },
  });
}

const installation = {
  installationId: "installation-1",
} as InstallationResponse;

describe("M3-2 asset read hooks", () => {
  let host: HTMLDivElement;
  let root: Root;

  async function flush() {
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });
  }

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    Object.values(client).forEach((mock) => mock.mockReset());
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  it("starts Registry list in loading and maps a bare [] to empty", async () => {
    const pending = deferred<RegistryBundleSummary[]>();
    client.listRegistryBundles.mockReturnValue(pending.promise);
    let latest!: AssetReadState<RegistryBundleSummary[]>;

    function Probe() {
      latest = useRegistryBundles();
      return null;
    }

    act(() => root.render(<Probe />));
    expect(latest).toMatchObject({
      data: null,
      status: "loading",
      refreshing: false,
      stale: false,
    });

    pending.resolve([]);
    await flush();
    expect(latest).toMatchObject({
      data: [],
      status: "empty",
      error: null,
      refreshing: false,
      stale: false,
    });
  });

  it("marks reload as refreshing and preserves stale data after 500", async () => {
    const refresh = deferred<RegistryBundleSummary[]>();
    client.listRegistryBundles
      .mockResolvedValueOnce(REGISTRY_BUNDLE_LIST_FIXTURE)
      .mockReturnValueOnce(refresh.promise);
    let latest!: AssetReadState<RegistryBundleSummary[]>;

    function Probe() {
      latest = useRegistryBundles();
      return null;
    }

    act(() => root.render(<Probe />));
    await flush();
    expect(latest.status).toBe("ready");

    act(() => latest.reload());
    expect(latest).toMatchObject({
      data: REGISTRY_BUNDLE_LIST_FIXTURE,
      status: "ready",
      refreshing: true,
      stale: false,
    });

    refresh.reject(apiError(500, "INTERNAL_ERROR"));
    await flush();
    expect(latest).toMatchObject({
      data: REGISTRY_BUNDLE_LIST_FIXTURE,
      status: "error",
      refreshing: false,
      stale: true,
    });
  });

  it("maps an initial network failure to error without stale data", async () => {
    client.listRegistryBundles.mockRejectedValue(
      Object.assign(new Error("Failed to fetch"), {
        status: 0,
        body: {
          code: "NETWORK",
          message: "Failed to fetch",
          details: null,
          traceId: "",
        },
      }),
    );
    let latest!: AssetReadState<RegistryBundleSummary[]>;

    function Probe() {
      latest = useRegistryBundles();
      return null;
    }

    act(() => root.render(<Probe />));
    await flush();
    expect(latest).toMatchObject({
      data: null,
      status: "error",
      refreshing: false,
      stale: false,
    });
    expect(latest.error?.kind).toBe("network");
  });

  it.each([
    [401, "AUTH_REQUIRED", "error"],
    [403, "MARKING_ACCESS_DENIED", "forbidden"],
    [404, "NOT_FOUND", "not_visible_or_missing"],
  ] as const)("clears old detail data after HTTP %i", async (status, code, expectedStatus) => {
    const denied = deferred<RegistryBundleDetail>();
    client.getRegistryBundle
      .mockResolvedValueOnce(REGISTRY_BUNDLE_DETAIL_FIXTURE)
      .mockReturnValueOnce(denied.promise);
    let latest!: AssetReadState<RegistryBundleDetail>;
    const selection = { publisher: "aos", bundleId: "solution.example" };

    function Probe() {
      latest = useRegistryBundle(selection);
      return null;
    }

    act(() => root.render(<Probe />));
    await flush();
    expect(latest.data).toBe(REGISTRY_BUNDLE_DETAIL_FIXTURE);

    act(() => latest.reload());
    denied.reject(apiError(status, code));
    await flush();
    expect(latest).toMatchObject({
      data: null,
      status: expectedStatus,
      refreshing: false,
      stale: false,
    });
  });

  it("prevents an older Registry detail response from replacing a new selection", async () => {
    const oldRequest = deferred<RegistryBundleDetail>();
    const newRequest = deferred<RegistryBundleDetail>();
    const oldSelection = { publisher: "aos", bundleId: "solution.old" };
    const newSelection = { publisher: "aos", bundleId: "solution.new" };
    const oldDetail = {
      ...REGISTRY_BUNDLE_DETAIL_FIXTURE,
      bundleId: "solution.old",
    };
    const newDetail = {
      ...REGISTRY_BUNDLE_DETAIL_FIXTURE,
      bundleId: "solution.new",
    };
    client.getRegistryBundle.mockImplementation((bundleId: string) =>
      bundleId === "solution.old" ? oldRequest.promise : newRequest.promise,
    );
    let latest!: AssetReadState<RegistryBundleDetail>;

    function Probe({ selection }: { selection: RegistryBundleSelection }) {
      latest = useRegistryBundle(selection);
      return null;
    }

    act(() => root.render(<Probe selection={oldSelection} />));
    act(() => root.render(<Probe selection={newSelection} />));
    expect(latest.status).toBe("loading");
    expect(latest.data).toBeNull();

    newRequest.resolve(newDetail);
    await flush();
    expect(latest.data?.bundleId).toBe("solution.new");

    oldRequest.resolve(oldDetail);
    await flush();
    expect(latest.data?.bundleId).toBe("solution.new");
  });

  it("maps Installation items=[] to empty and forwards page parameters", async () => {
    const response: InstallationListResponse = {
      items: [],
      total: 0,
      limit: 20,
      offset: 40,
    };
    client.listInstallations.mockResolvedValue(response);
    let latest!: AssetReadState<InstallationListResponse>;

    function Probe() {
      latest = useInstallations({ state: "draft", limit: 20, offset: 40 });
      return null;
    }

    act(() => root.render(<Probe />));
    await flush();
    expect(client.listInstallations).toHaveBeenCalledWith({
      state: "draft",
      limit: 20,
      offset: 40,
    });
    expect(latest).toMatchObject({ data: response, status: "empty" });
  });

  it("uses only the Registry version and Installation read methods", async () => {
    client.getRegistryBundleVersion.mockResolvedValue(
      REGISTRY_VERSION_DETAIL_FIXTURE,
    );
    client.getInstallation.mockResolvedValue(installation);
    let versionState!: AssetReadState<RegistryVersionDetail>;
    let installationState!: AssetReadState<InstallationResponse>;

    function Probe() {
      versionState = useRegistryVersion({
        publisher: "aos",
        bundleId: "solution.example",
        version: "1.0.0",
      });
      installationState = useInstallation("installation-1");
      return null;
    }

    act(() => root.render(<Probe />));
    await flush();
    expect(client.getRegistryBundleVersion).toHaveBeenCalledWith(
      "solution.example",
      "1.0.0",
      "aos",
    );
    expect(client.getInstallation).toHaveBeenCalledWith("installation-1");
    expect(versionState).toMatchObject({
      data: REGISTRY_VERSION_DETAIL_FIXTURE,
      status: "ready",
    });
    expect(installationState).toMatchObject({ data: installation, status: "ready" });
  });

  it("keeps nullable detail selections idle without issuing reads", () => {
    let bundleState!: AssetReadState<RegistryBundleDetail>;
    let versionState!: AssetReadState<RegistryVersionDetail>;
    let installationState!: AssetReadState<InstallationResponse>;

    function Probe() {
      bundleState = useRegistryBundle(null);
      versionState = useRegistryVersion(null);
      installationState = useInstallation(null);
      return null;
    }

    act(() => root.render(<Probe />));
    expect(bundleState.status).toBe("idle");
    expect(versionState.status).toBe("idle");
    expect(installationState.status).toBe("idle");
    expect(client.getRegistryBundle).not.toHaveBeenCalled();
    expect(client.getRegistryBundleVersion).not.toHaveBeenCalled();
    expect(client.getInstallation).not.toHaveBeenCalled();
  });
});
