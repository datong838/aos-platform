import { useState } from "react";

import type { InstallationState } from "../../api/assetControl/types";
import { S2Chrome } from "./shared";
import { BpBanner, BpTabs, BpToolbar } from "./blueprintUi";
import { InstallationDetail } from "./assetBundles/InstallationDetail";
import { InstallationPanel } from "./assetBundles/InstallationPanel";
import { RegistryPanel } from "./assetBundles/RegistryPanel";
import {
  useInstallation,
  useInstallations,
  useRegistryBundle,
  useRegistryBundles,
  useRegistryVersion,
} from "./assetBundles/readHooks";
import type {
  InstallationPageRequest,
  RegistryBundleSelection,
  RegistryVersionSelection,
} from "./assetBundles/model";

export const ASSET_VIEW_TABS = [
  { id: "registry", label: "资产 Registry" },
  { id: "installations", label: "安装管理（只读）" },
] as const;

type AssetView = (typeof ASSET_VIEW_TABS)[number]["id"];

const DEFAULT_INSTALLATION_PAGE: InstallationPageRequest = {
  limit: 20,
  offset: 0,
};

/** `/apollo/assets` compatibility entry for the canonical asset control plane. */
export function AssetBundlesPage() {
  const [activeView, setActiveView] = useState<AssetView>("registry");
  const [bundleSelection, setBundleSelection] =
    useState<RegistryBundleSelection | null>(null);
  const [versionSelection, setVersionSelection] =
    useState<RegistryVersionSelection | null>(null);
  const [installationRequest, setInstallationRequest] =
    useState<InstallationPageRequest>(DEFAULT_INSTALLATION_PAGE);
  const [installationId, setInstallationId] = useState<string | null>(null);

  const registryState = useRegistryBundles();
  const bundleDetailState = useRegistryBundle(bundleSelection);
  const versionDetailState = useRegistryVersion(versionSelection);
  const installationsState = useInstallations(installationRequest);
  const installationDetailState = useInstallation(installationId);

  function selectBundle(selection: RegistryBundleSelection) {
    setBundleSelection(selection);
    setVersionSelection(null);
  }

  function changeInstallationState(state: InstallationState | undefined) {
    setInstallationRequest((current) => ({ ...current, state, offset: 0 }));
    setInstallationId(null);
  }

  return (
    <S2Chrome
      title="FDE 资产包"
      lede="读取 Canonical Registry、安装记录与服务端证据；本阶段不提供安装写操作"
    >
      <BpBanner tone="info">
        当前页面只展示服务端真实事实，不使用 Mock 兜底。Resolve、创建、审批和安装动作将在后续受控阶段开放。
      </BpBanner>

      <div style={{ marginTop: "1rem" }}>
        <BpToolbar>
          <BpTabs
            tabs={[...ASSET_VIEW_TABS]}
            active={activeView}
            onChange={(view) => setActiveView(view as AssetView)}
          />
        </BpToolbar>
      </div>

      {activeView === "registry" ? (
        <RegistryPanel
          state={registryState}
          selected={bundleSelection}
          onSelect={selectBundle}
          detailState={bundleDetailState}
          versionState={versionDetailState}
          selectedVersion={versionSelection}
          onSelectVersion={setVersionSelection}
        />
      ) : (
        <div style={{ display: "grid", gap: "1rem" }}>
          <InstallationPanel
            state={installationsState}
            request={installationRequest}
            selectedInstallationId={installationId}
            onStateChange={changeInstallationState}
            onPageChange={(offset) =>
              setInstallationRequest((current) => ({ ...current, offset }))
            }
            onSelect={setInstallationId}
          />
          <InstallationDetail state={installationDetailState} />
        </div>
      )}
    </S2Chrome>
  );
}
