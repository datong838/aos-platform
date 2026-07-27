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
  | "execute"
  | "branch"
  | "handoff";

/** Branch 双路分叉定义 */
export interface BranchPath {
  id: string;
  label: string;
  condition: string;
  color: string;
}

/** Handoff 汇聚配置 */
export interface HandoffConfig {
  decision: string;
  artifacts: string[];
  open_qs: string[];
  handoff_to: "risk_agent" | "draft_inbox" | "webhook";
}

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
  {
    kind: "branch",
    title: "Branch · 分支",
    desc: "条件分叉：根据表达式选择执行路径",
    icon: "🔀",
  },
  {
    kind: "handoff",
    title: "Handoff · 汇聚",
    desc: "汇聚多路上下文，输出决策摘要+产物+待确认项",
    icon: "🔗",
  },
];

/** Block 样式元数据（导出供测试） */
export const KIND_META: Record<BlockKind, { label: string; color: string; bg: string; border: string }> = {
  input:          { label: "输入",      color: "var(--aos-indigo)", bg: "var(--aos-indigo-bg)", border: "var(--aos-indigo-border)" },
  create_variable:{ label: "创建变量",  color: "var(--color-info)", bg: "var(--aos-accent-light)", border: "var(--aos-green-border)" },
  get_property:   { label: "获取属性",  color: "var(--aos-amber)", bg: "var(--aos-amber-bg)", border: "var(--aos-amber-border)" },
  use_llm:        { label: "使用 LLM",  color: "var(--aos-purple-600)", bg: "var(--aos-indigo-bg)", border: "var(--aos-indigo-border)" },
  use_tool:       { label: "使用工具",  color: "var(--aos-purple-600)", bg: "var(--aos-indigo-bg)", border: "var(--aos-indigo-border)" },
  transform:      { label: "数据变换",  color: "var(--color-info)", bg: "var(--aos-accent-light)", border: "var(--aos-accent-border)" },
  apply_action:   { label: "应用动作",  color: "var(--aos-amber-600)", bg: "var(--aos-amber-bg)", border: "var(--aos-amber-border)" },
  execute:        { label: "执行",      color: "var(--aos-green)", bg: "var(--aos-green-bg)", border: "var(--aos-green-border)" },
  branch:         { label: "分支",      color: "var(--aos-red)", bg: "var(--aos-red-bg)", border: "var(--aos-red-border)" },
  handoff:        { label: "汇聚",      color: "var(--aos-indigo-600)", bg: "var(--aos-indigo-bg)", border: "var(--aos-indigo-border)" },
};

/** 向后兼容：部分渲染处仅需要颜色字符串 */
const KIND_COLORS: Record<BlockKind, string> = Object.fromEntries(
  (Object.entries(KIND_META) as [BlockKind, { color: string }][]).map(([k, v]) => [k, v.color]),
) as Record<BlockKind, string>;

/** 导出 PALETTE 供测试 */
export { PALETTE };

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
    const defaultConfig: Record<string, unknown> =
      kind === "branch"
        ? {
            paths: [
              { id: "p1", label: "高风险", condition: "risk_level IN [high, critical]", color: "var(--aos-red)" },
              { id: "p2", label: "低风险", condition: "risk_level IN [low, medium]", color: "var(--aos-green-600)" },
            ],
          }
        : kind === "handoff"
          ? {
              decision: "风险分诊结论：中等风险，建议人工复核",
              artifacts: ["risk_assessment.json", "order_snapshot.diff"],
              open_qs: ["是否需要升级到 L4 模型？"],
              handoff_to: "draft_inbox" as const,
            }
          : {};
    const b: BlockDef = { id: uid(), kind, label: def.title, config: defaultConfig };
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
      lede="拖拽编排 10 种 Block · 实时预览 · CoT 调试 · dryRun 不落库 · Draft 审批写生产 · 分支+汇聚"
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
        <div style={{ background: "var(--aos-red-border)", color: "var(--aos-red)", padding: "8px 12px", borderRadius: 2, marginBottom: 12, fontSize: "0.85rem" }}>
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
            borderRadius: 2,
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
                  borderRadius: 2,
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
            borderRadius: 2,
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
                borderRadius: 2,
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
                      borderRadius: 2,
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

                  {/* Branch Block 双路分叉视觉 */}
                  {b.kind === "branch" && (
                    <div style={{ width: "100%", marginTop: 2 }}>
                      <div style={{ textAlign: "center", color: "var(--aos-text-tertiary)", fontSize: 10, padding: "2px 0" }}>↓ ↓</div>
                      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                        {((b.config.paths as BranchPath[]) || []).map((p, pi) => (
                          <div
                            key={p.id}
                            style={{
                              borderRadius: 2,
                              border: `1px solid ${p.color}60`,
                              background: `${p.color}0A`,
                              padding: "6px 8px",
                              fontSize: "0.68rem",
                            }}
                          >
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                              <span style={{ color: p.color, fontWeight: 600 }}>分支 · {p.label}</span>
                              <span style={{ fontSize: 9, color: "var(--aos-text-tertiary)" }}>#{pi === 0 ? "4A" : "4B"}</span>
                            </div>
                            <div style={{ fontFamily: "monospace", color: "var(--aos-text-secondary)", marginTop: 2, fontSize: "0.62rem" }}>
                              {p.condition}
                            </div>
                          </div>
                        ))}
                      </div>
                      <div style={{ textAlign: "center", color: "var(--aos-text-tertiary)", fontSize: 10, padding: "2px 0" }}>↓ ↓ 汇聚</div>
                    </div>
                  )}

                  {/* Handoff Block 三区域预览 */}
                  {b.kind === "handoff" && (
                    <div
                      style={{
                        width: "100%", marginTop: 2,
                        borderRadius: 2, border: "2px solid var(--aos-indigo-border)", background: "var(--aos-indigo-bg)",
                        padding: 8, fontSize: "0.68rem",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 6 }}>
                        <span style={{ fontSize: "0.75rem" }}>🔗</span>
                        <span style={{ color: "var(--aos-indigo-600)", fontWeight: 600 }}>汇聚 · Handoff 上下文</span>
                      </div>
                      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 4 }}>
                        <div style={{ borderRadius: 4, background: "rgba(255,255,255,0.6)", border: "1px solid var(--aos-indigo-border)", padding: "4px 6px" }}>
                          <div style={{ fontSize: 9, color: "var(--aos-text-tertiary)" }}>decision</div>
                          <div style={{ fontSize: 10, color: "var(--aos-text)", fontWeight: 500, marginTop: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                            {String(b.config.decision || "—").slice(0, 12) || "—"}
                          </div>
                        </div>
                        <div style={{ borderRadius: 4, background: "rgba(255,255,255,0.6)", border: "1px solid var(--aos-indigo-border)", padding: "4px 6px" }}>
                          <div style={{ fontSize: 9, color: "var(--aos-text-tertiary)" }}>artifacts</div>
                          <div style={{ fontSize: 10, color: "var(--aos-text)", fontWeight: 500, marginTop: 1 }}>
                            {((b.config.artifacts as string[]) || []).length} 个产物
                          </div>
                        </div>
                        <div style={{ borderRadius: 4, background: "rgba(255,255,255,0.6)", border: "1px solid var(--aos-indigo-border)", padding: "4px 6px" }}>
                          <div style={{ fontSize: 9, color: "var(--aos-text-tertiary)" }}>open_qs</div>
                          <div style={{ fontSize: 10, color: "var(--aos-text)", fontWeight: 500, marginTop: 1 }}>
                            {((b.config.open_qs as string[]) || []).length} 个待确认
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
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
                  borderBottom: rightTab === t.key ? "2px solid var(--aos-blue)" : "2px solid transparent",
                  background: "none",
                  color: rightTab === t.key ? "var(--aos-blue)" : "var(--aos-muted)",
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
              borderRadius: 2,
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

                {/* Branch 配置：条件表达式 + 双路分叉 */}
                {selected.kind === "branch" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    <div style={{ fontSize: "0.72rem", color: "var(--aos-muted)", background: "var(--aos-red-bg)", padding: "6px 8px", borderRadius: 2, border: "1px solid var(--aos-red-border)" }}>
                      🔀 Branch Block · 根据 condition 表达式分叉到不同路径
                    </div>
                    {((selected.config.paths as BranchPath[]) || []).map((p, idx) => (
                      <div
                        key={p.id}
                        style={{
                          border: `1px solid ${p.color}40`,
                          borderLeft: `3px solid ${p.color}`,
                          borderRadius: 2,
                          padding: 10,
                          background: `${p.color}08`,
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                          <span style={{ fontSize: "0.65rem", fontWeight: 700, color: p.color }}>
                            路径 {idx === 0 ? "A" : "B"} · #{idx === 0 ? "4A" : "4B"}
                          </span>
                          <input
                            value={p.label}
                            onChange={(e) => {
                              const paths = [...((selected.config.paths as BranchPath[]) || [])];
                              paths[idx] = { ...p, label: e.target.value };
                              updateConfig("paths", paths);
                            }}
                            placeholder={idx === 0 ? "高风险" : "低风险"}
                            style={{
                              flex: 1, fontSize: "0.78rem", fontWeight: 600,
                              color: p.color, border: `1px solid ${p.color}40`, borderRadius: 4,
                              padding: "2px 6px", background: "var(--aos-card)",
                            }}
                          />
                        </div>
                        <label style={{ display: "block", fontSize: "0.7rem", marginBottom: 6, color: "var(--aos-muted)" }}>
                          条件表达式
                          <input
                            value={p.condition}
                            onChange={(e) => {
                              const paths = [...((selected.config.paths as BranchPath[]) || [])];
                              paths[idx] = { ...p, condition: e.target.value };
                              updateConfig("paths", paths);
                            }}
                            placeholder="risk_level IN [high, critical]"
                            style={{
                              display: "block", width: "100%", marginTop: 2, fontSize: "0.72rem",
                              fontFamily: "monospace", border: "1px solid var(--aos-border)",
                              borderRadius: 4, padding: "4px 6px",
                            }}
                          />
                        </label>
                        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                          <label style={{ fontSize: "0.68rem", color: "var(--aos-muted)", display: "flex", alignItems: "center", gap: 4 }}>
                            颜色
                            <input
                              type="color"
                              value={p.color}
                              onChange={(e) => {
                                const paths = [...((selected.config.paths as BranchPath[]) || [])];
                                paths[idx] = { ...p, color: e.target.value };
                                updateConfig("paths", paths);
                              }}
                              style={{ width: 28, height: 20, border: "none", padding: 0, cursor: "pointer" }}
                            />
                          </label>
                          <span style={{ fontSize: "0.65rem", fontFamily: "monospace", color: p.color }}>{p.color}</span>
                        </div>
                      </div>
                    ))}
                    <button
                      type="button"
                      onClick={() => {
                        const paths = [...((selected.config.paths as BranchPath[]) || [])];
                        paths.push({ id: `p${paths.length + 1}`, label: "新路径", condition: "", color: "var(--aos-text-secondary)" });
                        updateConfig("paths", paths);
                      }}
                      style={{
                        fontSize: "0.72rem", padding: "4px 10px", border: "1px dashed var(--aos-border)",
                        borderRadius: 4, background: "transparent", cursor: "pointer", color: "var(--aos-muted)",
                      }}
                    >
                      + 添加路径
                    </button>
                  </div>
                )}

                {/* Handoff 配置：decision / artifacts / open_qs / handoff_to */}
                {selected.kind === "handoff" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                    <div style={{ fontSize: "0.72rem", color: "var(--aos-indigo-600)", background: "var(--aos-indigo-bg)", padding: "6px 8px", borderRadius: 2, border: "1px solid var(--aos-indigo-border)" }}>
                      🔗 Handoff Block · 汇聚多路上下文，输出交接摘要
                    </div>

                    {/* decision */}
                    <label style={{ display: "block", fontSize: "0.75rem", marginBottom: 0, color: "var(--aos-text)", fontWeight: 500 }}>
                      <span style={{ color: "var(--aos-indigo-600)" }}>decision</span> · 决策摘要
                      <textarea
                        value={String(selected.config.decision || "")}
                        onChange={(e) => updateConfig("decision", e.target.value)}
                        rows={3}
                        placeholder="风险分诊结论：中等风险，建议人工复核"
                        style={{
                          display: "block", width: "100%", marginTop: 4, fontSize: "0.78rem",
                          border: "1px solid var(--aos-indigo-border)", borderRadius: 4, padding: "6px 8px",
                          background: "var(--aos-surface-hover)", resize: "vertical",
                        }}
                      />
                    </label>

                    {/* artifacts */}
                    <div>
                      <div style={{ fontSize: "0.75rem", fontWeight: 500, color: "var(--aos-text)", marginBottom: 4 }}>
                        <span style={{ color: "var(--aos-indigo-600)" }}>artifacts</span> · 产物列表
                        <span style={{ marginLeft: 6, fontSize: "0.65rem", color: "var(--aos-muted)" }}>
                          ({((selected.config.artifacts as string[]) || []).length} 项)
                        </span>
                      </div>
                      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        {((selected.config.artifacts as string[]) || []).map((name, i) => (
                          <div key={i} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--aos-blue)", flexShrink: 0 }} />
                            <input
                              value={name}
                              onChange={(e) => {
                                const arr = [...((selected.config.artifacts as string[]) || [])];
                                arr[i] = e.target.value;
                                updateConfig("artifacts", arr);
                              }}
                              style={{
                                flex: 1, fontSize: "0.72rem", fontFamily: "monospace",
                                border: "1px solid var(--aos-border)", borderRadius: 4, padding: "3px 6px",
                              }}
                            />
                            <button
                              type="button"
                              onClick={() => {
                                const arr = ((selected.config.artifacts as string[]) || []).filter((_, j) => j !== i);
                                updateConfig("artifacts", arr);
                              }}
                              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--aos-red)", fontSize: "0.8rem" }}
                            >
                              ×
                            </button>
                          </div>
                        ))}
                        <button
                          type="button"
                          onClick={() => {
                            const arr = [...((selected.config.artifacts as string[]) || []), "new_artifact.json"];
                            updateConfig("artifacts", arr);
                          }}
                          style={{ fontSize: "0.68rem", padding: "2px 8px", border: "1px dashed var(--aos-border)", borderRadius: 4, background: "transparent", cursor: "pointer", color: "var(--aos-muted)", alignSelf: "flex-start" }}
                        >
                          + 产物
                        </button>
                      </div>
                    </div>

                    {/* open_qs */}
                    <div>
                      <div style={{ fontSize: "0.75rem", fontWeight: 500, color: "var(--aos-text)", marginBottom: 4 }}>
                        <span style={{ color: "var(--aos-indigo-600)" }}>open_qs</span> · 待确认项
                        <span style={{ marginLeft: 6, fontSize: "0.65rem", color: "var(--aos-muted)" }}>
                          ({((selected.config.open_qs as string[]) || []).length} 项)
                        </span>
                      </div>
                      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                        {((selected.config.open_qs as string[]) || []).map((q, i) => (
                          <div key={i} style={{ display: "flex", alignItems: "flex-start", gap: 4 }}>
                            <span style={{ fontSize: "0.65rem", color: "var(--aos-amber-600)", fontWeight: 600, marginTop: 3 }}>Q{i + 1}</span>
                            <input
                              value={q}
                              onChange={(e) => {
                                const arr = [...((selected.config.open_qs as string[]) || [])];
                                arr[i] = e.target.value;
                                updateConfig("open_qs", arr);
                              }}
                              style={{
                                flex: 1, fontSize: "0.72rem",
                                border: "1px solid var(--aos-amber-border)", borderRadius: 4, padding: "3px 6px", background: "var(--aos-amber-bg)",
                              }}
                            />
                            <button
                              type="button"
                              onClick={() => {
                                const arr = ((selected.config.open_qs as string[]) || []).filter((_, j) => j !== i);
                                updateConfig("open_qs", arr);
                              }}
                              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--aos-red)", fontSize: "0.8rem" }}
                            >
                              ×
                            </button>
                          </div>
                        ))}
                        <button
                          type="button"
                          onClick={() => {
                            const arr = [...((selected.config.open_qs as string[]) || []), "新的待确认项？"];
                            updateConfig("open_qs", arr);
                          }}
                          style={{ fontSize: "0.68rem", padding: "2px 8px", border: "1px dashed var(--aos-border)", borderRadius: 4, background: "transparent", cursor: "pointer", color: "var(--aos-muted)", alignSelf: "flex-start" }}
                        >
                          + 待确认项
                        </button>
                      </div>
                    </div>

                    {/* handoff_to */}
                    <label style={{ display: "block", fontSize: "0.75rem", fontWeight: 500, color: "var(--aos-text)" }}>
                      <span style={{ color: "var(--aos-indigo-600)" }}>handoff_to</span> · 传递目标
                      <select
                        value={String(selected.config.handoff_to || "draft_inbox")}
                        onChange={(e) => updateConfig("handoff_to", e.target.value)}
                        style={{
                          display: "block", width: "100%", marginTop: 4, fontSize: "0.78rem",
                          border: "1px solid var(--aos-border)", borderRadius: 4, padding: "4px 8px", background: "var(--aos-card)",
                        }}
                      >
                        <option value="risk_agent">风控审批 Agent（risk-approver）</option>
                        <option value="draft_inbox">人工审批台（Draft Inbox）</option>
                        <option value="webhook">外部 Webhook</option>
                      </select>
                    </label>
                  </div>
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
              borderRadius: 2,
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

              {/* 预览模式增强：dryRun 试运行结果 + 统计 + 分支高亮 */}
              {execResults.length > 0 && (
                <div style={{
                  marginBottom: 8, padding: 10, borderRadius: 2,
                  background: dryRun ? "var(--aos-green-bg)" : "var(--aos-accent-light)",
                  border: `1px solid ${dryRun ? "var(--aos-green-border)" : "var(--aos-accent-border)"}`,
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
                    <span style={{ fontSize: "0.7rem", fontWeight: 700, color: dryRun ? "var(--aos-green-700)" : "var(--aos-blue-600)" }}>
                      {dryRun ? "🧪 dryRun 试运行结果" : "🚀 生产执行结果"}
                    </span>
                  </div>
                  {/* 统计：耗时 + Tokens */}
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 6 }}>
                    <span style={{ fontSize: "0.65rem", padding: "2px 6px", borderRadius: 3, background: "rgba(255,255,255,0.7)", color: "var(--aos-text)" }}>
                      ⏱ 耗时 ~{(execResults.length * 0.3).toFixed(2)}s
                    </span>
                    <span style={{ fontSize: "0.65rem", padding: "2px 6px", borderRadius: 3, background: "rgba(255,255,255,0.7)", color: "var(--aos-text)" }}>
                      🎯 Tokens 入 {execResults.length * 284} / 出 {execResults.length * 47}
                    </span>
                    <span style={{ fontSize: "0.65rem", padding: "2px 6px", borderRadius: 3, background: "rgba(255,255,255,0.7)", color: "var(--aos-text)" }}>
                      📦 {execResults.length} 步
                    </span>
                  </div>
                  {/* 分支路径高亮 */}
                  {blocks.some((b) => b.kind === "branch") && (() => {
                    const branchBlock = blocks.find((b) => b.kind === "branch");
                    const paths = (branchBlock?.config.paths as BranchPath[]) || [];
                    const activeIdx = 0; // dryRun 默认命中第一条路径
                    return (
                      <div style={{ display: "grid", gridTemplateColumns: `repeat(${Math.min(paths.length, 2)}), 1fr)`, gap: 4, marginTop: 4 }}>
                        {paths.slice(0, 2).map((p, pi) => (
                          <div key={p.id} style={{
                            padding: "3px 6px", borderRadius: 4, fontSize: "0.62rem",
                            border: pi === activeIdx ? `2px solid ${p.color}` : `1px solid ${p.color}40`,
                            background: pi === activeIdx ? `${p.color}15` : "transparent",
                            fontWeight: pi === activeIdx ? 700 : 400,
                            color: pi === activeIdx ? p.color : "var(--aos-text-tertiary)",
                          }}>
                            {pi === activeIdx ? "▶ " : "  "}{p.label}
                          </div>
                        ))}
                      </div>
                    );
                  })()}
                </div>
              )}

              {/* Latest results */}
              {execResults.length > 0 && (
                <details open style={{ marginBottom: 8 }}>
                  <summary style={{ fontSize: "0.75rem", cursor: "pointer", color: "var(--aos-muted)" }}>
                    CoT 推理链（{execResults.length} 步）
                  </summary>
                  <div style={{ marginTop: 6 }}>
                    {execResults.map((r, i) => {
                      const blk = blocks[i];
                      const isBranch = blk?.kind === "branch";
                      const isHandoff = blk?.kind === "handoff";
                      return (
                      <div key={r.block_id}
                        style={{
                          borderLeft: `3px solid ${KIND_COLORS[blk?.kind || "input"] || "var(--aos-text-secondary)"}`,
                          padding: "4px 8px",
                          marginBottom: 4,
                          fontSize: "0.72rem",
                          background: isHandoff ? "var(--aos-indigo-bg)" : isBranch ? "var(--aos-red-bg)" : "var(--aos-card)",
                          borderRadius: "0 4px 4px 0",
                        }}>
                        <strong>Step {i + 1}</strong>{" "}
                        {isBranch && <span style={{ color: "var(--aos-red)", fontSize: "0.62rem" }}>🔀 分支求值</span>}
                        {isHandoff && <span style={{ color: "var(--aos-indigo-600)", fontSize: "0.62rem" }}>🔗 汇聚输出</span>}
                        {r.cot.map((line, j) => (
                          <div key={j} style={{ color: "var(--aos-text)", marginTop: 2 }}>{line}</div>
                        ))}
                      </div>
                      );
                    })}
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
                    background: "var(--aos-text)", color: "var(--aos-text-tertiary)", borderRadius: 2, lineHeight: 1.4,
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
                      <span style={{ color: h.success ? "var(--aos-green)" : "var(--aos-red)" }}>{h.success ? "✓" : "✗"}</span>
                      <span style={{ color: "var(--aos-muted)", fontFamily: "monospace" }}>{h.timestamp}</span>
                      <span style={{ color: "var(--aos-text)" }}>{h.blockCount} blocks</span>
                      <span style={{ fontSize: "0.65rem", padding: "1px 4px", borderRadius: 3,
                        background: h.dryRun ? "var(--aos-amber-bg)" : "var(--aos-green-bg)", color: h.dryRun ? "var(--aos-amber-700)" : "var(--aos-green-700)" }}>
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
              borderRadius: 2,
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
                    border: `1px solid ${automationTriggers[t.kind] ? "var(--aos-blue)" : "var(--aos-border)"}`,
                    borderRadius: 2, cursor: "pointer", fontSize: "0.78rem",
                    background: automationTriggers[t.kind] ? "var(--aos-blue)10" : "transparent",
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
              <div style={{ marginTop: 12, padding: "8px 10px", background: "var(--aos-amber-bg)", borderRadius: 2, fontSize: "0.7rem", color: "var(--aos-amber-700)" }}>
                💡 已启用 {Object.values(automationTriggers).filter(Boolean).length} 个触发器。变更将在下次执行时生效。
              </div>
            </div>
          )}
        </div>
      </div>
    </PageChrome>
  );
}
