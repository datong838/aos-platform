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
        <Link to="/aip/tools" className="muted">
          工具面板 →
        </Link>
        <Link to="/aip/logic" className="muted">
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
          <div className="muted" style={{ fontSize: "0.75rem" }}>
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
              : "L4 须 Evals 门控 + 熔断护栏；Full 运行时仍后置。"}
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

/** 82 · 对齐 workshop-cop.html · 4 KPI + Map/Graph + 钻取侧栏 */
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

  return (
    <S2Chrome title="态势大屏" lede="对齐 workshop-cop · KPI 来自 graph-health / metrics / evals">
      <BpToolbar>
        <button
          type="button"
          className="btn"
          onClick={() => {
            health.reload();
            metrics.reload();
            evals.reload();
            types.reload();
          }}
        >
          刷新态势
        </button>
        <span className="muted" style={{ fontSize: "0.75rem" }}>
          全屏态势布局 · 非独立大屏产品
        </span>
        <Link to="/workshop" className="muted">
          退出全屏示意 →
        </Link>
      </BpToolbar>
      {(health.err || metrics.err || evals.err) && (
        <p className="error">{health.err || metrics.err || evals.err}</p>
      )}

      <BpMetricGrid
        items={[
          {
            label: "在途订单（实例）",
            value: hm?.instances ?? "—",
            tone: "ok",
          },
          {
            label: "孤立实例",
            value: hm?.orphanInstances ?? "—",
            tone: (hm?.orphanInstances ?? 0) > 10 ? "warn" : "muted",
          },
          {
            label: "API p95 (ms)",
            value: totals?.p95Ms != null ? totals.p95Ms.toFixed(1) : "—",
            tone: "muted",
          },
          {
            label: "风险信号",
            value: riskCount,
            tone: riskCount > 0 ? "bad" : "ok",
          },
        ]}
      />

      <BpSplit
        left={
          <div className="bp-cop-map">
            <p className="muted" style={{ fontSize: "0.75rem", marginBottom: "0.75rem" }}>
              Map / Graph 主视觉 · 点选 Object Type 更新钻取（score={health.data?.score ?? "—"} · edges=
              {hm?.edges ?? "—"}）
            </p>
            <div className="bp-cop-nodes">
              {(types.data?.items || []).slice(0, 8).map((t) => (
                <button
                  key={t.id}
                  type="button"
                  className={`bp-cop-node${focusType === t.id ? " is-active" : ""}`}
                  onClick={() => setFocusType(t.id)}
                >
                  {t.name}
                </button>
              ))}
              {(types.data?.items?.length || 0) === 0 && (
                <span className="muted">暂无 Object Type · 先初始化种子</span>
              )}
            </div>
          </div>
        }
        right={
          <div className="bp-cop-sidebar">
            <div className="bp-ws-section-title">钻取 · Object View</div>
            {focusMeta ? (
              <>
                <p className="aos-text">
                  {focusMeta.name} · <span className="muted">{focusMeta.id}</span>
                </p>
                <p className="muted" style={{ fontSize: "0.8rem" }}>
                  图谱健康 {health.data?.score ?? "—"} · Eval {green ? "绿" : "未绿"}
                </p>
                <Link to="/workshop/inbox" className="nav-link">
                  打开运营 Inbox →
                </Link>
                <Link to={`/ontology`} className="btn" style={{ marginTop: 8, display: "block" }}>
                  本体 Discover →
                </Link>
              </>
            ) : (
              <p className="muted">点选左侧节点查看钻取</p>
            )}
            <button type="button" className="btn" style={{ marginTop: "1rem", width: "100%" }}>
              调拨 Action 🟡
            </button>
          </div>
        }
      />

      <BpLinkRow
        links={[
          { to: "/ontology/graph-health", label: "图谱健康" },
          { to: "/aip/evals", label: "Evals 门控" },
          { to: "/workshop/inbox", label: "运营 Inbox" },
        ]}
      />
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
        <Link to="/workshop/canvas" className="muted">
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
              <div>父 Module：{selected?.name || "运营台"}</div>
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
