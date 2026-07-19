import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";
import { BpDebugPanel, BpLinkRow, BpSplit, BpTable, BpTabs, BpToolbar } from "./s2/blueprintUi";

const STUDIO_TABS = [
  { id: "prompt", label: "Prompt" },
  { id: "tools", label: "工具绑定" },
  { id: "try", label: "试对话" },
  { id: "publish", label: "发布门控" },
];

const DEMO_TOOLS = [
  { id: "query.objects", kind: "Query Objects", status: "开", tone: "ok" as const },
  { id: "wiki.fields", kind: "Wiki 字段 Tool ★", status: "结构化优先", tone: "warn" as const },
  { id: "action.dispatch", kind: "Action · 派单", status: "HITL", tone: "warn" as const },
];

/** 90 · 对齐 agents.html · 4 Tab + L2 门控 + Prompt chips */
export function StudioPage() {
  const [tab, setTab] = useState("prompt");
  const [tools, setTools] = useState<{ id: string; kind: string }[]>([]);
  const [selected, setSelected] = useState<string[]>(["query.objects"]);
  const [agentName, setAgentName] = useState("WorkOrder 派单 Buddy");
  const [systemPrompt, setSystemPrompt] = useState(
    "你是 WorkOrder 运营助手。优先读 Object 与 Wiki 结构化字段，禁止臆造字段。写回必须走 Action / Draft。",
  );
  const [defaultModel, setDefaultModel] = useState("—");
  const [lastRoute, setLastRoute] = useState<string | null>(null);
  const [chatPayload, setChatPayload] = useState<unknown>(null);
  const [query, setQuery] = useState("wo-1001 当前风险与建议下一步？");
  const [answer, setAnswer] = useState("");
  const [toolCalls, setToolCalls] = useState<unknown[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    apiGet<{ items: { id: string; kind: string }[] }>("/v1/aip/tools")
      .then((r) => setTools(r.items))
      .catch((e) => setErr(String(e.message || e)));
    apiGet<{ defaultTextModel?: string }>("/v1/aip/models")
      .then((r) => setDefaultModel(r.defaultTextModel || "—"))
      .catch(() => setDefaultModel("—"));
  }, []);

  function toggle(id: string) {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  }

  async function onChat(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      const res = await apiPost<{
        answer: string;
        toolCalls: unknown[];
        route?: string;
        provider?: string;
      }>("/v1/aip/chat", {
        query: `【System】${systemPrompt}\n\n【User】${query}`,
        withTools: selected.length > 0,
        tools: selected,
      });
      setAnswer(res.answer);
      setLastRoute(`${res.route || "?"} · ${res.provider || "?"}`);
      setChatPayload(res);
      setToolCalls(res.toolCalls || []);
      setTab("try");
    } catch (ex) {
      setErr(String((ex as Error).message || ex));
    }
  }

  const toolRows = (tools.length > 0 ? tools : DEMO_TOOLS.map((t) => ({ id: t.id, kind: t.kind }))).map(
    (t) => {
      const demo = DEMO_TOOLS.find((d) => d.id === t.id);
      return [
        t.kind || t.id,
        <label key={t.id}>
          <input
            type="checkbox"
            checked={selected.includes(t.id)}
            onChange={() => toggle(t.id)}
          />{" "}
          {selected.includes(t.id) ? "开" : "关"}
        </label>,
        demo?.status || "—",
      ];
    },
  );

  return (
    <PageChrome title="Chatbot Studio" lede="配置壳：Prompt · 工具 · Ontology/Wiki · L4 须 Evals 绿">
      <BpToolbar>
        <span className="bp-studio-badge">L2 任务 Agent</span>
        <Link to="/aip/tools" className="btn" style={{ textDecoration: "none", fontSize: "0.75rem" }}>
          工具面板
        </Link>
        <Link to="/aip/evals" className="btn-nav">
          Evals
        </Link>
      </BpToolbar>

      <BpTabs tabs={STUDIO_TABS} active={tab} onChange={setTab} />

      <div style={{ marginTop: "1rem" }}>
        {tab === "prompt" && (
          <div className="bp-object-panel">
            <h1 className="aos-text" style={{ fontSize: "1.1rem" }}>
              Chatbot Studio · {agentName}
            </h1>
            <p className="muted" style={{ fontSize: "0.875rem" }}>
              配置壳：Prompt · 工具 · Ontology/Wiki 上下文 · L4 须 Evals 绿 + Draft 默认
            </p>
            <label className="muted" style={{ display: "block", fontSize: "0.75rem", marginTop: "1rem" }}>
              名称
              <input
                value={agentName}
                onChange={(e) => setAgentName(e.target.value)}
                style={{ display: "block", width: "100%", marginTop: 4 }}
              />
            </label>
            <label className="muted" style={{ display: "block", marginTop: 8, fontSize: "0.75rem" }}>
              系统提示词
              <textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                rows={5}
                style={{ display: "block", width: "100%", marginTop: 4 }}
              />
            </label>
            <div className="bp-studio-chips">
              <span className="bp-studio-chip bp-studio-chip-violet">/WorkOrder.status</span>
              <span className="bp-studio-chip bp-studio-chip-orange">/Wiki.summary</span>
              <span className="bp-studio-chip bp-studio-chip-amber">默认模型 · {defaultModel}</span>
            </div>
          </div>
        )}

        {tab === "tools" && (
          <div className="bp-object-panel">
            <p className="muted">已绑定工具（含 API 目录）</p>
            <BpTable columns={["工具", "开关", "策略"]} rows={toolRows} />
            <BpLinkRow links={[{ to: "/aip/tools", label: "打开完整工具面板" }]} />
          </div>
        )}

        {tab === "try" && (
          <BpSplit
            left={
              <div className="bp-object-panel">
                <div className="bp-ws-section-title">试对话</div>
                <form className="filter-bar" onSubmit={onChat}>
                  <input
                    aria-label="studio-query"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    style={{ flex: 1, minWidth: 0 }}
                  />
                  <button type="submit" className="btn">
                    发送
                  </button>
                </form>
                {err && <p className="error">{err}</p>}
                {answer && (
                  <div style={{ marginTop: "0.75rem" }}>
                    <div className="muted" style={{ fontSize: "0.7rem" }}>Buddy · {lastRoute}</div>
                    <p className="aos-text" style={{ whiteSpace: "pre-wrap", marginTop: 4 }}>
                      {answer}
                    </p>
                  </div>
                )}
                {chatPayload != null && (
                  <BpDebugPanel value={chatPayload} title="试对话原始 JSON" />
                )}
                {toolCalls.length > 0 && (
                  <div style={{ marginTop: "0.75rem" }}>
                    <BpTable
                      columns={["tool", "status", "detail"]}
                      rows={toolCalls.map((tc, i) => {
                        const t = tc as Record<string, unknown>;
                        return [
                          String(t.id || t.tool || `#${i + 1}`),
                          String(t.status || "—"),
                          String(t.summary || t.result || "—"),
                        ];
                      })}
                    />
                  </div>
                )}
              </div>
            }
            right={
              <div className="bp-object-panel">
                <div className="bp-ws-section-title">工作台预览</div>
                <p className="muted" style={{ fontSize: "0.875rem" }}>
                  已读 WorkOrder + Wiki。建议 Action「更新状态」→ 进入提案审批。
                </p>
                <Link
                  to="/workshop/buddy?order=wo-1001&assist=1"
                  className="nav-link"
                >
                  在工作台预览 Buddy 组件 →
                </Link>
              </div>
            }
          />
        )}

        {tab === "publish" && (
          <div className="bp-studio-gate">
            <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
              L4 发布为 Function
            </h2>
            <label className="muted" style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
              <input type="checkbox" disabled /> 启用无人值守写回
            </label>
            <p className="bp-prop-warn" style={{ fontSize: "0.75rem", marginTop: 8 }}>
              未满足门控：Evals 须绿 · Draft 须默认暂存。当前不可勾选。
            </p>
            <BpLinkRow
              links={[
                { to: "/aip/evals", label: "去跑 Evals" },
                { to: "/aip/drafts", label: "Draft 审批台" },
                { to: "/aip/maturity", label: "成熟度楼梯" },
              ]}
            />
          </div>
        )}
      </div>
    </PageChrome>
  );
}
