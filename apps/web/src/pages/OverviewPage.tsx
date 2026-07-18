import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { API_BASE } from "../api/client";
import { OverviewDomainGrid } from "../components/OverviewDomainGrid";
import { PageChrome } from "../components/PageChrome";
import { fetchOverviewMetrics, type OverviewMetrics } from "../overviewMetrics";
import { BpBanner, BpDomainPanel, BpIndexTile, BpMetricGrid, BpToolbar } from "./s2/blueprintUi";

/** 97 · 对齐 index.html · 控制面 + 四域 live 指标（无业务主链） */
export function OverviewPage() {
  const [metrics, setMetrics] = useState<OverviewMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(() => {
    setLoading(true);
    void fetchOverviewMetrics()
      .then(setMetrics)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    reload();
  }, [reload]);

  const m = metrics;
  const health = m?.health ?? "…";
  const healthOk = health === "ok" || health === "healthy";
  const agnesReady = m?.sidecar === "agnes-openai-compatible";

  return (
    <PageChrome
      title="AI操作系统"
      lede="日常从工作台进入；建设路径：Connector → Pipeline → Dataset → OKF / Ontology → AIP → 工作台。"
    >
      <BpToolbar>
        <button type="button" className="btn" onClick={reload} disabled={loading}>
          {loading ? "刷新中…" : "刷新指标"}
        </button>
        <Link to="/data" className="muted" style={{ fontSize: "0.75rem" }}>
          数据连接 →
        </Link>
      </BpToolbar>

      <p className="status-pill" style={{ marginBottom: "1rem" }}>
        <span className="status-dot" />
        {API_BASE} · health: {health} · LLM: {m?.sidecar ?? "…"}
        {agnesReady && m?.defaultModel ? ` · ${m.defaultModel}` : ""}
      </p>

      {m && m.workOrders === 0 && (
        <BpBanner tone="warn">
          尚无 WorkOrder 实例 · 请到 <Link to="/data">数据连接</Link> 点击「初始化业务数据」后再演示 Inbox/Buddy。
        </BpBanner>
      )}

      <BpDomainPanel
        tone="aip"
        title="操作系统控制面"
        hint={`WorkOrder ${m?.workOrders ?? "…"} · Draft 待审 ${m?.pendingDrafts ?? "…"} · 模型 ${m?.models ?? "…"}`}
      >
        <BpMetricGrid
          items={[
            { label: "API 健康", value: health, tone: healthOk ? "ok" : "warn" },
            { label: "LLM", value: m?.defaultModel || m?.sidecar || "…", tone: agnesReady ? "ok" : "muted" },
            { label: "Evals 门控", value: m?.evalsGreen ? "绿" : "—", tone: m?.evalsGreen ? "ok" : "warn" },
            { label: "Workbench 模块", value: m?.modules ?? "…", tone: "muted" },
          ]}
        />
        <div className="bp-index-grid bp-index-grid-4" style={{ marginTop: "1rem" }}>
          <BpIndexTile
            to="/aip/model-router"
            eyebrow="模型"
            title={`${m?.models ?? "…"} 可路由`}
            desc="任务路由 · 试聊 · 预热"
            accent="amber"
          />
          <BpIndexTile
            to="/aip/tools"
            eyebrow="插件"
            title={`${m?.plugins ?? "…"} 已登记`}
            desc="parsers · capabilities"
            accent="amber"
          />
          <BpIndexTile
            to="/workshop"
            eyebrow="模块"
            title={`${m?.modules ?? "…"} Module`}
            desc="应用列表 · 运营 Inbox"
            accent="sky"
          />
          <BpIndexTile
            to="/aip/drafts"
            eyebrow="HITL"
            title={m?.pendingDrafts ? `${m.pendingDrafts} 待审` : "Draft 审批"}
            desc="提案 → 写生产 Ontology"
            accent="emerald"
          />
        </div>
      </BpDomainPanel>

      <OverviewDomainGrid metrics={m} />
    </PageChrome>
  );
}
