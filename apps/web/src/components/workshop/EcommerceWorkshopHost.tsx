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

function HostState({
  state,
  onRetry,
}: {
  state: "loading" | "empty" | "forbidden" | "failed" | "not-installed";
  onRetry?: () => void;
}) {
  return (
    <div className="ecommerce-workshop-host-state">
      <h1>电商工作台</h1>
      <AsyncStateBoundary
        state={state}
        action={
          onRetry ? (
            <button type="button" onClick={onRetry}>重新读取目录</button>
          ) : undefined
        }
      />
    </div>
  );
}

export function EcommerceWorkshopHost() {
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const contextId = searchParams.get("context");
  const currentTargetId = searchParams.get("target");
  const catalog = useEcommerceWorkshopCatalog();
  const match = findInstalledWorkshopRoute(catalog.modules, location.pathname);

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
      >
        <EcommerceWorkshopSharedContext contextId={contextId} currentTargetId={currentTargetId} />
        {match.module.moduleId === "ecommerce.task-cockpit" ? <TaskCockpitPage /> : match.module.moduleId === "ecommerce.operations" ? <OperationsPage /> : match.module.moduleId === "ecommerce.content-campaign" ? <ContentCampaignPage /> : match.module.moduleId === "ecommerce.creator-growth" ? <CreatorGrowthPage /> : match.module.moduleId === "ecommerce.media-studio" ? <MediaStudioPage /> : match.module.moduleId === "ecommerce.analyst" ? <AnalystPage /> : match.module.moduleId === "ecommerce.price-governance" ? <PriceGovernancePage /> : match.module.moduleId === "ecommerce.customer" ? <CustomerPage /> : undefined}
      </EcommerceWorkshopShell>
    );
  }
  if (catalog.phase === "loading") return <HostState state="loading" />;
  if (catalog.phase === "forbidden") return <HostState state="forbidden" />;
  if (catalog.phase === "failed") {
    return <HostState state="failed" onRetry={catalog.reload} />;
  }
  if (catalog.phase === "empty") return <HostState state="not-installed" />;
  return <HostState state="not-installed" />;
}
