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
  const catalog = useEcommerceWorkshopCatalog();
  const match = findInstalledWorkshopRoute(catalog.modules, location.pathname);

  if (match?.kind === "legacy") {
    return <Navigate to={match.module.route} replace />;
  }
  if (match) {
    const exposesReadOnly = match.module.moduleId === "ecommerce.task-cockpit" || match.module.moduleId === "ecommerce.operations" || match.module.moduleId === "ecommerce.content-campaign";
    return (
      <EcommerceWorkshopShell
        module={match.module}
        dataCutoff={catalog.response?.dataCutoff ?? null}
        catalogStale={catalog.phase === "stale"}
        exposeReadOnlyWhenUnverified={exposesReadOnly}
      >
        {match.module.moduleId === "ecommerce.task-cockpit" ? <TaskCockpitPage /> : match.module.moduleId === "ecommerce.operations" ? <OperationsPage /> : match.module.moduleId === "ecommerce.content-campaign" ? <ContentCampaignPage /> : undefined}
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
