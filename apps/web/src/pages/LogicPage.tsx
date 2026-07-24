import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";
import { BpDebugPanel, BpPropGrid, BpToolbar } from "./s2/blueprintUi";

type LogicNode = {
  id: string;
  kind: "query" | "function" | "llm" | "propose";
  title: string;
};

type DebugPayload = {
  dryRun?: boolean;
  proposedEdits?: unknown[];
  productionWritten?: boolean;
  graph?: { id: string; kind: string; title: string }[];
  edges?: string[];
};

const PALETTE: Omit<LogicNode, "id">[] = [
  { kind: "query", title: "Query · Object Set" },
  { kind: "function", title: "Function · transform" },
  { kind: "llm", title: "Use LLM" },
  { kind: "propose", title: "Propose Edits" },
];

const DEFAULT_GRAPH: LogicNode[] = [
  { id: "q1", kind: "query", title: "Query · WorkOrder" },
  { id: "f1", kind: "function", title: "Function · map fields" },
  { id: "l1", kind: "llm", title: "Use LLM · 建议" },
  { id: "p1", kind: "propose", title: "Propose Edits" },
];

const KIND_LABEL: Record<LogicNode["kind"], string> = {
  query: "Query",
  function: "Function",
  llm: "LLM",
  propose: "Propose",
};

/** 86 · Logic 三栏 + kind 色带 + Debug 折叠（dryRun 不落库） */
export function LogicPage() {
  const [graph, setGraph] = useState<LogicNode[]>(() => structuredClone(DEFAULT_GRAPH));
  const [selected, setSelected] = useState(DEFAULT_GRAPH[0].id);
  const [objectId, setObjectId] = useState("wo-1001");
  const [note, setNote] = useState("logic-ui");
  const [llmPrompt, setLlmPrompt] = useState(
    "你是 WorkOrder 运营助手。根据 objectId 与 note 给出简短建议，不写生产库。",
  );
  const [llmAnswer, setLlmAnswer] = useState("");
  const [llmPayload, setLlmPayload] = useState<unknown>(null);
  const [debug, setDebug] = useState<DebugPayload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const node = useMemo(
    () => graph.find((n) => n.id === selected) ?? graph[0],
    [graph, selected],
  );

  const edges = useMemo(() => {
    const lines: string[] = [];
    for (let i = 0; i < graph.length - 1; i++) {
      lines.push(`${graph[i].title} → ${graph[i + 1].title}`);
    }
    return lines;
  }, [graph]);

  function addFromPalette(kind: LogicNode["kind"], title: string) {
    const id = `${kind}-${Date.now().toString(36)}`;
    setGraph((g) => [...g, { id, kind, title }]);
    setSelected(id);
  }

  function removeSelected() {
    setGraph((g) => {
      if (g.length <= 1) return g;
      const next = g.filter((n) => n.id !== selected);
      setSelected(next[0]?.id || "");
      return next;
    });
  }

  async function tryLlm() {
    setBusy(true);
    setErr(null);
    setLlmAnswer("");
    setLlmPayload(null);
    try {
      const res = await apiPost<{ answer?: string; route?: string; provider?: string }>("/v1/aip/chat", {
        query: `${llmPrompt}\n\nobjectType=WorkOrder objectId=${objectId} note=${note}`,
        withTools: false,
      });
      setLlmAnswer(String(res.answer || "（无 answer）"));
      setLlmPayload(res);
    } catch (e) {
      setErr(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  async function dryRun() {
    setBusy(true);
    setErr(null);
    try {
      const res = await apiPost<{
        dryRun: boolean;
        proposedEdits: unknown[];
        productionWritten: boolean;
      }>("/v1/aip/logic/run", {
        dryRun: true,
        edits: [
          {
            objectType: "WorkOrder",
            objectId,
            set: { note },
          },
        ],
      });
      setDebug({
        ...res,
        graph: graph.map((n) => ({ id: n.id, kind: n.kind, title: n.title })),
        edges,
      });
    } catch (e) {
      setErr(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  const debugSummary = debug
    ? [
        { label: "dryRun", value: String(debug.dryRun ?? true), tone: "ok" },
        {
          label: "productionWritten",
          value: String(debug.productionWritten ?? false),
          tone: debug.productionWritten ? "warn" : "ok",
        },
        { label: "proposedEdits", value: String(debug.proposedEdits?.length ?? 0) },
        { label: "graph nodes", value: String(debug.graph?.length ?? graph.length) },
        { label: "edges", value: String(debug.edges?.length ?? edges.length) },
      ]
    : [];

  return (
    <PageChrome
      title="Logic 画布"
      lede="86 · 调色板 / 节点串 / Debug · dryRun 不落库 · 写生产须经 Draft"
    >
      <BpToolbar>
        <button type="button" className="btn" disabled={busy} onClick={() => void dryRun()}>
          {busy ? "运行中…" : "试跑 dryRun"}
        </button>
        <button type="button" className="btn" onClick={removeSelected}>
          删除选中
        </button>
        <Link to="/aip/drafts" className="btn" style={{ textDecoration: "none" }}>
          Draft 审批台
        </Link>
      </BpToolbar>

      {err && <p className="error">{err}</p>}

      <div className="canvas-grid canvas-grid-3">
        <div className="bp-logic-panel">
          <h2 className="bp-logic-panel-title">节点调色板</h2>
          <ul className="bp-logic-palette">
            {PALETTE.map((p) => (
              <li key={p.kind}>
                <button
                  type="button"
                  className={`bp-logic-chip bp-logic-${p.kind}`}
                  onClick={() => addFromPalette(p.kind, p.title)}
                >
                  + {p.title}
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="bp-logic-panel">
          <h2 className="bp-logic-panel-title">画布（串行图）</h2>
          <ul className="bp-logic-graph">
            {graph.map((n, i) => (
              <li key={n.id} className="bp-logic-graph-item">
                <button
                  type="button"
                  className={
                    n.id === selected
                      ? `bp-logic-node bp-logic-${n.kind} bp-logic-node-active`
                      : `bp-logic-node bp-logic-${n.kind}`
                  }
                  onClick={() => setSelected(n.id)}
                >
                  <span className="bp-logic-node-kind">{KIND_LABEL[n.kind]}</span>
                  <span className="bp-logic-node-title">
                    {i + 1}. {n.title}
                  </span>
                </button>
                {i < graph.length - 1 && <div className="bp-logic-edge">↓</div>}
              </li>
            ))}
          </ul>
        </div>

        <div className="bp-logic-panel">
          <h2 className="bp-logic-panel-title">Debug / 运行</h2>
          <p className="muted">选中：{node?.title || "—"}</p>
          <label className="muted" style={{ display: "block" }}>
            objectId{" "}
            <input value={objectId} onChange={(e) => setObjectId(e.target.value)} />
          </label>
          <label className="muted" style={{ display: "block", marginTop: 8 }}>
            propose note{" "}
            <input value={note} onChange={(e) => setNote(e.target.value)} />
          </label>

          {node?.kind === "llm" && (
            <div style={{ marginTop: "1rem" }}>
              <p className="bp-ws-section-title" style={{ fontSize: "0.8rem" }}>
                Use LLM 块
              </p>
              <label className="muted" style={{ display: "block", fontSize: "0.75rem" }}>
                Prompt
                <textarea
                  value={llmPrompt}
                  onChange={(e) => setLlmPrompt(e.target.value)}
                  rows={4}
                  style={{ display: "block", width: "100%", marginTop: 4 }}
                />
              </label>
              <button
                type="button"
                className="btn"
                style={{ marginTop: 8 }}
                disabled={busy}
                onClick={() => void tryLlm()}
              >
                试聊 LLM
              </button>
              {llmAnswer && (
                <p className="aos-text" style={{ fontSize: "0.875rem", marginTop: 8, whiteSpace: "pre-wrap" }}>
                  {llmAnswer}
                </p>
              )}
              {llmPayload != null && <BpDebugPanel value={llmPayload} title="LLM 原始 JSON" />}
            </div>
          )}

          {debug && (
            <div style={{ marginTop: "1rem" }}>
              <p className="aos-text" style={{ fontSize: "0.8rem" }}>
                productionWritten={String(debug.productionWritten)} · 须 Draft 才写生产
              </p>
              <BpPropGrid items={debugSummary} />
              <details style={{ marginTop: "0.75rem" }}>
                <summary className="muted">完整 Debug JSON</summary>
                <pre className="card" style={{ fontSize: "0.7rem", overflow: "auto", maxHeight: 220 }}>
                  {JSON.stringify(debug, null, 2)}
                </pre>
              </details>
            </div>
          )}
        </div>
      </div>
    </PageChrome>
  );
}
