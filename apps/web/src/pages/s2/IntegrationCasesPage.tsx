import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { getTenant } from "../../api/tenant";
import type { IntegrationCaseScope } from "../../api/integrationCases/types";
import { integrationCaseClient } from "../../api/integrationCases/client";
import {
  createIntegrationCaseCommand,
  integrationCaseIdempotencyKeyFor,
} from "../../api/integrationCases/idempotency";
import { BpBanner, BpToolbar } from "./blueprintUi";
import { S2Chrome } from "./shared";
import { IntegrationCaseCatalog } from "./integrationCases/IntegrationCaseCatalog";
import { IntegrationCaseDetail } from "./integrationCases/IntegrationCaseDetail";
import { IntegrationCaseStats } from "./integrationCases/IntegrationCaseStats";
import { IntegrationCaseTimeline } from "./integrationCases/IntegrationCaseTimeline";
import { useIntegrationCasesReadModel } from "./integrationCases/useIntegrationCasesReadModel";

function currentTenantKey(): string {
  const tenant = getTenant();
  return `${tenant.orgId}:${tenant.projectId}`;
}

function useTenantKey(): string {
  const [tenantKey, setTenantKey] = useState(currentTenantKey);

  useEffect(() => {
    const handleTenantUpdate = () => setTenantKey(currentTenantKey());
    window.addEventListener("aos-tenant-updated", handleTenantUpdate);
    return () => window.removeEventListener("aos-tenant-updated", handleTenantUpdate);
  }, []);

  return tenantKey;
}

function ListStatus({
  status,
  message,
  onRetry,
}: {
  status: string;
  message: string | null;
  onRetry: () => void;
}) {
  if (status === "loading") return <p role="status">正在读取接入案例…</p>;
  if (status === "refreshing") return <p role="status">正在刷新服务端事实…</p>;
  if (status === "stale") {
    return (
      <BpBanner tone="warn">
        刷新失败，当前显示最后一次服务端事实。{message ? ` ${message}` : ""}
      </BpBanner>
    );
  }
  if (status === "forbidden") {
    return (
      <BpBanner tone="warn">
        当前账号无权读取接入案例。 <button type="button" className="btn" onClick={onRetry}>重试</button>
      </BpBanner>
    );
  }
  if (status === "not_visible_or_missing") {
    return (
      <BpBanner tone="warn">
        接入案例不可见或不存在；为避免泄漏，不区分两种情况。 <button type="button" className="btn" onClick={onRetry}>重试</button>
      </BpBanner>
    );
  }
  if (status === "error") {
    return (
      <BpBanner tone="warn">
        接入案例读取失败：{message ?? "未知读取错误"} <button type="button" className="btn" onClick={onRetry}>重试</button>
      </BpBanner>
    );
  }
  return null;
}

export function IntegrationCasesPage() {
  const tenantKey = useTenantKey();
  const [scope, setScope] = useState<IntegrationCaseScope>("current");
  const [filter, setFilter] = useState("");
  const model = useIntegrationCasesReadModel({ tenantKey, scope, filter });
  const list = model.list.data;
  const [snapshotPending, setSnapshotPending] = useState(false);
  const [snapshotError, setSnapshotError] = useState<string | null>(null);

  const createSnapshot = useCallback(async () => {
    const detail = model.detail.data;
    if (!detail || detail.scope !== "current") return;
    setSnapshotPending(true);
    setSnapshotError(null);
    try {
      await integrationCaseClient.createEvidenceSnapshot(detail.caseId, {
        idempotencyKey: integrationCaseIdempotencyKeyFor(createIntegrationCaseCommand()),
        etagVersion: detail.etagVersion,
      });
      model.refreshDetail();
      model.refreshTimeline();
    } catch (e) {
      setSnapshotError(String((e as Error).message || e));
    } finally {
      setSnapshotPending(false);
    }
  }, [model]);
  const listMatchesScope = list?.scope === scope;
  const listStatusMessage = model.list.error?.message ?? null;

  const summary = useMemo(() => {
    if (!listMatchesScope || !list) return null;
    return `服务端返回 ${list.total} 个${scope === "current" ? "当前" : "脱敏参考"}案例`;
  }, [list, listMatchesScope, scope]);

  function changeScope(nextScope: IntegrationCaseScope) {
    if (nextScope === scope) return;
    setFilter("");
    setScope(nextScope);
  }

  return (
    <S2Chrome
      title="接入案例"
      lede="案例阶段、统计、待处理事项与时间线均来自服务端权威记录"
    >
      <BpToolbar>
        <button
          type="button"
          className={scope === "current" ? "btn btn-primary" : "btn"}
          aria-pressed={scope === "current"}
          onClick={() => changeScope("current")}
        >
          当前工作区
        </button>
        <button
          type="button"
          className={scope === "reference" ? "btn btn-primary" : "btn"}
          aria-pressed={scope === "reference"}
          onClick={() => changeScope("reference")}
        >
          脱敏参考
        </button>
        <label>
          <span className="sr-only">筛选接入案例</span>
          <input
            type="search"
            value={filter}
            placeholder="按名称或标识筛选"
            aria-label="筛选接入案例"
            onChange={(event) => setFilter(event.target.value)}
          />
        </label>
        <button type="button" className="btn" onClick={model.refreshAll}>刷新</button>
        <Link to="/apollo/assets" className="btn-nav">安装管理 →</Link>
      </BpToolbar>

      <ListStatus
        status={model.list.status}
        message={listStatusMessage}
        onRetry={model.refreshList}
      />

      {listMatchesScope && list ? (
        <>
          <IntegrationCaseStats scope={scope} stats={list.stats} />
          <section style={{ marginTop: "1.5rem" }} aria-label="接入案例目录区域">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12 }}>
              <h2 className="bp-ws-section-title">{scope === "current" ? "当前接入案例" : "脱敏参考案例"}</h2>
              {summary && <span className="muted">{summary}</span>}
            </div>
            <IntegrationCaseCatalog
              scope={scope}
              items={model.visibleItems}
              selectedCaseId={model.selectedCaseId}
              onSelectCase={(caseId) => model.selectCase(model.selectedCaseId === caseId ? null : caseId)}
            />
          </section>
        </>
      ) : null}

      {model.selectedCaseId ? (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
            gap: "1rem",
            marginTop: "1.5rem",
          }}
        >
          <IntegrationCaseDetail
            state={model.detail}
            onRetry={model.refreshDetail}
            onCreateSnapshot={createSnapshot}
            snapshotPending={snapshotPending}
            snapshotError={snapshotError}
          />
          <IntegrationCaseTimeline state={model.timeline} onRetry={model.refreshTimeline} />
        </div>
      ) : (
        <BpBanner tone="info">选择一个接入案例后查看阶段门、待处理事项和阶段事件。</BpBanner>
      )}

      <BpBanner tone="info">
        本页不推断生产状态，也不接收客户端证据；过期、撤销和负向证据由服务端重新计算并保留历史。
      </BpBanner>
    </S2Chrome>
  );
}
