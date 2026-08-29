import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiPost, S2Chrome, useJsonGet } from "./shared";
import { BpMaturityStairs } from "./blueprintUi";
import { AipOperationalProjectionStrip } from "../../components/aip/AipOperationalProjectionStrip";

export { ModuleInterfacePage } from "./ModuleInterfacePage";

export function isBreakerTripConfirmed(value: { open?: boolean; mode?: string }): boolean {
  return value.open === true && value.mode === "L3";
}

/** 81 · 对齐 aip-maturity.html · L1～L4 楼梯 */
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
  const [level, setLevel] = useState(2);
  const [toast, setToast] = useState("");

  async function simBreaker() {
    try {
      const result = await apiPost<{ open?: boolean; mode?: string }>("/v1/aip/circuit/trip", { failureRate: 0.06 });
      if (!isBreakerTripConfirmed(result)) throw new Error("服务端未确认降级到智能协作模式");
      setToast("服务端已确认熔断 · 失败率超过 5% → 降级为智能协作模式");
      evals.reload();
    } catch (e) {
      setToast(String((e as Error).message || e));
    }
  }

  const green = evals.data?.green === true;
  const workspaceAgentLabel = useMemo(() => {
    const items = agents.data?.items || [];
    if (!items.length) return null;
    const preferred =
      items.find((item) => String(item.instanceId || item.id || "").includes("content_officer")) || items[0];
    return preferred.overlay?.displayName || preferred.name || preferred.instanceId || preferred.id || null;
  }, [agents.data]);

  const levelLabel = level === 1 ? "临时分析" : level === 2 ? "任务智能体" : level === 3 ? "智能协作应用" : "自动化智能体";

  return (
    <S2Chrome
      title="智能体成熟度楼梯"
      lede="先完成临时分析，再固化任务智能体、嵌入业务应用，最后才进入受控自动化；页面预览不冒充真实上线门控。"
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
          { label: "当前成熟度", value: levelLabel },
          { label: "评测", value: green ? "通过" : "未运行" },
          { label: "审批草稿", value: String(drafts.data?.count ?? drafts.data?.items?.length ?? 0) },
          { label: "同事数", value: String(agents.data?.items?.length ?? 0) },
          { label: "自动化门控", value: evals.data?.l4Allowed === true ? "允许申请" : "尚未开放" },
        ].map((s) => (
          <div key={s.label} className="card" style={{ padding: "10px 12px" }}>
            <div style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>{s.label}</div>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{s.value}</div>
          </div>
        ))}
      </div>
      {/* 顶部状态条 · 对齐 aip-maturity.html 黄色背景卡片 */}
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
          <div style={{ fontSize: 12, color: "var(--aos-muted)", marginBottom: 2 }}>判定层</div>
          <div style={{ color: "var(--aos-amber-700)", fontWeight: 500 }}>◆ {levelLabel}</div>
        </div>
        <div style={{ fontSize: 12, color: "var(--aos-muted)", lineHeight: 1.6 }}>
          <div>
            评测 <span style={{ color: green ? "var(--aos-green-700)" : "var(--aos-amber-700)" }}>{green ? "● 通过" : "○ 未运行"}</span>
            {" · "}
            草稿 <span style={{ color: "var(--aos-green-700)" }}>审批台 {drafts.data?.count ?? drafts.data?.items?.length ?? "—"} 项</span>
          </div>
          <div>
            执行范围 <span style={{ color: "var(--aos-text)" }}>● 用户范围</span>
          </div>
        </div>
      </div>

      {/* 楼梯卡片网格 */}
      <BpMaturityStairs
        active={level}
        onSelect={setLevel}
        steps={[
          {
            level: 1,
            label: "探索",
            title: "临时分析",
            desc: "临时对话 · 拖入文档即可分析问答",
            foot: <span style={{ fontSize: 11, color: "var(--aos-indigo-600)" }}>沙箱 / 售前</span>,
          },
          {
            level: 2,
            label: "专用",
            title: "任务专用智能体",
            desc: "智能体配置 · 指令 · 工具 · 本体与知识库",
            foot: (
              <Link to="/aip/tools" style={{ fontSize: 11, color: "var(--aos-amber-700)", textDecoration: "none" }}>
                打开工具面板 →
              </Link>
            ),
          },
          {
            level: 3,
            label: "协作",
            title: "智能协作应用",
            desc: "工作台 · 智能体组件 · 业务变量绑定",
            foot: (
              <Link to="/workshop" style={{ fontSize: 11, color: "var(--aos-blue-600)", textDecoration: "none" }}>
                打开工作台 →
              </Link>
            ),
          },
          {
            level: 4,
            label: "自动化 · 须门控",
            title: "自动化智能体",
            desc: "发布为受控业务能力 · 须通过评测与草稿审批 · 失败率超过阈值自动降级",
            tone: "rose",
            foot: (
              <span
                style={{
                  fontSize: 11,
                  color: "var(--aos-red)",
                  padding: "2px 6px",
                  borderRadius: 4,
                  border: "1px solid var(--aos-red-border)",
                  background: "var(--aos-red-bg)",
                }}
              >
                私有模 · 预热中
              </span>
            ),
          },
        ]}
      />

      {/* 下一推荐 + 熔断护栏整合卡片 */}
      <div
        style={{
          marginTop: "1rem",
          borderRadius: 2,
          border: "1px solid var(--aos-border)",
          background: "rgba(255, 255, 255, 0.4)",
          padding: "20px",
        }}
      >
        <h2 style={{ fontSize: 14, fontWeight: 500, color: "var(--aos-text)", margin: "0 0 12px" }}>下一推荐</h2>
        <p style={{ fontSize: 14, color: "var(--aos-text-secondary)", margin: "0 0 12px" }}>
          {level < 3
            ? "嵌入工作台智能体组件后进入智能协作应用阶段；不要越级开启自动化。"
            : level === 3
              ? "评测通过且草稿审批流程稳定后，再申请受控自动化。"
              : "受控自动化必须通过评测门控并启用熔断护栏；完整运行时仍按权威状态开放。"}
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: toast ? 8 : 0 }}>
          <button
            type="button"
            onClick={() => { setLevel(3); setToast("仅切换本页智能协作阶段预览，不修改服务端成熟度"); }}
            style={{
              padding: "6px 12px",
              fontSize: 12,
              fontWeight: 500,
              borderRadius: 2,
              border: "none",
              background: "var(--aos-amber)",
              color: "var(--text-on-brand)",
              cursor: "pointer",
            }}
          >
            预览智能协作阶段
          </button>
          <button
            type="button"
            onClick={() => setToast(`自动化申请条件：评测${green ? "已通过" : "未通过"} · 草稿审批台 ${drafts.data?.count ?? drafts.data?.items?.length ?? "未知"} 项 · 必须启用熔断护栏`)}
            style={{
              padding: "6px 12px",
              fontSize: 12,
              borderRadius: 2,
              border: "1px solid var(--aos-red-border)",
              background: "transparent",
              color: "var(--aos-red)",
              cursor: "pointer",
            }}
          >
            查看自动化申请条件
          </button>
          <Link
            to="/aip/logic"
            style={{
              padding: "6px 12px",
              fontSize: 12,
              borderRadius: 2,
              border: "1px solid var(--aos-border)",
              background: "transparent",
              color: "var(--aos-text)",
              cursor: "pointer",
              textDecoration: "none",
            }}
          >
            打开业务逻辑编排
          </Link>
        </div>
        {toast && <p style={{ fontSize: 11, color: "var(--aos-muted)", margin: "4px 0 0" }}>{toast}</p>}

        {/* 熔断护栏子卡片 */}
        <div
          style={{
            marginTop: 12,
            borderRadius: 2,
            border: "1px solid var(--aos-red-border)",
            background: "var(--aos-red-bg)",
            padding: "16px",
          }}
        >
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center", marginBottom: 8 }}>
            <span style={{ color: "var(--aos-red)", fontWeight: 500, fontSize: 12 }}>自动化熔断护栏</span>
            <span
              style={{
                fontSize: 11,
                padding: "2px 8px",
                borderRadius: 4,
                border: "1px solid var(--aos-red-border)",
                color: "var(--aos-red)",
              }}
            >
              失败率超过 5% 时自动降级为智能协作
            </span>
            <span
              style={{
                fontSize: 11,
                padding: "2px 8px",
                borderRadius: 4,
                border: "1px solid var(--aos-amber-border)",
                color: "var(--aos-amber-700)",
              }}
            >
              私有模 · 预热中
            </span>
          </div>
          <p style={{ fontSize: 12, color: "var(--aos-muted)", margin: "0 0 12px" }}>
            上线前须评测通过且写操作默认进入草稿审批；模型预热完成前禁止全量自动化。
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            <Link
              to="/aip/evals"
              style={{
                fontSize: 11,
                padding: "4px 8px",
                borderRadius: 4,
                border: "1px solid var(--aos-border)",
                color: "var(--aos-amber-700)",
                textDecoration: "none",
              }}
            >
              评测门控
            </Link>
            <Link
              to="/aip/model-router"
              style={{
                fontSize: 11,
                padding: "4px 8px",
                borderRadius: 4,
                border: "1px solid var(--aos-border)",
                color: "var(--aos-text)",
                textDecoration: "none",
              }}
            >
              模型路由
            </Link>
            <button
              type="button"
              onClick={() => void simBreaker()}
              style={{
                fontSize: 11,
                padding: "4px 8px",
                borderRadius: 4,
                border: "1px solid var(--aos-red-border)",
                background: "transparent",
                color: "var(--aos-red)",
                cursor: "pointer",
              }}
            >
              模拟熔断降级
            </button>
          </div>
        </div>
      </div>

      {(evals.err || drafts.err) && <p className="error">{evals.err || drafts.err}</p>}
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
