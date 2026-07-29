import { useState } from "react";
import { Link } from "react-router-dom";
import { apiPost, S2Chrome, useJsonGet } from "./shared";
import { BpMaturityStairs } from "./blueprintUi";

export { ModuleInterfacePage } from "./ModuleInterfacePage";

/** 81 · 对齐 aip-maturity.html · L1～L4 楼梯 */
export function MaturityPage() {
  const evals = useJsonGet<{ green?: boolean; l4Allowed?: boolean }>("/v1/aip/evals/status");
  const [level, setLevel] = useState(2);
  const [toast, setToast] = useState("");

  async function simBreaker() {
    try {
      await apiPost("/v1/aip/circuit/trip", { failureRate: 0.06 });
      setToast("已模拟熔断 · 失败率>5% → 降级 L3");
      evals.reload();
    } catch (e) {
      setToast(String((e as Error).message || e));
    }
  }

  const green = evals.data?.green === true;

  const levelLabel = level === 1 ? "临时分析" : level === 2 ? "任务 Agent" : level === 3 ? "Agentic 应用" : "自动化 Agent";

  return (
    <S2Chrome
      title="Agent 成熟度楼梯"
      lede="别一上来做自动化。先 Threads，再固化 Agent，再嵌应用，最后才自动化。"
    >
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
          <div style={{ color: "var(--aos-text)", fontWeight: 500 }}>维修派单 Buddy</div>
        </div>
        <div>
          <div style={{ fontSize: 12, color: "var(--aos-muted)", marginBottom: 2 }}>判定层</div>
          <div style={{ color: "var(--aos-amber-700)", fontWeight: 500 }}>◆ L{level} {levelLabel}</div>
        </div>
        <div style={{ fontSize: 12, color: "var(--aos-muted)", lineHeight: 1.6 }}>
          <div>
            Eval <span style={{ color: green ? "var(--aos-green-700)" : "var(--aos-amber-700)" }}>{green ? "● 绿" : "○ 未跑"}</span>
            {" · "}
            Draft <span style={{ color: "var(--aos-green-700)" }}>● 默认暂存</span>
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
            label: "L1",
            title: "临时分析",
            desc: "AIP Threads · 拖文档即问即答",
            foot: <span style={{ fontSize: 11, color: "var(--aos-indigo-600)" }}>沙箱 / 售前</span>,
          },
          {
            level: 2,
            label: "L2",
            title: "任务专用 Agent",
            desc: "Chatbot Studio · Prompt · 工具 · Ontology/Wiki",
            foot: (
              <Link to="/aip/tools" style={{ fontSize: 11, color: "var(--aos-amber-700)", textDecoration: "none" }}>
                打开工具面板 →
              </Link>
            ),
          },
          {
            level: 3,
            label: "L3",
            title: "Agentic 应用",
            desc: "工作台 / OSDK · Agent 组件 · 变量绑定",
            foot: (
              <Link to="/workshop" style={{ fontSize: 11, color: "var(--aos-blue-600)", textDecoration: "none" }}>
                打开工作台 →
              </Link>
            ),
          },
          {
            level: 4,
            label: "L4 · 须门控",
            title: "自动化 Agent",
            desc: "发布为 Function · Automate · 须 Eval + Draft · 失败率>5% 熔断降 L3",
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
            ? "挂 Workshop Agent 组件 → 升 L3；勿直接开 L4。"
            : level === 3
              ? "Eval 绿 + Draft 流程稳定后再申请 L4。"
              : "L4 须 Evals 门控 + 熔断护栏；完整运行时规划中。"}
        </p>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: toast ? 8 : 0 }}>
          <button
            type="button"
            onClick={() => { setLevel(3); setToast("已标记 L3（本地 UI）"); }}
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
            标记升级到 L3
          </button>
          <button
            type="button"
            onClick={() => setToast("L4 评审须 Eval 绿 · 见 Evals 门控")}
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
            申请 L4 上线评审
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
            并行：Logic 画布（可 Automate）
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
            <span style={{ color: "var(--aos-red)", fontWeight: 500, fontSize: 12 }}>L4 熔断护栏</span>
            <span
              style={{
                fontSize: 11,
                padding: "2px 8px",
                borderRadius: 4,
                border: "1px solid var(--aos-red-border)",
                color: "var(--aos-red)",
              }}
            >
              失败率&gt;5% 自动降 L3
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
            上线前须 Eval 绿 + Draft 默认暂存；冷模型预热完成前禁止全量自动化。
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
              Evals 门控
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

      {evals.err && <p className="error">{evals.err}</p>}
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

  const mockFactories = [
    { id: "f1", name: "华东 F1 · 上海", status: "正常" as const, desc: "在产 1,247 件 · 产能 92% · 交期 3.2d", warn: false },
    { id: "f2", name: "华东 F2 · 苏州", status: "正常" as const, desc: "在产 892 件 · 产能 87% · 交期 4.1d", warn: false },
    { id: "f3", name: "华南 F3 · 深圳", status: "预警" as const, desc: "在产 621 件 · 产能 64% · SLA 缺口 23%", warn: true },
  ];

  const riskItems = [
    { name: "华南 F3 · 深圳", tag: "SLA 缺口 23%", desc: "电容组件缺料 · 预计 7 天恢复", tone: "bad" as const },
    { name: "华北前置仓 FD-2", tag: "周转 24d", desc: "库存积压 · 建议调拨华南", tone: "warn" as const },
    { name: "华东 CDC-3", tag: "出库延迟 2.1h", desc: "WMS 批次作业排队中", tone: "warn" as const },
  ];

  const eventItems: { title: string; desc: string; time: string; tone: "ok" | "warn" | "bad" | "default" }[] = [
    { title: "调拨完成", desc: "F1 → 华南仓 · 电容组件 500 件", time: "2 分钟前", tone: "ok" },
    { title: "SLA 预警", desc: "华南 F3 · 交期超时 12 单", time: "8 分钟前", tone: "warn" },
    { title: "库存盘点", desc: "CDC-1 · 差异率 0.03% · 通过", time: "25 分钟前", tone: "ok" },
    { title: "订单履约", desc: "ORD-8821 · 发货完成 · 物流 SF", time: "42 分钟前", tone: "ok" },
    { title: "AIP 决策", desc: "Buddy 建议对华南 F3 发起调拨", time: "1 小时前", tone: "default" },
  ];

  return (
    <S2Chrome title="态势大屏" lede="对齐 workshop-cop · KPI 来自 graph-health / metrics / evals">
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
            <h2 className="p-cop-map-title">供应链网络态势</h2>
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
              <text x="200" y="126" textAnchor="middle" fill="currentColor" fontSize="12" fontWeight="500">CDCs</text>
              <text x="200" y="142" textAnchor="middle" fill="var(--aos-text-tertiary)" fontSize="10">3 中央仓</text>

              {/* Pipeline node */}
              <circle cx="340" cy="130" r="35" fill="rgba(56,161,105,0.08)" stroke="rgba(56,161,105,0.4)" strokeWidth="2" />
              <text x="340" y="126" textAnchor="middle" fill="currentColor" fontSize="12" fontWeight="500">FDs</text>
              <text x="340" y="142" textAnchor="middle" fill="var(--aos-text-tertiary)" fontSize="10">4 前置仓</text>

              {/* Source factories */}
              <rect x="20" y="55" width="60" height="36" rx="8" fill="rgba(43,108,176,0.08)" stroke="rgba(43,108,176,0.3)" strokeWidth="1.5" />
              <text x="50" y="78" textAnchor="middle" fill="currentColor" fontSize="10">华东 F1</text>
              <rect x="20" y="120" width="60" height="36" rx="8" fill="rgba(56,161,105,0.08)" stroke="rgba(56,161,105,0.3)" strokeWidth="1.5" />
              <text x="50" y="143" textAnchor="middle" fill="currentColor" fontSize="10">华东 F2</text>
              <rect x="20" y="185" width="60" height="36" rx="8" fill="rgba(214,158,46,0.08)" stroke="rgba(214,158,46,0.3)" strokeWidth="1.5" />
              <text x="50" y="208" textAnchor="middle" fill="currentColor" fontSize="10">华南 F3</text>

              {/* Destinations */}
              <rect x="410" y="55" width="56" height="36" rx="8" fill="rgba(56,161,105,0.08)" stroke="rgba(56,161,105,0.3)" strokeWidth="1.5" />
              <text x="438" y="78" textAnchor="middle" fill="currentColor" fontSize="10">华东仓</text>
              <rect x="410" y="120" width="56" height="36" rx="8" fill="rgba(43,108,176,0.08)" stroke="rgba(43,108,176,0.3)" strokeWidth="1.5" />
              <text x="438" y="143" textAnchor="middle" fill="currentColor" fontSize="10">华北仓</text>
              <rect x="410" y="185" width="56" height="36" rx="8" fill="rgba(229,62,62,0.08)" stroke="rgba(229,62,62,0.3)" strokeWidth="1.5" />
              <text x="438" y="208" textAnchor="middle" fill="currentColor" fontSize="10">华南仓</text>

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
            {mockFactories.map((f) => (
              <button
                key={f.id}
                type="button"
                className={`p-cop-factory-card${f.warn ? " is-warn" : ""}${focusType === f.id ? " is-active" : ""}`}
                onClick={() => setFocusType(f.id)}
              >
                <div className="p-cop-factory-head">
                  <span className="p-cop-factory-name">{f.name}</span>
                  <span className="p-cop-factory-status">{f.status}</span>
                </div>
                <div className="p-cop-factory-desc">{f.desc}</div>
              </button>
            ))}
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
            <button type="button" className="p-cop-action-btn">
              🟡 调拨 · 华南紧急补货
            </button>
            <Link to="/workshop/inbox" className="p-cop-action-btn is-secondary">
              打开运营 Inbox →
            </Link>
          </div>
        </div>
      </div>

      {/* Bottom row: detail tables / alerts */}
      <div className="p-cop-bottom">
        {/* Risk factory detail */}
        <div className="p-cop-panel is-bad">
          <div className="p-cop-panel-head">
            <h2 className="p-cop-panel-title">风险工厂详情</h2>
            <span className="p-cop-map-subtitle">{riskItems.length} 家须关注</span>
          </div>
          <div className="p-cop-risk-list">
            {riskItems.map((r, i) => (
              <div key={i} className={`p-cop-risk-item${r.tone === "bad" ? " is-bad" : " is-warn"}`}>
                <div>
                  <span className="p-cop-risk-name">{r.name}</span>
                  <span className="p-cop-risk-tag">{r.tag}</span>
                </div>
                <span className="p-cop-risk-desc">{r.desc}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Recent events */}
        <div className="p-cop-panel">
          <div className="p-cop-panel-head">
            <h2 className="p-cop-panel-title">实时事件 · Action 记录</h2>
            <Link to="/workshop/events" className="p-cop-panel-link">全部事件 →</Link>
          </div>
          <div className="p-cop-event-list">
            {eventItems.map((e, i) => (
              <div key={i} className="p-cop-event-item">
                <span className={`p-cop-event-dot${e.tone === "ok" ? " is-ok" : e.tone === "warn" ? " is-warn" : e.tone === "bad" ? " is-bad" : ""}`} />
                <div className="p-cop-event-body">
                  <span className="p-cop-event-title">{e.title}</span>
                  <span className="p-cop-event-desc">{e.desc}</span>
                </div>
                <span className="p-cop-event-time">{e.time}</span>
              </div>
            ))}
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
