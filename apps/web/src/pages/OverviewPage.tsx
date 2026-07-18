import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { OverviewDomainGrid } from "../components/OverviewDomainGrid";
import { PageChrome } from "../components/PageChrome";
import { fetchOverviewMetrics, type OverviewMetrics } from "../overviewMetrics";
import { BpBanner, BpToolbar } from "./s2/blueprintUi";

/** 97 / 38 §9 · 对齐 index.html · 工作台为首域（控制面已并入） */
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

  return (
    <PageChrome
      title="数据操作系统 · 本体数字孪生 · AIP 人工智能平台 · 工作台"
      titleTone="brand"
      lede="日常从工作台进入；建设路径：连接器 → 管道 → 数据集 → OKF / 本体 → AIP → 工作台。"
    >
      <BpToolbar>
        <button type="button" className="btn" onClick={reload} disabled={loading}>
          {loading ? "刷新中…" : "刷新指标"}
        </button>
        <Link to="/data" className="muted" style={{ fontSize: "0.75rem" }}>
          数据连接 →
        </Link>
      </BpToolbar>

      {m && m.workOrders === 0 && (
        <BpBanner tone="warn">
          暂无工单 · 请到 <Link to="/data">数据连接</Link> 新建数据源并完成同步后再使用收件箱 / 智能助手。
        </BpBanner>
      )}

      <OverviewDomainGrid metrics={m} />
    </PageChrome>
  );
}
