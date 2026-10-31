import { Navigate, useLocation } from "react-router-dom";

import { AsyncStateBoundary } from "./AsyncStateBoundary";
import {
  findInstalledWorkshopRoute,
  useEcommerceWorkshopCatalog,
} from "./EcommerceWorkshopCatalogContext";
import { EcommerceWorkshopShell } from "./EcommerceWorkshopShell";
import { TaskCockpitPage } from "./TaskCockpitPage";
import { OperationsPage } from "./OperationsPage";
import { ContentCampaignPage } from "./ContentCampaignPage";
import { CreatorGrowthPage } from "./CreatorGrowthPage";
import { MediaStudioPage } from "./MediaStudioPage";
import { AnalystPage } from "./AnalystPage";
import { PriceGovernancePage } from "./PriceGovernancePage";
import { CustomerPage } from "./CustomerPage";
import { EcommerceWorkshopSharedContext } from "./EcommerceWorkshopSharedContext";
import { getAuthRevision, getTenant } from "../../api/tenant";
import { WorkshopInstallationDiagnosis } from "./WorkshopInstallationDiagnosis";
import { WorkshopSessionRecovery } from "./WorkshopSessionRecovery";

function HostState({
  state,
  onRetry,
  authenticationRejected = false,
}: {
  state: "loading" | "empty" | "forbidden" | "failed";
  onRetry?: () => void;
  authenticationRejected?: boolean;
}) {
  return (
    <div className="ecommerce-workshop-host-state">
      <h1>电商工作台</h1>
      <AsyncStateBoundary
        state={state}
        title={authenticationRejected ? "当前身份认证未通过" : state === "empty" ? "当前工作台入口不可用" : undefined}
        description={authenticationRejected ? "请重新登录后再次读取当前工作区；此拒绝不表示安装已失效。" : state === "empty" ? "当前目录没有此工作台的可见入口。请核对安装配置与访问权限后重新读取。" : undefined}
        action={
          onRetry ? (
            <button type="button" onClick={onRetry}>重新读取目录</button>
          ) : undefined
        }
      />
      {state === "empty" && <WorkshopInstallationDiagnosis key={JSON.stringify([getTenant(), getAuthRevision()])} />}
    </div>
  );
}

function EcommerceWorkshopContent({ onCatalogReload }: { onCatalogReload?: () => void } = {}) {
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const contextId = searchParams.get("context");
  const currentTargetId = searchParams.get("target");
  const catalog = useEcommerceWorkshopCatalog();
  const match = findInstalledWorkshopRoute(
    catalog.developmentPreview ? catalog.previewModules : catalog.modules,
    location.pathname,
  );

  if (match?.kind === "legacy") {
    return <Navigate to={match.module.route} replace />;
  }
  if (match) {
    const exposesReadOnly = match.module.moduleId === "ecommerce.task-cockpit" || match.module.moduleId === "ecommerce.operations" || match.module.moduleId === "ecommerce.content-campaign" || match.module.moduleId === "ecommerce.creator-growth" || match.module.moduleId === "ecommerce.media-studio" || match.module.moduleId === "ecommerce.analyst" || match.module.moduleId === "ecommerce.price-governance" || match.module.moduleId === "ecommerce.customer";
    return (
      <EcommerceWorkshopShell
        module={match.module}
        dataCutoff={catalog.response?.dataCutoff ?? null}
        catalogStale={catalog.phase === "stale"}
        exposeReadOnlyWhenUnverified={exposesReadOnly}
        developmentPreview={catalog.developmentPreview}
      >
        <EcommerceWorkshopSharedContext contextId={contextId} currentTargetId={currentTargetId} />
        {match.module.moduleId === "ecommerce.task-cockpit" ? <TaskCockpitPage /> : match.module.moduleId === "ecommerce.operations" ? <OperationsPage /> : match.module.moduleId === "ecommerce.content-campaign" ? <ContentCampaignPage /> : match.module.moduleId === "ecommerce.creator-growth" ? <CreatorGrowthPage /> : match.module.moduleId === "ecommerce.media-studio" ? <MediaStudioPage /> : match.module.moduleId === "ecommerce.analyst" ? <AnalystPage /> : match.module.moduleId === "ecommerce.price-governance" ? <PriceGovernancePage /> : match.module.moduleId === "ecommerce.customer" ? <CustomerPage /> : undefined}
      </EcommerceWorkshopShell>
    );
  }
  if (catalog.phase === "loading") return <HostState state="loading" />;
  if (catalog.phase === "forbidden") return <HostState state="forbidden" authenticationRejected={catalog.error?.status === 401} />;
  if (catalog.phase === "failed") {
    return <HostState state="failed" onRetry={onCatalogReload ?? catalog.reload} />;
  }
  return <HostState state="empty" onRetry={onCatalogReload ?? catalog.reload} />;
}

export function EcommerceWorkshopHost(props: { onCatalogReload?: () => void } = {}) {
  return <><WorkshopSessionRecovery /><EcommerceWorkshopContent {...props} /></>;
}
