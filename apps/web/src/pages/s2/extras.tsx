import { useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost, S2Chrome, useJsonGet } from "./shared";
import {
  BpBanner,
  BpKvList,
  BpLinkRow,
  BpMaturityStairs,
  BpMetricGrid,
  BpSplit,
  BpTable,
  BpToolbar,
} from "./blueprintUi";

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

  return (
    <S2Chrome
      title="Agent 成熟度楼梯"
      lede="别一上来做自动化。先 Threads，再固化 Agent，再嵌应用，最后才自动化。"
    >
      <BpToolbar>
        <Link to="/aip/tools" className="btn-nav">
          工具面板 →
        </Link>
        <Link to="/aip/logic" className="btn-nav">
          Logic 画布
        </Link>
      </BpToolbar>

      <div className="bp-domain bp-domain-aip" style={{ marginBottom: "1rem" }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "1.5rem", fontSize: "0.875rem" }}>
          <div>
            <div className="muted" style={{ fontSize: "0.65rem" }}>
              当前工作区
            </div>
            <div style={{ color: "var(--aos-text)", fontWeight: 500 }}>维修派单 Buddy</div>
          </div>
          <div>
            <div className="muted" style={{ fontSize: "0.65rem" }}>
              判定层
            </div>
            <div style={{ color: "#fcd34d", fontWeight: 500 }}>◆ L{level} 任务 Agent</div>
          </div>
          <div className="btn-nav">
            Eval {green ? "● 绿" : "○ 未绿"} · Draft ● 默认暂存 · 执行范围 ● 用户范围
          </div>
        </div>
      </div>

      <BpMaturityStairs
        active={level}
        onSelect={setLevel}
        steps={[
          {
            level: 1,
            label: "L1",
            title: "临时分析",
            desc: "AIP Threads · 拖文档即问即答",
            foot: <span className="muted" style={{ fontSize: "0.625rem" }}>沙箱 / 售前</span>,
          },
          {
            level: 2,
            label: "L2",
            title: "任务专用 Agent",
            desc: "Chatbot Studio · Prompt · 工具 · Ontology/Wiki",
            foot: (
              <Link to="/aip/tools" style={{ fontSize: "0.625rem", color: "#fcd34d" }}>
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
              <Link to="/workshop" style={{ fontSize: "0.625rem", color: "#7dd3fc" }}>
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
              <span className="bp-tag bp-tag-bad" style={{ fontSize: "0.625rem" }}>
                私有模 · 预热中
              </span>
            ),
          },
        ]}
      />

      <div className="bp-object-panel" style={{ marginTop: "1rem" }}>
        <h2 className="bp-ws-section-title">下一推荐</h2>
        <p className="muted" style={{ fontSize: "0.875rem" }}>
          {level < 3
            ? "挂 Workshop Agent 组件 → 升 L3；勿直接开 L4。"
            : level === 3
              ? "Eval 绿 + Draft 流程稳定后再申请 L4。"
              : "L4 须 Evals 门控 + 熔断护栏；完整运行时规划中。"}
        </p>
        <div className="bp-object-actions">
          <button type="button" className="btn" onClick={() => { setLevel(3); setToast("已标记 L3（本地 UI）"); }}>
            标记升级到 L3
          </button>
          <button type="button" className="btn" onClick={() => setToast("L4 评审须 Eval 绿 · 见 Evals 门控")}>
            申请 L4 上线评审
          </button>
          <Link to="/aip/logic" className="btn" style={{ textDecoration: "none" }}>
            Logic 画布
          </Link>
        </div>
        {toast && <p className="aos-text">{toast}</p>}
      </div>

      <BpBanner tone="warn">
        <strong>L4 熔断护栏</strong> · 失败率&gt;5% 自动降 L3 · 上线前须 Eval 绿 + Draft 默认暂存
        <div className="bp-object-actions" style={{ marginTop: "0.5rem" }}>
          <Link to="/aip/evals">Evals 门控</Link>
          {" · "}
          <Link to="/aip/drafts">Draft 审批台</Link>
          {" · "}
          <Link to="/aip/model-router">模型路由</Link>
          {" · "}
          <button type="button" className="btn" onClick={() => void simBreaker()}>
            模拟熔断降级
          </button>
        </div>
      </BpBanner>

      {evals.err && <p className="error">{evals.err}</p>}

      <BpLinkRow
        links={[
          { to: "/aip/evals", label: "Evals" },
          { to: "/aip/drafts", label: "Draft" },
          { to: "/aip/logic", label: "Logic" },
        ]}
      />
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

  const eventItems = [
    { title: "调拨完成", desc: "F1 → 华南仓 · 电容组件 500 件", time: "2 分钟前", tone: "ok" as const },
    { title: "SLA 预警", desc: "华南 F3 · 交期超时 12 单", time: "8 分钟前", tone: "warn" as const },
    { title: "库存盘点", desc: "CDC-1 · 差异率 0.03% · 通过", time: "25 分钟前", tone: "ok" as const },
    { title: "订单履约", desc: "ORD-8821 · 发货完成 · 物流 SF", time: "42 分钟前", tone: "ok" as const },
    { title: "AIP 决策", desc: "Buddy 建议对华南 F3 发起调拨", time: "1 小时前", tone: "default" as const },
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

export function ModuleInterfacePage() {
  const { data, err, reload } = useJsonGet<{
    items: {
      id: string;
      name: string;
      objectType?: string;
      entryPath?: string;
      widgets?: unknown[];
    }[];
  }>("/v1/modules");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [runtimeSummary, setRuntimeSummary] = useState("");
  const [msg, setMsg] = useState("");

  const selected = data?.items?.find((m) => m.id === selectedId) || data?.items?.[0];

  async function createMod() {
    await apiPost("/v1/modules", {
      name: "接口台 Module",
      description: "从模块接口页创建",
      objectType: "WorkOrder",
      entryPath: "/workshop/inbox",
      widgets: ["table", "filters", "selection"],
      buddyBound: true,
    });
    setMsg("已创建");
    reload();
  }

  async function openRuntime(id: string) {
    const r = await apiGet<{ entryPath?: string; widgets?: string[] }>(
      `/v1/modules/${encodeURIComponent(id)}/runtime`,
    );
    setRuntimeSummary(`runtime ${id} · entry=${r.entryPath} · widgets=${(r.widgets || []).join(",")}`);
  }

  const widgets = (selected?.widgets || []) as string[];
  const ot = selected?.objectType || "WorkOrder";
  const ifaceRows: (string | JSX.Element)[][] = [
    ["input.selection", `${ot}[]`, "入参"],
    ...(widgets.includes("filters") || widgets.some((w) => String(w).includes("filter"))
      ? [["input.filterStatus", "string", "入参"]]
      : []),
    ...(widgets.includes("table") || widgets.some((w) => String(w).includes("table"))
      ? [["output.selectedId", "string", "出参"]]
      : []),
    ...(widgets.includes("selection")
      ? [["output.selection", `${ot}[]`, "出参"]]
      : []),
  ];
  if (ifaceRows.length === 0) {
    ifaceRows.push(["input.selection", `${ot}[]`, "默认契约"]);
  }

  return (
    <S2Chrome title="Module 接口与嵌套 Loop" lede="定义子 Module 暴露的输入/输出接口，支持 Loop 嵌套渲染。">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => void createMod().catch(console.error)}>
          创建 Module
        </button>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
        <Link to="/workshop/canvas" className="btn-nav">
          返回画布 →
        </Link>
      </BpToolbar>
      {msg && <p className="aos-text">{msg}</p>}
      {err && <p className="error">{err}</p>}

      <BpSplit
        left={
          <div className="bp-object-panel">
            <div className="bp-ws-section-title">接口定义 · {selected?.name || "维修 Inbox"}</div>
            <BpTable
              columns={["接口", "类型", "方向"]}
              rows={ifaceRows.map((r) => [
                <span key={String(r[0])} style={{ color: String(r[2]).includes("出") ? "#6ee7b7" : "#7dd3fc" }}>
                  {r[0]}
                </span>,
                r[1],
                r[2],
              ])}
            />
            {selected && (
              <BpKvList
                rows={[
                  { key: "entryPath", value: selected.entryPath || "—", mono: true },
                  { key: "objectType", value: selected.objectType || "—" },
                  { key: "moduleId", value: selected.id, mono: true },
                ]}
              />
            )}
          </div>
        }
        right={
          <div className="bp-object-panel">
            <div className="bp-ws-section-title">嵌套 Loop</div>
            <div className="muted" style={{ fontSize: "0.8rem" }}>
              <div>父 Module：{selected?.name || "风险告警管理"}</div>
              <div style={{ marginLeft: "1rem", borderLeft: "2px solid rgba(56,189,248,0.3)", paddingLeft: "0.75rem", marginTop: 8 }}>
                <div className="card" style={{ marginBottom: 6 }}>子 Loop · 工单列表行</div>
                <div className="card">子 Module · 详情侧栏</div>
              </div>
              <p style={{ marginTop: 8 }}>
                Loop 变量 <code>row</code> 绑定至子 Module <code>input.workOrder</code>
              </p>
            </div>
          </div>
        }
      />

      <BpBanner tone="info">
        嵌套 Module 通过 Interface 契约解耦；Loop 内子 Module 可独立预览与测试。
      </BpBanner>

      <div className="bp-ws-section-title" style={{ marginTop: "1rem" }}>
        已注册 Module
      </div>
      <ul className="card-list">
        {(data?.items || []).map((m) => (
          <li key={m.id} className="card">
            <button
              type="button"
              className={selected?.id === m.id ? "nav-link active" : "nav-link"}
              onClick={() => setSelectedId(m.id)}
            >
              {m.name} <span className="muted">({m.id})</span>
            </button>
            <button
              type="button"
              className="btn"
              style={{ marginLeft: 8 }}
              onClick={() => void openRuntime(m.id)}
            >
              Runtime
            </button>
          </li>
        ))}
      </ul>
      {runtimeSummary && <p className="aos-text">{runtimeSummary}</p>}
    </S2Chrome>
  );
}
