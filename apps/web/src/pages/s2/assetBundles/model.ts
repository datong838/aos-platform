import type { AssetControlError } from "../../../api/assetControl/errors";
import type { InstallationState } from "../../../api/assetControl/types";

export type AssetReadStatus =
  | "idle"
  | "loading"
  | "ready"
  | "empty"
  | "forbidden"
  | "not_visible_or_missing"
  | "error";

/** Shared read-only state. Mutation capabilities deliberately do not belong here. */
export interface AssetReadState<T> {
  data: T | null;
  status: AssetReadStatus;
  error: AssetControlError | null;
  refreshing: boolean;
  stale: boolean;
  reload: () => void;
}

export interface RegistryBundleSelection {
  publisher: string;
  bundleId: string;
}

export interface RegistryVersionSelection extends RegistryBundleSelection {
  version: string;
}

export interface InstallationPageRequest {
  state?: InstallationState;
  limit: number;
  offset: number;
}

export interface InstallationPageControls {
  hasPrevious: boolean;
  hasNext: boolean;
  previousOffset: number;
  nextOffset: number;
}

export function installationPageControls(
  total: number,
  limit: number,
  offset: number,
): InstallationPageControls {
  const safeTotal = Math.max(0, total);
  const safeLimit = Math.max(1, limit);
  const safeOffset = Math.max(0, offset);
  return {
    hasPrevious: safeOffset > 0,
    hasNext: safeOffset + safeLimit < safeTotal,
    previousOffset: Math.max(0, safeOffset - safeLimit),
    nextOffset: safeOffset + safeLimit,
  };
}
