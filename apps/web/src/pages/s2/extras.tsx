import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { S2Chrome, useJsonGet } from "./shared";
import { AipOperationalProjectionStrip } from "../../components/aip/AipOperationalProjectionStrip";

export { ModuleInterfacePage } from "./ModuleInterfacePage";

export function isBreakerTripConfirmed(value: { open?: boolean; mode?: string }): boolean {
  return value.open === true && value.mode === "L3";
}

type MaturityEvidenceCard = {
  dimension: string;
  state: string;
  evidence: string;
  gap: string;
  href: string;
  action: string;
};

/** 81 · 基于当前租户权威读取的四维成熟度证据，不允许本地预览冒充状态。 */
export function MaturityPage() {
  const evals = useJsonGet<{ green?: boolean; l4Allowed?: boolean }>("/v1/aip/evals/status");
  const drafts = useJsonGet<{ count?: number; items?: unknown[] }>("/v1/aip/drafts");
  const agents = useJsonGet<{
    items?: Array<{
      instanceId?: string;
      id?: string;
      name?: string;
      overlay?: { displayName?: string };
    }>;
  }>("/v1/aip/agents");
  const tools = useJsonGet<{ items?: Array<{ id?: string; kind?: string; blocked?: boolean }> }>("/v1/aip/tools");
  const automations = useJsonGet<{ items?: Array<{ status?: string; updated_at?: string }> }>("/v1/aip/logic/automation-policies");
  const suites = useJsonGet<{ items?: unknown[] }>("/v1/evals/suites");
  const cutoff = useMemo(() => new Date().toISOString(), [evals.data, drafts.data, agents.data, tools.data, automations.data, suites.data]);

  const green = evals.data?.green === true;
  const workspaceAgentLabel = useMemo(() => {
    const items = agents.data?.items || [];
    if (!items.length) return null;
    const preferred =
      items.find((item) => String(item.instanceId || item.id || "").includes("content_officer")) || items[0];
    return preferred.overlay?.displayName || preferred.name || preferred.instanceId || preferred.id || null;
  }, [agents.data]);

  const draftCount = drafts.data?.count ?? drafts.data?.items?.length ?? 0;
  const agentCount = agents.data?.items?.length ?? 0;
  const toolItems = tools.data?.items ?? [];
  const runnableTools = toolItems.filter((item) => !item.blocked).length;
  const activeAutomations = (automations.data?.items ?? []).filter((item) => item.status === "active").length;
  const suiteCount = suites.data?.items?.length ?? 0;
  const cards: MaturityEvidenceCard[] = [
    {
      dimension: "业务能力",
      state: agentCount > 0 && runnableTools > 0 ? "已有可消费能力" : "需要补齐绑定",
      evidence: `${agentCount} 位数字同事 · ${runnableTools}/${toolItems.length} 个工具可受控使用`,
      gap: agentCount === 0 ? "尚无数字同事实例" : runnableTools === 0 ? "尚无可运行工具" : "继续核对角色、工具与业务逻辑的适配范围",
      href: "/aip/tools",
      action: "核对工具与同事绑定",
    },
    {
      dimension: "可运行性",
      state: activeAutomations > 0 ? "存在活动自动化" : "可人工试跑",
      evidence: `${activeAutomations} 条活动自动化 · 评测门 ${evals.data?.l4Allowed === true ? "允许申请" : "未允许自动化"}`,
      gap: activeAutomations > 0 ? "继续核验最近运行与凭证" : "先从业务逻辑安全试跑，再按需建立自动化",
      href: "/aip/logic?tab=automation",
      action: "查看业务逻辑运行",
    },
    {
      dimension: "质量",
      state: evals.data?.green === true ? "当前评测通过" : "需要运行评测",
      evidence: `${suiteCount} 个评测套件 · 当前门控 ${evals.data?.green === true ? "GREEN" : "未通过"}`,
      gap: suiteCount === 0 ? "缺少真实评测套件" : evals.data?.green === true ? "持续核对精确修订与报告截止时间" : "运行绑定当前 Logic 修订的真实套件",
      href: "/aip/evals",
      action: "查看评测证据",
    },
    {
      dimension: "治理",
      state: draftCount > 0 ? "存在待审业务变更" : "审批队列为空",
      evidence: `${draftCount} 项草稿 · 写操作保持提案、草稿、审批、凭证链`,
      gap: "任何写操作都必须保留职责分离、幂等键和交付凭证",
      href: "/aip/drafts",
      action: "查看草稿审批",
    },
  ];

  function reloadAll() {
    evals.reload();
    drafts.reload();
    agents.reload();
    tools.reload();
    automations.reload();
    suites.reload();
  }

  return (
    <S2Chrome
      title="智能体成熟度楼梯"
      lede="从业务能力、可运行性、质量和治理四个维度读取当前租户证据；每项结论都可追溯到配置、评测或审批入口。"
    >
      <AipOperationalProjectionStrip />
      <div style={{ marginBottom: 12, fontSize: 13 }}>
        <Link to="/aip/memory-governance?view=candidates" data-testid="maturity-memory-bridge">
          知识候选治理 →
        </Link>
        <span style={{ color: "var(--aos-text-secondary)", margin: "0 8px" }}>·</span>
        <Link to="/aip/memory-governance?view=readiness">知识就绪门 →</Link>
      </div>
      <div
        data-testid="maturity-ops-stats"
        style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(110px,1fr))", gap: 10, marginBottom: 12 }}
      >
        {[
          { label: "业务能力", value: `${agentCount} 位同事` },
          { label: "评测", value: green ? "通过" : "未运行" },
          { label: "审批草稿", value: String(drafts.data?.count ?? drafts.data?.items?.length ?? 0) },
          { label: "同事数", value: String(agents.data?.items?.length ?? 0) },
          { label: "自动化", value: `${activeAutomations} 条活动` },
        ].map((s) => (
          <div key={s.label} className="card" style={{ padding: "10px 12px" }}>
            <div style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{s.label}</div>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{s.value}</div>
          </div>
        ))}
      </div>
      <div
        style={{
          borderRadius: 2,
          border: "1px solid var(--aos-amber-border)",
          background: "var(--aos-amber-bg)",
          padding: "16px",
          marginBottom: "1rem",
          display: "flex",
          flexWrap: "wrap",
          gap: "1rem",
          alignItems: "center",
          justifyContent: "space-between",
          fontSize: 14,
        }}
      >
        <div>
          <div style={{ fontSize: 12, color: "var(--aos-muted)", marginBottom: 2 }}>当前工作区</div>
          <div style={{ color: "var(--aos-text)", fontWeight: 500 }}>
            {workspaceAgentLabel || (agents.loading ? "读取数字同事…" : "尚未安装栖月汇数字同事")}
          </div>
          {!workspaceAgentLabel && !agents.loading ? (
            <Link to="/aip/studio" style={{ fontSize: 12 }}>去 Studio 安装 →</Link>
          ) : null}
        </div>
        <div>
          <div style={{ fontSize: 12, color: "var(--aos-muted)", marginBottom: 2 }}>证据截止</div>
          <div style={{ color: "var(--aos-amber-700)", fontWeight: 500 }}>{cutoff}</div>
        </div>
        <div style={{ fontSize: 12, color: "var(--aos-muted)", lineHeight: 1.6 }}>
          <div>
            评测 <span style={{ color: green ? "var(--aos-green-700)" : "var(--aos-amber-700)" }}>{green ? "● 通过" : "○ 未运行"}</span>
            {" · "}
            草稿 <span style={{ color: "var(--aos-green-700)" }}>审批台 {draftCount} 项</span>
          </div>
          <div>
            执行范围 <span style={{ color: "var(--aos-text)" }}>● 当前组织与工作区</span>
          </div>
        </div>
      </div>

      <div data-testid="maturity-evidence-grid" style={{ display: "grid", gridTemplateColumns: "repeat(2,minmax(0,1fr))", gap: 12 }}>
        {cards.map((card) => (
          <section key={card.dimension} className="card" style={{ padding: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
              <h2 style={{ margin: 0, fontSize: 16 }}>{card.dimension}</h2>
              <strong>{card.state}</strong>
            </div>
            <p className="aos-text"><strong>当前证据：</strong>{card.evidence}</p>
            <p className="muted" style={{ fontSize: 12 }}><strong>证据截止：</strong>{cutoff}</p>
            <p className="aos-text"><strong>待提升项：</strong>{card.gap}</p>
            <Link to={card.href} className="btn-nav">{card.action} →</Link>
          </section>
        ))}
      </div>
      <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
        <button type="button" className="btn" onClick={reloadAll}>重新读取全部证据</button>
        <Link to="/aip/studio" className="btn-nav">智能体配置 →</Link>
        <Link to="/aip/logic" className="btn-nav">业务逻辑 →</Link>
        <Link to="/aip/evals" className="btn-nav">评测门控 →</Link>
      </div>
      {(evals.err || drafts.err || agents.err || tools.err || automations.err || suites.err) && (
        <p className="error">{evals.err || drafts.err || agents.err || tools.err || automations.err || suites.err}</p>
      )}
    </S2Chrome>
  );
}

type GraphHealth = {
  score?: number;
  metrics?: {
    instances?: number;
    orphanInstances?: number;
    objectTypes?: number;
    edges?: number;
  };
};

type MetricsSnap = {
  totals?: { count?: number; errors?: number; p95Ms?: number | null };
};

/** 82 · 对齐 workshop-cop.html · 4 KPI + Map/Graph + 钻取侧栏 + 底部详情 */
export function CopPage() {
  const health = useJsonGet<GraphHealth>("/v1/ontology/graph-health");
  const metrics = useJsonGet<MetricsSnap>("/v1/metrics");
  const evals = useJsonGet<{ green?: boolean; l4Allowed?: boolean }>("/v1/aip/evals/status");
  const types = useJsonGet<{ items: { id: string; name: string }[] }>("/v1/ontology/object-types");
  const [focusType, setFocusType] = useState<string | null>(null);

  const hm = health.data?.metrics;
  const totals = metrics.data?.totals;
  const green = evals.data?.green === true;
  const riskCount =
    (totals?.errors ?? 0) > 0 || !green ? Math.max(1, totals?.errors ?? 1) : 0;

  const focusMeta = types.data?.items?.find((t) => t.id === focusType);

  const kpiItems = [
    {
      label: "在途订单（实例）",
      value: hm?.instances ?? "—",
      tone: "ok" as const,
      hint: "图谱健康 · 正常",
      hintTone: "up" as const,
    },
    {
      label: "孤立实例",
      value: hm?.orphanInstances ?? "—",
      tone: (hm?.orphanInstances ?? 0) > 10 ? "warn" as const : "muted" as const,
      hint: (hm?.orphanInstances ?? 0) > 10 ? "须关注 · 超过阈值" : "在合理范围内",
      hintTone: (hm?.orphanInstances ?? 0) > 10 ? "down" as const : "up" as const,
    },
    {
      label: "API p95 (ms)",
      value: totals?.p95Ms != null ? Number(totals.p95Ms).toFixed(1) : "—",
      tone: "muted" as const,
      hint: "响应稳定",
      hintTone: "up" as const,
    },
    {
      label: "风险信号",
      value: riskCount,
      tone: riskCount > 0 ? "bad" as const : "ok" as const,
      hint: riskCount > 0 ? "须干预 · 待处理" : "全部正常",
      hintTone: riskCount > 0 ? "down" as const : "up" as const,
    },
  ];

  const currentTypes = types.data?.items || [];

  return (
    <S2Chrome title="态势大屏" lede="汇总当前图谱健康、服务指标与评测状态">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
        <button
          type="button"
          onClick={() => {
            health.reload();
            metrics.reload();
            evals.reload();
            types.reload();
          }}
          style={{
            fontSize: "12px",
            padding: "5px 12px",
            borderRadius: "4px",
            border: "1px solid var(--aos-border)",
            background: "var(--aos-aside)",
            color: "var(--aos-text)",
            cursor: "pointer",
          }}
        >
          刷新态势
        </button>
        <span className="muted" style={{ fontSize: "12px" }}>
          全屏态势布局 · 非独立大屏产品
        </span>
        <Link to="/workshop" className="btn-nav" style={{ fontSize: "12px" }}>
          退出全屏 →
        </Link>
      </div>

      {(health.err || metrics.err || evals.err) && (
        <p className="error">{health.err || metrics.err || evals.err}</p>
      )}

      {/* KPI Row */}
      <div className="p-cop-kpi-grid">
        {kpiItems.map((k, i) => (
          <div
            key={i}
            className={`p-cop-kpi-card${k.tone === "warn" ? " is-warn" : k.tone === "bad" ? " is-bad" : ""}`}
          >
            <div className="p-cop-kpi-label">{k.label}</div>
            <div className="p-cop-kpi-value">{k.value}</div>
            <div className={`p-cop-kpi-hint${k.hintTone === "up" ? " is-up" : k.hintTone === "down" ? " is-down" : ""}`}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: "12px", height: "12px" }}>
                <path strokeLinecap="round" d={k.hintTone === "down" ? "M19 6L5 18" : "M5 18l7-7 7 7"} />
              </svg>
              {k.hint}
            </div>
          </div>
        ))}
      </div>

      {/* Main visual area */}
      <div className="p-cop-main">
        <div className="p-cop-map">
          <div className="p-cop-map-header">
            <h2 className="p-cop-map-title">当前业务对象态势</h2>
            <span className="p-cop-map-subtitle">
              {types.data?.items?.length || 0} 对象类型 · {hm?.edges ?? 0} 关系边 · 健康度 {health.data?.score ?? "—"}
            </span>
          </div>
          <div className="p-cop-map-svg">
            <svg viewBox="0 0 680 260" preserveAspectRatio="xMidYMid meet">
              {/* Connection lines */}
              <line x1="80" y1="130" x2="200" y2="130" stroke="rgba(43,108,176,0.3)" strokeWidth="2" strokeDasharray="6,3" />
              <line x1="80" y1="130" x2="200" y2="70" stroke="rgba(43,108,176,0.2)" strokeWidth="1.5" strokeDasharray="4,3" />
              <line x1="80" y1="130" x2="200" y2="190" stroke="rgba(214,158,46,0.25)" strokeWidth="1.5" strokeDasharray="4,3" />
              <line x1="340" y1="130" x2="460" y2="130" stroke="rgba(56,161,105,0.3)" strokeWidth="2" strokeDasharray="6,3" />
              <line x1="340" y1="130" x2="460" y2="70" stroke="rgba(56,161,105,0.2)" strokeWidth="1.5" strokeDasharray="4,3" />
              <line x1="340" y1="130" x2="460" y2="190" stroke="rgba(229,62,62,0.3)" strokeWidth="1.5" strokeDasharray="4,3" />

              {/* Hub node (CDC) */}
              <circle cx="200" cy="130" r="35" fill="rgba(43,108,176,0.08)" stroke="rgba(43,108,176,0.4)" strokeWidth="2" />
              <text x="200" y="126" textAnchor="middle" fill="currentColor" fontSize="12" fontWeight="500">图谱实例</text>
              <text x="200" y="142" textAnchor="middle" fill="var(--aos-text-tertiary)" fontSize="10">{hm?.instances ?? "—"} 条</text>

              {/* Pipeline node */}
              <circle cx="340" cy="130" r="35" fill="rgba(56,161,105,0.08)" stroke="rgba(56,161,105,0.4)" strokeWidth="2" />
              <text x="340" y="126" textAnchor="middle" fill="currentColor" fontSize="12" fontWeight="500">图谱关系</text>
              <text x="340" y="142" textAnchor="middle" fill="var(--aos-text-tertiary)" fontSize="10">{hm?.edges ?? "—"} 条</text>

              {/* Current authority nodes; no sample factories or warehouses. */}
              <rect x="20" y="55" width="60" height="36" rx="8" fill="rgba(43,108,176,0.08)" stroke="rgba(43,108,176,0.3)" strokeWidth="1.5" />
              <text x="50" y="78" textAnchor="middle" fill="currentColor" fontSize="10">当前对象</text>
              <rect x="20" y="120" width="60" height="36" rx="8" fill="rgba(56,161,105,0.08)" stroke="rgba(56,161,105,0.3)" strokeWidth="1.5" />
              <text x="50" y="143" textAnchor="middle" fill="currentColor" fontSize="10">图谱关系</text>
              <rect x="20" y="185" width="60" height="36" rx="8" fill="rgba(214,158,46,0.08)" stroke="rgba(214,158,46,0.3)" strokeWidth="1.5" />
              <text x="50" y="208" textAnchor="middle" fill="currentColor" fontSize="10">健康指标</text>

              {/* Destinations */}
              <rect x="410" y="55" width="56" height="36" rx="8" fill="rgba(56,161,105,0.08)" stroke="rgba(56,161,105,0.3)" strokeWidth="1.5" />
              <text x="438" y="78" textAnchor="middle" fill="currentColor" fontSize="10">对象类型</text>
              <rect x="410" y="120" width="56" height="36" rx="8" fill="rgba(43,108,176,0.08)" stroke="rgba(43,108,176,0.3)" strokeWidth="1.5" />
              <text x="438" y="143" textAnchor="middle" fill="currentColor" fontSize="10">关系类型</text>
              <rect x="410" y="185" width="56" height="36" rx="8" fill="rgba(229,62,62,0.08)" stroke="rgba(229,62,62,0.3)" strokeWidth="1.5" />
              <text x="438" y="208" textAnchor="middle" fill="currentColor" fontSize="10">风险信号</text>

              {/* Object type nodes */}
              {(types.data?.items || []).slice(0, 5).map((t, i) => {
                const cx = 560 + (i % 2) * 60;
                const cy = 60 + Math.floor(i / 2) * 80;
                const isActive = focusType === t.id;
                return (
                  <g
                    key={t.id}
                    style={{ cursor: "pointer" }}
                    onClick={() => setFocusType(t.id)}
                  >
                    <circle
                      cx={cx}
                      cy={cy}
                      r="22"
                      fill={isActive ? "rgba(56,189,248,0.15)" : "rgba(100,116,139,0.08)"}
                      stroke={isActive ? "rgba(56,189,248,0.6)" : "rgba(100,116,139,0.3)"}
                      strokeWidth={isActive ? "2" : "1.5"}
                    />
                    <text x={cx} y={cy + 4} textAnchor="middle" fill="currentColor" fontSize="9">
                      {t.name.length > 6 ? t.name.slice(0, 6) : t.name}
                    </text>
                  </g>
                );
              })}

              {/* Alert icon */}
              <circle cx="600" cy="200" r="12" fill="rgba(229,62,62,0.12)" stroke="rgba(229,62,62,0.35)" strokeWidth="1" />
              <text x="600" y="204" textAnchor="middle" fill="#fb7185" fontSize="14">!</text>
            </svg>
          </div>
        </div>

        {/* Side panel: drill-down */}
        <div className="p-cop-sidebar">
          <h2 className="p-cop-sidebar-title">钻取详情 · {focusMeta ? focusMeta.name : "选择节点"}</h2>

          <div className="p-cop-factory-list">
            {currentTypes.slice(0, 6).map((item) => (
              <button
                key={item.id}
                type="button"
                className={`p-cop-factory-card${focusType === item.id ? " is-active" : ""}`}
                onClick={() => setFocusType(item.id)}
              >
                <div className="p-cop-factory-head">
                  <span className="p-cop-factory-name">{item.name}</span>
                  <span className="p-cop-factory-status">当前权威</span>
                </div>
                <div className="p-cop-factory-desc">点击查看当前图谱健康与评测状态</div>
              </button>
            ))}
            {!currentTypes.length && <p className="muted">当前租户没有可钻取的对象类型。</p>}
          </div>

          {focusMeta && (
            <div style={{ fontSize: "11px", color: "var(--aos-text-secondary)" }}>
              <p style={{ margin: "0 0 4px" }}>
                <strong style={{ color: "var(--aos-text)" }}>{focusMeta.name}</strong>{" "}
                <span className="muted">· {focusMeta.id}</span>
              </p>
              <p style={{ margin: 0 }}>
                图谱健康 {health.data?.score ?? "—"} · Eval {green ? "绿" : "未绿"}
              </p>
            </div>
          )}

          <div className="p-cop-sidebar-actions">
            <Link to="/workshop/inbox" className="p-cop-action-btn is-secondary">
              打开风险告警管理 →
            </Link>
          </div>
        </div>
      </div>

      {/* Bottom row: detail tables / alerts */}
      <div className="p-cop-bottom">
        {/* Risk factory detail */}
        <div className="p-cop-panel is-bad">
          <div className="p-cop-panel-head">
            <h2 className="p-cop-panel-title">当前风险信号</h2>
            <span className="p-cop-map-subtitle">{riskCount} 项须关注</span>
          </div>
          <div className="p-cop-risk-list">
            {riskCount > 0 ? <div className="p-cop-risk-item is-warn"><div><span className="p-cop-risk-name">系统观测发现风险信号</span><span className="p-cop-risk-tag">{riskCount} 项</span></div><span className="p-cop-risk-desc">进入风险告警管理读取可追溯的业务对象明细。</span></div> : <p className="muted">当前观测未返回风险信号。</p>}
          </div>
        </div>

        {/* Recent events */}
        <div className="p-cop-panel">
          <div className="p-cop-panel-head">
            <h2 className="p-cop-panel-title">实时业务事件</h2>
            <Link to="/workshop/events" className="p-cop-panel-link">全部事件 →</Link>
          </div>
          <div className="p-cop-event-list">
            <p className="muted">当前接口未提供可追溯的业务事件明细；页面不会使用演示事件填充。</p>
          </div>
        </div>
      </div>

      <div style={{ marginTop: "16px", display: "flex", gap: "16px", fontSize: "12px" }}>
        <Link to="/ontology/graph-health" className="btn-nav" style={{ textDecoration: "none" }}>
          图谱健康 →
        </Link>
        <Link to="/aip/evals" className="btn-nav" style={{ textDecoration: "none" }}>
          Evals 门控 →
        </Link>
        <Link to="/workshop/inbox" className="btn-nav" style={{ textDecoration: "none" }}>
          运营 Inbox →
        </Link>
      </div>
    </S2Chrome>
  );
}
