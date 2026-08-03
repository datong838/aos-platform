import { useState } from "react";

import type {
  CompositionRequest,
  InstallationState,
  StoredCompositionLock,
} from "../../api/assetControl/types";
import { S2Chrome } from "./shared";
import { BpBanner, BpTabs, BpToolbar } from "./blueprintUi";
import { InstallationDetail } from "./assetBundles/InstallationDetail";
import { InstallationPanel } from "./assetBundles/InstallationPanel";
import { RegistryPanel } from "./assetBundles/RegistryPanel";
import { CompositionDependencyPanel } from "./assetBundles/CompositionDependencyPanel";
import { CompositionDiffPanel } from "./assetBundles/CompositionDiffPanel";
import { CompositionLockDetail } from "./assetBundles/CompositionLockDetail";
import { CompositionPanel } from "./assetBundles/CompositionPanel";
import {
  useInstallation,
  useInstallations,
  useRegistryBundle,
  useRegistryBundles,
  useRegistryVersion,
} from "./assetBundles/readHooks";
import {
  useResolveCreateCommands,
  type CreateInstallationDraft,
} from "./assetBundles/resolveCreateHooks";
import type {
  AssetReadState,
  InstallationPageRequest,
  RegistryBundleSelection,
  RegistryVersionSelection,
} from "./assetBundles/model";

export const ASSET_VIEW_TABS = [
  { id: "registry", label: "资产 Registry" },
  { id: "composition", label: "组合预检与创建" },
  { id: "installations", label: "安装管理（只读）" },
] as const;

type AssetView = (typeof ASSET_VIEW_TABS)[number]["id"];

const DEFAULT_INSTALLATION_PAGE: InstallationPageRequest = {
  limit: 20,
  offset: 0,
};

const DEFAULT_COMPOSITION_REQUEST: CompositionRequest = {
  requested: [],
  platformApiVersion: "1.0.0",
  platformRelease: "2026.08",
  environment: "dev",
};

const DEFAULT_CREATE_DRAFT: CreateInstallationDraft = {
  overlayRevision: "overlay-1",
  displayName: "",
};

function resolveReadState(
  state: ReturnType<typeof useResolveCreateCommands>["resolveState"],
  reload: () => void,
): AssetReadState<StoredCompositionLock> {
  const status = (() => {
    if (state.phase === "idle") return "idle";
    if (state.phase === "running" || state.phase === "reconciling") return "loading";
    if (state.phase === "succeeded") return "ready";
    if (state.phase === "forbidden") return "forbidden";
    if (state.phase === "not_visible_or_missing") return "not_visible_or_missing";
    return "error";
  })();
  return {
    data: state.phase === "succeeded" ? state.data : null,
    status,
    error: state.error,
    refreshing: state.phase === "reconciling",
    stale: state.stale,
    reload,
  };
}

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
  const [compositionRequest, setCompositionRequest] =
    useState<CompositionRequest>(DEFAULT_COMPOSITION_REQUEST);
  const [createDraft, setCreateDraft] =
    useState<CreateInstallationDraft>(DEFAULT_CREATE_DRAFT);

  const registryState = useRegistryBundles();
  const bundleDetailState = useRegistryBundle(bundleSelection);
  const versionDetailState = useRegistryVersion(versionSelection);
  const installationsState = useInstallations(installationRequest);
  const installationDetailState = useInstallation(installationId);
  const commands = useResolveCreateCommands({
    onCreateSuccess: (installation) => {
      setInstallationId(installation.installationId);
      installationsState.reload();
      setActiveView("installations");
    },
  });

  const lockReadState = resolveReadState(commands.resolveState, () => {
    void (commands.resolveState.canRetrySameCommand
      ? commands.retryResolve()
      : commands.resolve(compositionRequest));
  });

  function selectBundle(selection: RegistryBundleSelection) {
    if (!commands.markInputChanged()) return;
    setBundleSelection(selection);
    setVersionSelection(null);
    setCompositionRequest((current) => ({ ...current, requested: [] }));
  }

  function changeInstallationState(state: InstallationState | undefined) {
    setInstallationRequest((current) => ({ ...current, state, offset: 0 }));
    setInstallationId(null);
  }

  function selectVersion(selection: RegistryVersionSelection) {
    if (!commands.markInputChanged()) return;
    setVersionSelection(selection);
    setCompositionRequest((current) => ({
      ...current,
      requested: [{
        publisher: selection.publisher,
        id: selection.bundleId,
        version: selection.version,
      }],
    }));
  }

  function changeCompositionRequest(request: CompositionRequest) {
    if (!commands.markInputChanged()) return;
    setCompositionRequest(request);
  }

  const selectedVersionIsEligible = Boolean(
    versionDetailState.status === "ready" &&
    versionDetailState.data?.status === "published" &&
    versionDetailState.data.signature,
  );
  const resolveDisabledReason = !versionSelection
    ? "请先从 Registry 选择一个版本"
    : versionDetailState.status === "loading"
      ? "正在核验版本事实"
      : !selectedVersionIsEligible
        ? "只有已发布且已签名的版本可以进入组合预检"
        : null;

  return (
    <S2Chrome
      title="FDE 资产包"
      lede="读取 Canonical Registry，执行服务端组合预检，并创建 draft Installation"
    >
      <BpBanner tone="info">
        当前页面不使用 Mock 兜底。Resolve、Lock/Diff 与 draft 创建使用现有 Canonical API；审批和安装动作仍不可达。
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
          onSelectVersion={selectVersion}
        />
      ) : activeView === "composition" ? (
        <div style={{ display: "grid", gap: "1rem" }}>
          <CompositionPanel
            request={compositionRequest}
            resolving={commands.resolveState.phase === "running" || commands.resolveState.phase === "reconciling"}
            disabledReason={resolveDisabledReason}
            onRequestChange={changeCompositionRequest}
            onResolve={() => { void commands.resolve(compositionRequest); }}
          />
          <CompositionLockDetail state={lockReadState} />
          {commands.resolveState.phase === "succeeded" && commands.resolveState.data && !commands.resolveState.stale && (
            <>
              <CompositionDependencyPanel lock={commands.resolveState.data} />
              <CompositionDiffPanel lock={commands.resolveState.data} />
              <section aria-label="创建 Draft Installation" style={{ border: "1px solid var(--aos-border)", borderRadius: 3, padding: 12 }}>
                <h3>创建 Draft Installation</h3>
                <p>只创建 draft；不会自动提交、审批、Apply 或 Verify。</p>
                <label>Display name<input aria-label="Installation display name" value={createDraft.displayName} onChange={(event) => setCreateDraft((current) => ({ ...current, displayName: event.target.value }))} /></label>
                <label>Overlay revision<input aria-label="Overlay revision" value={createDraft.overlayRevision} onChange={(event) => setCreateDraft((current) => ({ ...current, overlayRevision: event.target.value }))} /></label>
                <button type="button" className="btn btn-primary" disabled={!commands.canCreate || commands.createState.phase === "running" || commands.createState.phase === "unknown_outcome" || !createDraft.displayName.trim() || !createDraft.overlayRevision.trim()} onClick={() => { void commands.create(createDraft); }}>
                  {commands.createState.phase === "running" ? "创建中…" : "创建 Draft"}
                </button>
                {commands.createState.error && <p role="alert">{commands.createState.error.message}</p>}
                {commands.createState.canRetrySameCommand && <button type="button" className="btn" onClick={() => { void commands.retryCreate(); }}>使用原幂等键恢复创建</button>}
              </section>
            </>
          )}
        </div>
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
