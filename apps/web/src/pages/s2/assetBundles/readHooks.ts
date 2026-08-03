import { useCallback, useEffect, useRef, useState } from "react";
import { assetControlClient } from "../../../api/assetControl/client";
import { normalizeAssetControlError } from "../../../api/assetControl/errors";
import type {
  RegistryBundleDetail,
  RegistryBundleSummary,
  RegistryVersionDetail,
} from "../../../api/assetControl/registry";
import type {
  InstallationListResponse,
  InstallationResponse,
} from "../../../api/assetControl/types";
import type {
  AssetReadState,
  AssetReadStatus,
  InstallationPageRequest,
  RegistryBundleSelection,
  RegistryVersionSelection,
} from "./model";

type AssetReadSnapshot<T> = Omit<AssetReadState<T>, "reload">;

function idleSnapshot<T>(): AssetReadSnapshot<T> {
  return {
    data: null,
    status: "idle",
    error: null,
    refreshing: false,
    stale: false,
  };
}

function successfulStatus<T>(value: T, isEmpty: (value: T) => boolean): AssetReadStatus {
  return isEmpty(value) ? "empty" : "ready";
}

function errorStatus(kind: string): AssetReadStatus {
  if (kind === "forbidden") return "forbidden";
  if (kind === "not_visible_or_missing") return "not_visible_or_missing";
  return "error";
}

/**
 * Read-only request state machine shared by Registry and Installation hooks.
 * Request sequence and effect cleanup prevent late responses from replacing a
 * newer selection or reload.
 */
function useAssetRead<T>(
  requestKey: string | null,
  read: () => Promise<T>,
  isEmpty: (value: T) => boolean,
): AssetReadState<T> {
  const [snapshot, setSnapshot] = useState<AssetReadSnapshot<T>>(() => idleSnapshot<T>());
  const [reloadSequence, setReloadSequence] = useState(0);
  const requestSequence = useRef(0);
  const previousKey = useRef<string | null>(null);
  const readRef = useRef(read);
  const isEmptyRef = useRef(isEmpty);
  readRef.current = read;
  isEmptyRef.current = isEmpty;

  const reload = useCallback(() => {
    if (requestKey !== null) setReloadSequence((value) => value + 1);
  }, [requestKey]);

  useEffect(() => {
    const keyChanged = previousKey.current !== requestKey;
    previousKey.current = requestKey;
    const sequence = ++requestSequence.current;
    let active = true;

    if (requestKey === null) {
      setSnapshot(idleSnapshot<T>());
      return () => {
        active = false;
      };
    }

    setSnapshot((current) => {
      if (keyChanged || current.data === null) {
        return {
          data: null,
          status: "loading",
          error: null,
          refreshing: false,
          stale: false,
        };
      }
      return {
        data: current.data,
        status: successfulStatus(current.data, isEmptyRef.current),
        error: null,
        refreshing: true,
        stale: false,
      };
    });

    void Promise.resolve()
      .then(() => readRef.current())
      .then((data) => {
        if (!active || requestSequence.current !== sequence) return;
        setSnapshot({
          data,
          status: successfulStatus(data, isEmptyRef.current),
          error: null,
          refreshing: false,
          stale: false,
        });
      })
      .catch((cause: unknown) => {
        if (!active || requestSequence.current !== sequence) return;
        const error = normalizeAssetControlError(cause);
        const status = errorStatus(error.kind);
        const clearData =
          error.status === 401 ||
          error.status === 403 ||
          error.status === 404;
        setSnapshot((current) => ({
          data: clearData ? null : current.data,
          status,
          error,
          refreshing: false,
          stale: !clearData && current.data !== null,
        }));
      });

    return () => {
      active = false;
    };
  }, [requestKey, reloadSequence]);

  return { ...snapshot, reload };
}

const arrayIsEmpty = <T,>(items: T[]): boolean => items.length === 0;
const resourceIsNeverEmpty = (): boolean => false;
const installationListIsEmpty = (response: InstallationListResponse): boolean =>
  response.items.length === 0;

export function useRegistryBundles(): AssetReadState<RegistryBundleSummary[]> {
  return useAssetRead(
    "registry-bundles",
    () => assetControlClient.listRegistryBundles(),
    arrayIsEmpty,
  );
}

export function useRegistryBundle(
  selection: RegistryBundleSelection | null,
): AssetReadState<RegistryBundleDetail> {
  const requestKey = selection
    ? `registry-bundle:${selection.publisher}:${selection.bundleId}`
    : null;
  return useAssetRead(
    requestKey,
    () => {
      if (!selection) throw new Error("registry bundle selection is required");
      return assetControlClient.getRegistryBundle(
        selection.bundleId,
        selection.publisher,
      );
    },
    resourceIsNeverEmpty,
  );
}

export function useRegistryVersion(
  selection: RegistryVersionSelection | null,
): AssetReadState<RegistryVersionDetail> {
  const requestKey = selection
    ? `registry-version:${selection.publisher}:${selection.bundleId}:${selection.version}`
    : null;
  return useAssetRead(
    requestKey,
    () => {
      if (!selection) throw new Error("registry version selection is required");
      return assetControlClient.getRegistryBundleVersion(
        selection.bundleId,
        selection.version,
        selection.publisher,
      );
    },
    resourceIsNeverEmpty,
  );
}

export function useInstallations(
  request: InstallationPageRequest,
): AssetReadState<InstallationListResponse> {
  const requestKey = `installations:${request.state ?? "all"}:${request.limit}:${request.offset}`;
  return useAssetRead(
    requestKey,
    () => assetControlClient.listInstallations(request),
    installationListIsEmpty,
  );
}

export function useInstallation(
  installationId: string | null,
): AssetReadState<InstallationResponse> {
  const requestKey = installationId ? `installation:${installationId}` : null;
  return useAssetRead(
    requestKey,
    () => {
      if (!installationId) throw new Error("installation id is required");
      return assetControlClient.getInstallation(installationId);
    },
    resourceIsNeverEmpty,
  );
}
