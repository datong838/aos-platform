import { useCallback, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { apiPost } from "../../api/client";
import { PageChrome } from "../../components/PageChrome";

/* ── 类型定义 ── */

type BlockKind =
  | "input"
  | "create_variable"
  | "get_property"
  | "use_llm"
  | "use_tool"
  | "transform"
  | "apply_action"
  | "execute";

interface BlockDef {
  id: string;
  kind: BlockKind;
  label: string;
  config: Record<string, unknown>;
}

interface ExecutionResult {
  block_id: string;
  output: unknown;
  cot: string[];
  proposed_edits: Record<string, unknown>[];
}

/* ── 节点调色板定义 ── */

const PALETTE: { kind: BlockKind; title: string; desc: string; icon: string }[] = [
  {
    kind: "input",
    title: "Input · 输入",
    desc: "定义推理入口变量，如 objectId / objectType",
    icon: "📥",
  },
  {
    kind: "create_variable",
    title: "Create Variable",
    desc: "根据 DSL 表达式创建中间变量",
    icon: "📐",
  },
  {
    kind: "get_property",
    title: "Get Property",
    desc: "从 Ontology 对象读取属性值",
    icon: "🔗",
  },
  {
    kind: "use_llm",
    title: "Use LLM",
    desc: "调用大模型分析/生成/润色",
    icon: "🤖",
  },
  {
    kind: "use_tool",
    title: "Use Tool",
    desc: "调用注册的 Capability 工具",
    icon: "🔧",
  },
  {
    kind: "transform",
    title: "Transform",
    desc: "用 DSL 表达式变换数据",
    icon: "🔄",
  },
  {
    kind: "apply_action",
    title: "Apply Action",
    desc: "写回 Ontology（dryRun 不落库）",
    icon: "✏️",
  },
  {
    kind: "execute",
    title: "Execute",
    desc: "提交执行结果 / 触发通知",
    icon: "🚀",
  },
];

const KIND_COLORS: Record<BlockKind, string> = {
  input: "#6366f1",
  create_variable: "#14b8a6",
  get_property: "#f59e0b",
  use_llm: "#ec4899",
  use_tool: "#8b5cf6",
  transform: "#06b6d4",
  apply_action: "#f97316",
  execute: "#22c55e",
};

let _nextId = 0;
function uid(): string {
  _nextId += 1;
  return `b${_nextId}-${Date.now().toString(36)}`;
}

/* ── 主组件 ── */

type RightPanelTab = "config" | "history" | "automation";

interface RunHistoryEntry {
  timestamp: string;
  blockCount: number;
  dryRun: boolean;
  success: boolean;
  output: string;
}

const TRIGGER_TYPES = [
  { kind: "object_change", label: "对象变更", icon: "🔄", desc: "当 ObjectType 数据变化时触发" },
  { kind: "schedule", label: "定时触发", icon: "⏰", desc: "按 cron 表达式定时执行" },
  { kind: "manual", label: "人工触发", icon: "👤", desc: "用户手动点击执行" },
  { kind: "webhook", label: "Webhook", icon: "🔗", desc: "外部系统通过 HTTP 调用触发" },
  { kind: "threshold", label: "阈值告警", icon: "📊", desc: "当指标超过阈值时触发" },
];

export function LogicCanvasPage() {
  const [blocks, setBlocks] = useState<BlockDef[]>(() => [
    { id: uid(), kind: "input", label: "WorkOrder 输入", config: { objectType: "WorkOrder", objectId: "wo-1001" } },
    { id: uid(), kind: "get_property", label: "获取状态", config: { property: "status" } },
    { id: uid(), kind: "use_llm", label: "LLM 分析", config: { prompt: "分析工单状态并给出建议" } },
    { id: uid(), kind: "apply_action", label: "写回 note", config: { field: "note", valueFrom: "llm_output" } },
  ]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [execResults, setExecResults] = useState<ExecutionResult[]>([]);
  const [output, setOutput] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [dryRun, setDryRun] = useState(true);
  const [rightTab, setRightTab] = useState<RightPanelTab>("config");
  const [history, setHistory] = useState<RunHistoryEntry[]>([]);
  const [automationTriggers, setAutomationTriggers] = useState<Record<string, boolean>>({
    object_change: false,
    schedule: false,
    manual: true,
    webhook: false,
    threshold: false,
  });

  const canvasRef = useRef<HTMLDivElement>(null);
  const dragNode = useRef<{ kind: BlockKind; title: string } | null>(null);

  const selected = useMemo(() => blocks.find((b) => b.id === selectedId) ?? null, [blocks, selectedId]);

  /* ── 节点操作 ── */

  const addBlock = useCallback((kind: BlockKind) => {
    const def = PALETTE.find((p) => p.kind === kind)!;
    const b: BlockDef = { id: uid(), kind, label: def.title, config: {} };
    setBlocks((p) => [...p, b]);
    setSelectedId(b.id);
  }, []);

  const removeBlock = useCallback(() => {
    if (!selectedId) return;
    setBlocks((p) => p.filter((b) => b.id !== selectedId));
    setSelectedId("");
  }, [selectedId]);

  const moveBlock = useCallback((id: string, dir: -1 | 1) => {
    setBlocks((p) => {
      const idx = p.findIndex((b) => b.id === id);
      if (idx < 0) return p;
      const newIdx = idx + dir;
      if (newIdx < 0 || newIdx >= p.length) return p;
      const arr = [...p];
      [arr[idx], arr[newIdx]] = [arr[newIdx], arr[idx]];
      return arr;
    });
  }, []);

  const updateConfig = useCallback(
    (key: string, value: unknown) => {
      setBlocks((p) =>
        p.map((b) => (b.id === selectedId ? { ...b, config: { ...b.config, [key]: value } } : b)),
      );
    },
    [selectedId],
  );

  /* ── 拖拽 ── */

  const onDragStart = (kind: BlockKind, title: string) => {
    dragNode.current = { kind, title };
  };

  const onDrop = () => {
    if (dragNode.current) {
      addBlock(dragNode.current.kind);
      dragNode.current = null;
    }
  };

  /* ── 执行 ── */

  async function runLogic() {
    setBusy(true);
    setErr(null);
    setOutput("");
    try {
      const payload = {
        blocks: blocks.map((b) => ({
          id: b.id,
          kind: b.kind,
          name: b.label,
          config: b.config,
        })),
        dry_run: dryRun,
      };
      const res = await apiPost<{
        results?: ExecutionResult[];
        output?: unknown;
        cot?: string[];
        proposed_edits?: Record<string, unknown>[];
        production_written?: boolean;
      }>("/v1/aip/logic/execute", payload);
      setExecResults(res.results || []);
      setOutput(
        JSON.stringify(
          {
            output: res.output,
            cot: res.cot,
            proposed_edits: res.proposed_edits,
            production_written: res.production_written,
          },
          null,
          2,
        ),
      );
      setRightTab("history");
      setHistory((prev) => [{
        timestamp: new Date().toISOString().slice(11, 19),
        blockCount: blocks.length,
        dryRun,
        success: true,
        output: JSON.stringify(res.output, null, 2).slice(0, 200),
      }, ...prev].slice(0, 20));
    } catch (e: unknown) {
      setErr(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  /* ── 渲染 ── */

  return (
    <PageChrome
      title="AIP Logic 无代码编辑器"
      lede="拖拽编排 8 种 Block · 实时预览 · CoT 调试 · dryRun 不落库 · Draft 审批写生产"
    >
      {/* 工具栏 */}
      <div
        style={{
          display: "flex",
          gap: 8,
          alignItems: "center",
          marginBottom: 12,
          flexWrap: "wrap",
        }}
      >
        <button type="button" className="btn btn-primary" disabled={busy} onClick={runLogic}>
          {busy ? "⚙ 执行中…" : `▶ ${dryRun ? "dryRun 试跑" : "生产执行"}`}
        </button>
        <label style={{ fontSize: "0.8rem", display: "flex", alignItems: "center", gap: 4 }}>
          <input type="checkbox" checked={dryRun} onChange={() => setDryRun((v) => !v)} />
          dryRun（不落库）
        </label>
        {selected && (
          <button type="button" className="btn" onClick={removeBlock}>
            🗑 删除选中
          </button>
        )}
        <Link to="/aip/drafts" className="btn" style={{ textDecoration: "none" }}>
          📋 Draft 审批台
        </Link>
        <Link to="/aip/evals" className="btn" style={{ textDecoration: "none" }}>
          🛡 Evals 门控
        </Link>
        <span style={{ marginLeft: "auto", fontSize: "0.75rem", color: "var(--aos-muted)" }}>
          {blocks.length} blocks
        </span>
      </div>

      {err && (
        <div style={{ background: "#fecaca", color: "#991b1b", padding: "8px 12px", borderRadius: 6, marginBottom: 12, fontSize: "0.85rem" }}>
          {err}
        </div>
      )}

      {/* 三栏布局 */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "220px 1fr 320px",
          gap: 12,
          minHeight: "calc(100vh - 200px)",
        }}
      >
        {/* ── 左栏：节点调色板 ── */}
        <div
          style={{
            background: "var(--aos-card)",
            border: "1px solid var(--aos-border)",
            borderRadius: 8,
            padding: 12,
            overflowY: "auto",
          }}
        >
          <h3 style={{ fontSize: "0.85rem", margin: "0 0 10px", color: "var(--aos-text)" }}>
            Block 调色板
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {PALETTE.map((p) => (
              <button
                key={p.kind}
                type="button"
                draggable
                onDragStart={() => onDragStart(p.kind, p.title)}
                onClick={() => addBlock(p.kind)}
                title={p.desc}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "8px 10px",
                  border: `1px solid ${KIND_COLORS[p.kind]}30`,
                  borderLeft: `3px solid ${KIND_COLORS[p.kind]}`,
                  borderRadius: 6,
                  background: "var(--aos-card)",
                  cursor: "grab",
                  textAlign: "left",
                  fontSize: "0.8rem",
                  transition: "border-color 0.15s",
                }}
              >
                <span style={{ fontSize: "1.1rem" }}>{p.icon}</span>
                <span style={{ color: "var(--aos-text)", fontWeight: 500 }}>{p.title}</span>
              </button>
            ))}
          </div>
        </div>

        {/* ── 中栏：编排画布 ── */}
        <div
          ref={canvasRef}
          onDragOver={(e) => e.preventDefault()}
          onDrop={onDrop}
          style={{
            background: "var(--aos-card)",
            border: "1px solid var(--aos-border)",
            borderRadius: 8,
            padding: 16,
            overflowY: "auto",
            minHeight: 400,
          }}
        >
          <h3 style={{ fontSize: "0.85rem", margin: "0 0 12px", color: "var(--aos-text)" }}>
            {blocks.length > 0 ? `编排画布 · ${blocks.length} 个 Block` : "编排画布 · 从左侧拖拽节点"}
          </h3>
          {blocks.length === 0 ? (
            <div
              style={{
                height: 300,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                border: "2px dashed var(--aos-border)",
                borderRadius: 12,
                color: "var(--aos-muted)",
                fontSize: "0.95rem",
              }}
            >
              从左侧拖拽 Block 到此处，或点击添加
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {blocks.map((b, i) => (
                <div key={b.id} style={{ display: "flex", alignItems: "stretch", gap: 0 }}>
                  {/* 连线指示 */}
                  <div
                    style={{
                      width: 32,
                      display: "flex",
                      flexDirection: "column",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <div
                      style={{
                        width: 2,
                        height: 12,
                        background: i > 0 ? `${KIND_COLORS[blocks[i - 1].kind]}60` : "transparent",
                      }}
                    />
                    <div
                      style={{
                        width: 8,
                        height: 8,
                        borderRadius: "50%",
                        background: i > 0 ? KIND_COLORS[blocks[i - 1].kind] : "transparent",
                      }}
                    />
                  </div>
                  {/* Block 卡片 */}
                  <button
                    type="button"
                    onClick={() => setSelectedId(b.id)}
                    style={{
                      flex: 1,
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "10px 14px",
                      border: selectedId === b.id
                        ? `2px solid ${KIND_COLORS[b.kind]}`
                        : "1px solid var(--aos-border)",
                      borderLeft: `4px solid ${KIND_COLORS[b.kind]}`,
                      borderRadius: 6,
                      background: selectedId === b.id
                        ? `${KIND_COLORS[b.kind]}10`
                        : "var(--aos-card)",
                      cursor: "pointer",
                      textAlign: "left",
                      transition: "all 0.15s",
                    }}
                  >
                    <span style={{ fontSize: "0.85rem", fontWeight: 600, color: KIND_COLORS[b.kind], minWidth: 24 }}>
                      {i + 1}
                    </span>
                    <span
                      style={{
                        fontSize: "0.7rem",
                        padding: "2px 6px",
                        borderRadius: 4,
                        background: `${KIND_COLORS[b.kind]}20`,
                        color: KIND_COLORS[b.kind],
                        fontWeight: 600,
                        whiteSpace: "nowrap",
                      }}
                    >
                      {PALETTE.find((p) => p.kind === b.kind)?.icon} {b.kind}
                    </span>
                    <span style={{ flex: 1, fontSize: "0.82rem", color: "var(--aos-text)" }}>
                      {b.label}
                    </span>
                    {/* Move up/down */}
                    <span style={{ display: "flex", flexDirection: "column", gap: 1 }} onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        onClick={() => moveBlock(b.id, -1)}
                        disabled={i === 0}
                        style={{
                          background: "none", border: "none", cursor: i === 0 ? "default" : "pointer",
                          fontSize: "0.6rem", color: i === 0 ? "var(--aos-border)" : "var(--aos-muted)",
                          padding: "0 4px",
                        }}
                      >
                        ▲
                      </button>
                      <button
                        type="button"
                        onClick={() => moveBlock(b.id, 1)}
                        disabled={i === blocks.length - 1}
                        style={{
                          background: "none", border: "none", cursor: i === blocks.length - 1 ? "default" : "pointer",
                          fontSize: "0.6rem", color: i === blocks.length - 1 ? "var(--aos-border)" : "var(--aos-muted)",
                          padding: "0 4px",
                        }}
                      >
                        ▼
                      </button>
                    </span>
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ── 右栏：属性面板 + 历史 + 自动化 ── */}
        <div style={{ display: "flex", flexDirection: "column", gap: 12, overflowY: "auto" }}>
          {/* Tab switcher */}
          <div style={{ display: "flex", gap: 2, borderBottom: "2px solid var(--aos-border)" }}>
            {([
              { key: "config", label: "属性" },
              { key: "history", label: `历史 (${history.length})` },
              { key: "automation", label: "自动化" },
            ] as { key: RightPanelTab; label: string }[]).map((t) => (
              <button
                key={t.key}
                type="button"
                onClick={() => setRightTab(t.key)}
                style={{
                  padding: "6px 14px",
                  fontSize: "0.78rem",
                  fontWeight: rightTab === t.key ? 600 : 400,
                  border: "none",
                  borderBottom: rightTab === t.key ? "2px solid #3B82F6" : "2px solid transparent",
                  background: "none",
                  color: rightTab === t.key ? "#3B82F6" : "var(--aos-muted)",
                  cursor: "pointer",
                  marginBottom: "-2px",
                }}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Config tab */}
          {rightTab === "config" && (
          <div
            style={{
              background: "var(--aos-card)",
              border: "1px solid var(--aos-border)",
              borderRadius: 8,
              padding: 12,
            }}
          >
            <h3 style={{ fontSize: "0.85rem", margin: "0 0 10px", color: "var(--aos-text)" }}>
              Block 属性
            </h3>
            {selected ? (
              <div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    marginBottom: 10,
                  }}
                >
                  <span
                    style={{
                      width: 10,
                      height: 10,
                      borderRadius: "50%",
                      background: KIND_COLORS[selected.kind],
                    }}
                  />
                  <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--aos-text)" }}>
                    {selected.label || selected.kind}
                  </span>
                  <span
                    style={{
                      fontSize: "0.65rem",
                      padding: "1px 5px",
                      borderRadius: 3,
                      background: `${KIND_COLORS[selected.kind]}20`,
                      color: KIND_COLORS[selected.kind],
                    }}
                  >
                    {selected.kind}
                  </span>
                </div>

                {/* 通用属性 */}
                <label style={{ display: "block", fontSize: "0.75rem", marginBottom: 6 }}>
                  标签
                  <input
                    value={selected.label}
                    onChange={(e) => updateConfig("label", e.target.value)}
                    style={{ display: "block", width: "100%", marginTop: 2, fontSize: "0.8rem" }}
                  />
                </label>

                {/* 按 kind 渲染配置 */}
                {selected.kind === "input" && (
                  <>
                    <label style={{ display: "block", fontSize: "0.75rem", marginBottom: 6 }}>
                      Object Type
                      <input
                        value={String(selected.config.objectType || "WorkOrder")}
                        onChange={(e) => updateConfig("objectType", e.target.value)}
                        style={{ display: "block", width: "100%", marginTop: 2, fontSize: "0.8rem" }}
                      />
                    </label>
                    <label style={{ display: "block", fontSize: "0.75rem", marginBottom: 6 }}>
                      Object ID
                      <input
                        value={String(selected.config.objectId || "")}
                        onChange={(e) => updateConfig("objectId", e.target.value)}
                        style={{ display: "block", width: "100%", marginTop: 2, fontSize: "0.8rem" }}
                      />
                    </label>
                  </>
                )}
                {selected.kind === "get_property" && (
                  <label style={{ display: "block", fontSize: "0.75rem", marginBottom: 6 }}>
                    Property 名称
                    <input
                      value={String(selected.config.property || "status")}
                      onChange={(e) => updateConfig("property", e.target.value)}
                      style={{ display: "block", width: "100%", marginTop: 2, fontSize: "0.8rem" }}
                    />
                  </label>
                )}
                {selected.kind === "create_variable" && (
                  <>
                    <label style={{ display: "block", fontSize: "0.75rem", marginBottom: 6 }}>
                      变量名
                      <input
                        value={String(selected.config.name || "")}
                        onChange={(e) => updateConfig("name", e.target.value)}
                        style={{ display: "block", width: "100%", marginTop: 2, fontSize: "0.8rem" }}
                      />
                    </label>
                    <label style={{ display: "block", fontSize: "0.75rem", marginBottom: 6 }}>
                      DSL 表达式
                      <input
                        value={String(selected.config.expression || "")}
                        onChange={(e) => updateConfig("expression", e.target.value)}
                        style={{ display: "block", width: "100%", marginTop: 2, fontSize: "0.8rem" }}
                      />
                    </label>
                  </>
                )}
                {selected.kind === "use_llm" && (
                  <label style={{ display: "block", fontSize: "0.75rem", marginBottom: 6 }}>
                    Prompt
                    <textarea
                      value={String(selected.config.prompt || "")}
                      onChange={(e) => updateConfig("prompt", e.target.value)}
                      rows={4}
                      style={{ display: "block", width: "100%", marginTop: 2, fontSize: "0.8rem", resize: "vertical" }}
                    />
                  </label>
                )}
                {selected.kind === "use_tool" && (
                  <label style={{ display: "block", fontSize: "0.75rem", marginBottom: 6 }}>
                    Tool 名称
                    <input
                      value={String(selected.config.tool || "")}
                      onChange={(e) => updateConfig("tool", e.target.value)}
                      style={{ display: "block", width: "100%", marginTop: 2, fontSize: "0.8rem" }}
                    />
                  </label>
                )}
                {selected.kind === "transform" && (
                  <label style={{ display: "block", fontSize: "0.75rem", marginBottom: 6 }}>
                    DSL 表达式
                    <input
                      value={String(selected.config.expression || "")}
                      onChange={(e) => updateConfig("expression", e.target.value)}
                      style={{ display: "block", width: "100%", marginTop: 2, fontSize: "0.8rem" }}
                    />
                  </label>
                )}
                {selected.kind === "apply_action" && (
                  <>
                    <label style={{ display: "block", fontSize: "0.75rem", marginBottom: 6 }}>
                      Action Type
                      <input
                        value={String(selected.config.actionType || "")}
                        onChange={(e) => updateConfig("actionType", e.target.value)}
                        style={{ display: "block", width: "100%", marginTop: 2, fontSize: "0.8rem" }}
                      />
                    </label>
                    <label style={{ display: "block", fontSize: "0.75rem", marginBottom: 6 }}>
                      字段
                      <input
                        value={String(selected.config.field || "note")}
                        onChange={(e) => updateConfig("field", e.target.value)}
                        style={{ display: "block", width: "100%", marginTop: 2, fontSize: "0.8rem" }}
                      />
                    </label>
                  </>
                )}
                {selected.kind === "execute" && (
                  <label style={{ display: "block", fontSize: "0.75rem", marginBottom: 6 }}>
                    通知目标
                    <input
                      value={String(selected.config.notify || "")}
                      onChange={(e) => updateConfig("notify", e.target.value)}
                      style={{ display: "block", width: "100%", marginTop: 2, fontSize: "0.8rem" }}
                      placeholder="email / webhook / channel"
                    />
                  </label>
                )}
              </div>
            ) : (
              <p style={{ fontSize: "0.8rem", color: "var(--aos-muted)" }}>
                选择一个 Block 查看属性
              </p>
            )}
          </div>
          )}

          {/* History tab */}
          {rightTab === "history" && (
            <div style={{
              background: "var(--aos-card)",
              border: "1px solid var(--aos-border)",
              borderRadius: 8,
              padding: 12,
              flex: 1,
              overflowY: "auto",
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <h3 style={{ fontSize: "0.85rem", margin: 0, color: "var(--aos-text)" }}>执行历史</h3>
                {history.length > 0 && (
                  <button type="button" onClick={() => { setHistory([]); setExecResults([]); setOutput(""); }}
                    style={{ fontSize: "0.7rem", background: "none", border: "none", color: "var(--aos-muted)", cursor: "pointer" }}>
                    清除
                  </button>
                )}
              </div>

              {/* Latest results */}
              {execResults.length > 0 && (
                <details open style={{ marginBottom: 8 }}>
                  <summary style={{ fontSize: "0.75rem", cursor: "pointer", color: "var(--aos-muted)" }}>
                    CoT 推理链（{execResults.length} 步）
                  </summary>
                  <div style={{ marginTop: 6 }}>
                    {execResults.map((r, i) => (
                      <div key={r.block_id}
                        style={{
                          borderLeft: `3px solid ${KIND_COLORS[blocks[i]?.kind] || "#666"}`,
                          padding: "4px 8px",
                          marginBottom: 4,
                          fontSize: "0.72rem",
                          background: "var(--aos-card)",
                          borderRadius: "0 4px 4px 0",
                        }}>
                        <strong>Step {i + 1}</strong>{" "}
                        {r.cot.map((line, j) => (
                          <div key={j} style={{ color: "var(--aos-text)", marginTop: 2 }}>{line}</div>
                        ))}
                      </div>
                    ))}
                  </div>
                </details>
              )}

              {output && (
                <details open>
                  <summary style={{ fontSize: "0.75rem", cursor: "pointer", color: "var(--aos-muted)" }}>
                    最新输出 JSON
                  </summary>
                  <pre style={{
                    fontSize: "0.7rem", overflow: "auto", maxHeight: 200, marginTop: 6, padding: 8,
                    background: "#0d1117", color: "#c9d1d9", borderRadius: 6, lineHeight: 1.4,
                  }}>
                    {output}
                  </pre>
                </details>
              )}

              {/* History list */}
              {history.length > 0 ? (
                <div style={{ marginTop: 8 }}>
                  <div style={{ fontSize: "0.72rem", color: "var(--aos-muted)", marginBottom: 4 }}>运行记录</div>
                  {history.map((h, i) => (
                    <div key={i} style={{
                      display: "flex", alignItems: "center", gap: 6, padding: "4px 6px",
                      borderBottom: "1px solid var(--aos-border)", fontSize: "0.72rem",
                    }}>
                      <span style={{ color: h.success ? "#10B981" : "#EF4444" }}>{h.success ? "✓" : "✗"}</span>
                      <span style={{ color: "var(--aos-muted)", fontFamily: "monospace" }}>{h.timestamp}</span>
                      <span style={{ color: "var(--aos-text)" }}>{h.blockCount} blocks</span>
                      <span style={{ fontSize: "0.65rem", padding: "1px 4px", borderRadius: 3,
                        background: h.dryRun ? "#FEF3C7" : "#D1FAE5", color: h.dryRun ? "#92400E" : "#065F46" }}>
                        {h.dryRun ? "dry" : "prod"}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <p style={{ fontSize: "0.78rem", color: "var(--aos-muted)", marginTop: 8 }}>
                  点击 ▶ 执行按钮运行 Logic，历史记录将显示在此
                </p>
              )}
            </div>
          )}

          {/* Automation tab */}
          {rightTab === "automation" && (
            <div style={{
              background: "var(--aos-card)",
              border: "1px solid var(--aos-border)",
              borderRadius: 8,
              padding: 12,
              flex: 1,
              overflowY: "auto",
            }}>
              <h3 style={{ fontSize: "0.85rem", margin: "0 0 10px", color: "var(--aos-text)" }}>自动化触发器</h3>
              <p style={{ fontSize: "0.72rem", color: "var(--aos-muted)", marginBottom: 10 }}>
                配置 Logic 何时自动执行。可启用多种触发器组合。
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {TRIGGER_TYPES.map((t) => (
                  <label key={t.kind} style={{
                    display: "flex", alignItems: "center", gap: 8, padding: "8px 10px",
                    border: `1px solid ${automationTriggers[t.kind] ? "#3B82F6" : "var(--aos-border)"}`,
                    borderRadius: 6, cursor: "pointer", fontSize: "0.78rem",
                    background: automationTriggers[t.kind] ? "#3B82F610" : "transparent",
                  }}>
                    <input
                      type="checkbox"
                      checked={automationTriggers[t.kind] || false}
                      onChange={() => setAutomationTriggers((prev) => ({ ...prev, [t.kind]: !prev[t.kind] }))}
                    />
                    <span style={{ fontSize: "1rem" }}>{t.icon}</span>
                    <div>
                      <div style={{ fontWeight: 500, color: "var(--aos-text)" }}>{t.label}</div>
                      <div style={{ fontSize: "0.68rem", color: "var(--aos-muted)" }}>{t.desc}</div>
                    </div>
                  </label>
                ))}
              </div>
              <div style={{ marginTop: 12, padding: "8px 10px", background: "#FEF3C7", borderRadius: 6, fontSize: "0.7rem", color: "#92400E" }}>
                💡 已启用 {Object.values(automationTriggers).filter(Boolean).length} 个触发器。变更将在下次执行时生效。
              </div>
            </div>
          )}
        </div>
      </div>
    </PageChrome>
  );
}
