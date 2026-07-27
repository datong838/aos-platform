import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";

type TabId = "edit" | "auto" | "history";
type BlockKind =
  | "input"
  | "create_variable"
  | "get_attribute"
  | "use_llm"
  | "transform"
  | "apply_action"
  | "write_back"
  | "execute"
  | "branch"
  | "handoff";

type BlockNode = {
  id: string;
  kind: BlockKind;
  title: string;
  subtitle?: string;
  config: Record<string, unknown>;
};

type BranchPath = { label: string; condition: string; nextBlockId?: string; tone: "red" | "green" };

type RunResult = {
  runId: string;
  status: "success" | "failed" | "running";
  input: string;
  risk?: string;
  reason?: string;
  duration: string;
  tokensIn: number;
  tokensOut: number;
  amount?: string;
  currency?: string;
};

type HistoryItem = {
  id: string;
  status: "success" | "failed";
  duration: string;
  input: string;
  result: string;
  resultTone: "green" | "red";
};

const BLOCK_TOOLBAR: { kind: BlockKind; label: string; tone?: "yellow" | "green" }[] = [
  { kind: "create_variable", label: "+ 创建变量" },
  { kind: "get_attribute", label: "+ 获取属性" },
  { kind: "use_llm", label: "+ 使用 LLM", tone: "yellow" },
  { kind: "transform", label: "+ 数据变换" },
  { kind: "apply_action", label: "+ 应用动作" },
  { kind: "write_back", label: "+ 写回", tone: "green" },
  { kind: "execute", label: "+ 执行" },
  { kind: "branch", label: "+ 分支" },
];

const KIND_META: Record<BlockKind, { label: string; color: string; bg: string; border: string }> = {
  input: { label: "输入", color: "var(--aos-blue-600)", bg: "var(--aos-accent-light)", border: "var(--aos-accent-border)" },
  create_variable: { label: "创建变量", color: "var(--color-info)", bg: "var(--aos-accent-light)", border: "var(--aos-accent-border)" },
  get_attribute: { label: "获取对象属性", color: "var(--aos-purple-600)", bg: "var(--aos-indigo-bg)", border: "var(--aos-indigo-border)" },
  use_llm: { label: "使用 LLM", color: "var(--aos-amber-600)", bg: "var(--aos-amber-bg)", border: "var(--aos-amber-border)" },
  transform: { label: "数据变换", color: "var(--color-info)", bg: "var(--aos-accent-light)", border: "var(--aos-accent-border)" },
  apply_action: { label: "应用动作", color: "var(--aos-red)", bg: "var(--aos-red-bg)", border: "var(--aos-red-border)" },
  write_back: { label: "写回", color: "var(--aos-green-600)", bg: "var(--aos-green-bg)", border: "var(--aos-green-border)" },
  execute: { label: "执行", color: "var(--aos-indigo-600)", bg: "var(--aos-indigo-bg)", border: "var(--aos-indigo-border)" },
  branch: { label: "分支", color: "var(--aos-red)", bg: "var(--aos-red-bg)", border: "var(--aos-red-border)" },
  handoff: { label: "汇聚 · Handoff 上下文", color: "var(--aos-indigo-600)", bg: "var(--aos-indigo-bg)", border: "var(--aos-indigo-border)" },
};

const DEFAULT_BLOCKS: BlockNode[] = [
  { id: "b1", kind: "input", title: "输入", subtitle: "order : Object · Order", config: { source: "Workshop 选中行" } },
  {
    id: "b2",
    kind: "get_attribute",
    title: "获取对象属性",
    subtitle: "order.status · order.amount · order.currency · order.region",
    config: { sourceObject: "order", attributes: ["status", "amount", "currency", "region"] },
  },
  {
    id: "b3",
    kind: "use_llm",
    title: "使用 LLM · 风险评估",
    subtitle: "",
    config: {
      model: "私有-中",
      temperature: 0.3,
      maxTokens: 512,
      prompt:
        "你是订单风险评估助手。分析订单风险等级（low/medium/high/critical）。\n高风险因子：金额 > $500、跨境发货、新客首单、频繁退款的会员。",
      outputs: ["risk_level", "reason"],
    },
  },
];

const BRANCH_PATHS: BranchPath[] = [
  { label: "高风险", condition: "risk_level IN [high, critical]", tone: "red" },
  { label: "低风险", condition: "risk_level IN [low, medium]", tone: "green" },
];

const HISTORY_DATA: HistoryItem[] = [
  { id: "#1047", status: "success", duration: "1.2s", input: "ORD-0721-001", result: "低", resultTone: "green" },
  { id: "#1046", status: "success", duration: "1.8s", input: "ORD-0721-002", result: "高", resultTone: "red" },
  { id: "#1045", status: "success", duration: "1.1s", input: "ORD-0721-003", result: "低", resultTone: "green" },
  { id: "#1044", status: "success", duration: "1.5s", input: "ORD-0721-004", result: "中", resultTone: "green" },
  { id: "#1043", status: "failed", duration: "3.2s", input: "ORD-0721-005", result: "超时", resultTone: "red" },
];

const ARTIFACTS = [
  { name: "risk_assessment.json", type: "LLM 输出", color: "var(--aos-purple-600)" },
  { name: "order_snapshot.diff", type: "字段变更", color: "var(--aos-blue)" },
  { name: "escalation_ticket.log", type: "Action 产物", color: "var(--aos-red)" },
];

export function LogicPage() {
  const [tab, setTab] = useState<TabId>("edit");
  const [blocks, setBlocks] = useState<BlockNode[]>(DEFAULT_BLOCKS);
  const [selectedId, setSelectedId] = useState<string>("b3");
  const hasBranch = true;
  const hasHandoff = true;
  const [runResult, setRunResult] = useState<RunResult | null>({
    runId: "#1047",
    status: "success",
    input: "ORD-0721-001",
    risk: "低",
    reason: "金额适中，稳定客户",
    duration: "1,240ms",
    tokensIn: 284,
    tokensOut: 47,
    amount: "$129.99",
    currency: "USD",
  });
  const [running, setRunning] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [llmPrompt, setLlmPrompt] = useState(
    "你是订单风险评估助手。分析订单风险等级（low/medium/high/critical）。\n高风险因子：金额 > $500、跨境发货、新客首单、频繁退款的会员。",
  );
  const objectId = "ORD-0721-001";

  const selectedBlock = useMemo(() => blocks.find((b) => b.id === selectedId), [blocks, selectedId]);

  async function runLogic() {
    setRunning(true);
    setErr(null);
    try {
      const res = await apiPost<{
        duration_ms?: number;
        proposed_edits?: unknown[];
        production_written?: boolean;
      }>("/v1/aip/logic/run", {
        dryRun: true,
        graph: { nodes: blocks.map((b) => ({ id: b.id, kind: b.kind })) },
      });
      setRunResult({
        runId: "#" + Math.floor(1000 + Math.random() * 9000),
        status: "success",
        input: objectId,
        risk: "低",
        reason: "金额适中，稳定客户",
        duration: `${res.duration_ms || 1240}ms`,
        tokensIn: 284,
        tokensOut: 47,
        amount: "$129.99",
        currency: "USD",
      });
    } catch (e) {
      setErr(String((e as Error).message || e));
    } finally {
      setRunning(false);
    }
  }

  function addBlock(kind: BlockKind) {
    const meta = KIND_META[kind];
    const id = `${kind}-${Date.now().toString(36)}`;
    const newBlock: BlockNode = {
      id,
      kind,
      title: meta.label,
      config: {},
    };
    setBlocks((prev) => [...prev, newBlock]);
    setSelectedId(id);
  }

  return (
    <PageChrome title="AIP 逻辑画布" lede="Block 式编排 · 8 种块类型 · Handoff 上下文交接 · dryRun 不落库">
      <div
        style={{
          margin: "-20px -20px -24px",
          display: "flex",
          flexDirection: "column",
          minHeight: "calc(100vh - 140px)",
        }}
      >
        {/* Tab 导航 */}
        <div
          style={{
            borderBottom: "1px solid var(--aos-border)",
            background: "var(--aos-surface)",
            padding: "0 20px",
            display: "flex",
            alignItems: "center",
            gap: 4,
            flexShrink: 0,
          }}
        >
          {([
            { id: "edit", label: "编辑" },
            { id: "auto", label: "自动化" },
            { id: "history", label: "运行历史" },
          ] as const).map((t) => {
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                style={{
                  padding: "10px 16px",
                  fontSize: 13,
                  fontWeight: active ? 500 : 400,
                  color: active ? "var(--aos-indigo-600)" : "var(--aos-text-secondary)",
                  background: "none",
                  border: "none",
                  borderBottom: active ? "2px solid var(--aos-indigo-600)" : "2px solid transparent",
                  cursor: "pointer",
                }}
              >
                {t.label}
              </button>
            );
          })}
        </div>

        {/* 编辑 Tab */}
        {tab === "edit" && (
          <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
            {/* Block 工具栏 */}
            <div
              style={{
                padding: "8px 20px",
                borderBottom: "1px solid var(--aos-border)",
                display: "flex",
                flexWrap: "wrap",
                gap: 6,
                fontSize: 10,
                flexShrink: 0,
              }}
            >
              <span style={{ color: "var(--aos-text-tertiary)", alignSelf: "center", marginRight: 4 }}>块:</span>
              {BLOCK_TOOLBAR.map((b) => {
                const isYellow = b.tone === "yellow";
                const isGreen = b.tone === "green";
                return (
                  <button
                    key={b.kind}
                    type="button"
                    onClick={() => addBlock(b.kind)}
                    style={{
                      padding: "2.5px 10px",
                      fontSize: 10,
                      borderRadius: 2,
                      border: `1px solid ${isYellow ? "var(--aos-amber-border)" : isGreen ? "var(--aos-green-border)" : "var(--aos-border)"}`,
                      background: isYellow ? "var(--aos-amber-bg)" : isGreen ? "var(--aos-green-bg)" : "var(--aos-surface)",
                      color: isYellow ? "var(--aos-amber-600)" : isGreen ? "var(--aos-green-600)" : "var(--aos-text-secondary)",
                      cursor: "pointer",
                    }}
                  >
                    {b.label}
                  </button>
                );
              })}
            </div>

            {/* 三栏编排 */}
            <div
              style={{
                flex: 1,
                display: "grid",
                gridTemplateColumns: "5fr 4fr 3fr",
                minHeight: 0,
                overflow: "hidden",
              }}
            >
              {/* ① 编排区 */}
              <div
                style={{
                  borderRight: "1px solid var(--aos-border)",
                  overflowY: "auto",
                  padding: 16,
                  background:
                    "radial-gradient(circle, var(--aos-border) 1px, transparent 1px) 0 0 / 20px 20px, var(--aos-surface-hover)",
                }}
              >
                <div
                  style={{
                    fontSize: 10,
                    color: "var(--aos-text-tertiary)",
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    marginBottom: 8,
                  }}
                >
                  ① 编排 · 块链
                </div>

                {blocks.map((block, idx) => {
                  const meta = KIND_META[block.kind];
                  const selected = block.id === selectedId;
                  return (
                    <div key={block.id}>
                      <div
                        onClick={() => setSelectedId(block.id)}
                        style={{
                          borderRadius: 2,
                          border: `1px solid ${selected ? meta.color : meta.border}`,
                          background: meta.bg,
                          padding: 12,
                          fontSize: 12,
                          cursor: "pointer",
                          boxShadow: selected ? `0 0 0 3px ${meta.color}33` : "none",
                          transition: "all 0.15s",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                          }}
                        >
                          <span style={{ color: meta.color, fontWeight: 500 }}>{block.title}</span>
                          <span style={{ fontSize: 9, color: "var(--aos-text-tertiary)" }}>块 #{idx + 1}</span>
                        </div>
                        {block.subtitle && (
                          <div style={{ fontFamily: "monospace", color: "var(--aos-text-secondary)", marginTop: 4, fontSize: 11 }}>
                            {block.subtitle}
                          </div>
                        )}
                        {block.kind === "use_llm" && (
                          <>
                            <div
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: 8,
                                marginTop: 6,
                                fontSize: 10,
                                color: "var(--aos-text-secondary)",
                              }}
                            >
                              <span>模型: 私有-中</span>
                              <span>Temp: 0.3</span>
                              <span>Max: 512</span>
                            </div>
                            <div
                              style={{
                                marginTop: 8,
                                color: "var(--aos-text-secondary)",
                                lineHeight: 1.6,
                                fontSize: 11,
                                background: "var(--aos-gray-100)",
                                borderRadius: 4,
                                padding: 8,
                                border: "1px solid var(--aos-border)",
                              }}
                            >
                              {llmPrompt.split("\n")[0]}
                              <br />
                              高风险因子：金额 {">"} $500、跨境发货…
                            </div>
                            <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 8 }}>
                              <span
                                style={{
                                  padding: "2px 6px",
                                  borderRadius: 4,
                                  background: "var(--aos-green-bg)",
                                  border: "1px solid var(--aos-green-border)",
                                  color: "var(--aos-green-600)",
                                  fontSize: 9,
                                }}
                              >
                                输出: risk_level
                              </span>
                              <span
                                style={{
                                  padding: "2px 6px",
                                  borderRadius: 4,
                                  background: "var(--aos-green-bg)",
                                  border: "1px solid var(--aos-green-border)",
                                  color: "var(--aos-green-600)",
                                  fontSize: 9,
                                }}
                              >
                                输出: reason
                              </span>
                            </div>
                          </>
                        )}
                      </div>
                      {idx < blocks.length - 1 && (
                        <div style={{ textAlign: "center", color: "var(--aos-text-tertiary)", fontSize: 10, padding: "4px 0" }}>
                          ↓
                        </div>
                      )}
                    </div>
                  );
                })}

                {/* 分支双路 */}
                {hasBranch && (
                  <>
                    <div style={{ textAlign: "center", color: "var(--aos-text-tertiary)", fontSize: 10, padding: "4px 0" }}>↓ ↓</div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                      {BRANCH_PATHS.map((p, i) => (
                        <div
                          key={i}
                          onClick={() => setSelectedId(`branch-${i}`)}
                          style={{
                            borderRadius: 2,
                            border: `1px solid ${p.tone === "red" ? "var(--aos-red-border)" : "var(--aos-green-border)"}`,
                            background: p.tone === "red" ? "var(--aos-red-bg)" : "var(--aos-green-bg)",
                            padding: 12,
                            fontSize: 12,
                            cursor: "pointer",
                          }}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                            }}
                          >
                            <span
                              style={{
                                color: p.tone === "red" ? "var(--aos-red)" : "var(--aos-green-600)",
                                fontWeight: 500,
                              }}
                            >
                              分支 · {p.label}
                            </span>
                            <span style={{ fontSize: 9, color: "var(--aos-text-tertiary)" }}>#{i === 0 ? "4A" : "4B"}</span>
                          </div>
                          <div
                            style={{
                              fontFamily: "monospace",
                              color: "var(--aos-text-secondary)",
                              marginTop: 4,
                              fontSize: 11,
                            }}
                          >
                            {p.condition}
                          </div>
                          <div
                            style={{
                              marginTop: 8,
                              fontSize: 10,
                              color: p.tone === "red" ? "var(--aos-red)" : "var(--aos-green-600)",
                            }}
                          >
                            → {p.tone === "red" ? "Apply Action: escalate_to_supervisor" : "写回：update_status → shipped"}
                          </div>
                        </div>
                      ))}
                    </div>
                    <div style={{ textAlign: "center", color: "var(--aos-text-tertiary)", fontSize: 10, padding: "4px 0" }}>
                      ↓ ↓ 汇聚
                    </div>
                  </>
                )}

                {/* Handoff 汇聚节点 */}
                {hasHandoff && (
                  <div
                    onClick={() => setSelectedId("handoff")}
                    style={{
                      borderRadius: 2,
                      border: "2px solid var(--aos-indigo-border)",
                      background: "var(--aos-indigo-bg)",
                      padding: 12,
                      fontSize: 12,
                      cursor: "pointer",
                      boxShadow: selectedId === "handoff" ? "0 0 0 3px var(--aos-indigo)55" : "none",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--aos-indigo-600)" strokeWidth="2">
                          <path d="M8 7h8M8 12h8M8 17h8" strokeLinecap="round" />
                          <circle cx="5" cy="7" r="1.5" fill="currentColor" stroke="none" />
                          <circle cx="5" cy="12" r="1.5" fill="currentColor" stroke="none" />
                          <circle cx="5" cy="17" r="1.5" fill="currentColor" stroke="none" />
                        </svg>
                        <span style={{ color: "var(--aos-indigo-600)", fontWeight: 500 }}>汇聚 · Handoff 上下文</span>
                      </div>
                      <span style={{ fontSize: 9, color: "var(--aos-text-tertiary)" }}>块 #5</span>
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 6, marginTop: 8 }}>
                      <div
                        style={{
                          borderRadius: 4,
                          background: "rgba(255,255,255,0.6)",
                          border: "1px solid var(--aos-indigo-border)",
                          padding: "6px 8px",
                        }}
                      >
                        <div style={{ fontSize: 9, color: "var(--aos-text-tertiary)" }}>decision</div>
                        <div style={{ fontSize: 10, color: "var(--aos-text)", fontWeight: 500, marginTop: 1 }}>
                          风险分诊结论
                        </div>
                      </div>
                      <div
                        style={{
                          borderRadius: 4,
                          background: "rgba(255,255,255,0.6)",
                          border: "1px solid var(--aos-indigo-border)",
                          padding: "6px 8px",
                        }}
                      >
                        <div style={{ fontSize: 9, color: "var(--aos-text-tertiary)" }}>artifacts</div>
                        <div style={{ fontSize: 10, color: "var(--aos-text)", fontWeight: 500, marginTop: 1 }}>3 个产物</div>
                      </div>
                      <div
                        style={{
                          borderRadius: 4,
                          background: "rgba(255,255,255,0.6)",
                          border: "1px solid var(--aos-indigo-border)",
                          padding: "6px 8px",
                        }}
                      >
                        <div style={{ fontSize: 9, color: "var(--aos-text-tertiary)" }}>open_qs</div>
                        <div style={{ fontSize: 10, color: "var(--aos-text)", fontWeight: 500, marginTop: 1 }}>
                          1 个待确认
                        </div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* ② 配置区 */}
              <div style={{ borderRight: "1px solid var(--aos-border)", overflowY: "auto", padding: 16 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div
                    style={{
                      fontSize: 10,
                      color: "var(--aos-text-tertiary)",
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                    }}
                  >
                    ② 配置 · {selectedId === "handoff" ? "汇聚节点属性" : selectedBlock ? KIND_META[selectedBlock.kind].label : "选中块"}
                  </div>
                  <span
                    style={{
                      padding: "2px 8px",
                      borderRadius: 4,
                      fontSize: 9,
                      background: "var(--aos-indigo-bg)",
                      color: "var(--aos-indigo-600)",
                      fontWeight: 500,
                    }}
                  >
                    {selectedId === "handoff" ? "Handoff 上下文" : selectedBlock?.kind || "—"}
                  </span>
                </div>

                {/* Handoff 配置 */}
                {selectedId === "handoff" && (
                  <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 16 }}>
                    {/* 决策摘要 */}
                    <div
                      style={{
                        borderRadius: 2,
                        border: "1px solid var(--aos-border)",
                        background: "var(--aos-surface)",
                        padding: 12,
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--aos-text-secondary)" strokeWidth="1.5">
                          <path d="M9 12l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
                          <circle cx="12" cy="12" r="10" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                        <label style={{ fontSize: 11, color: "var(--aos-text-secondary)", fontWeight: 500 }}>
                          decision_summary · 决策摘要
                        </label>
                        <span style={{ fontSize: 9, color: "var(--aos-text-tertiary)", marginLeft: "auto" }}>必填</span>
                      </div>
                      <div
                        style={{
                          fontSize: 12,
                          color: "var(--aos-text)",
                          background: "rgba(255,255,255,0.6)",
                          borderRadius: 4,
                          padding: 8,
                          border: "1px solid var(--aos-border)",
                          lineHeight: 1.6,
                        }}
                      >
                        订单 <span style={{ fontFamily: "monospace" }}>ORD-0721-002</span> 风险等级判定为{" "}
                        <span style={{ color: "var(--aos-red)", fontWeight: 500 }}>高</span>
                        ，触发升级审批。主要风险因子：金额 $1,840 {" > "} 阈值 $500，跨境发货至东南亚，新客首单。
                      </div>
                    </div>

                    {/* 产物列表 */}
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--aos-text-secondary)" strokeWidth="1.5">
                          <path d="M6 2h9l5 5v15a1 1 0 01-1 1H6a1 1 0 01-1-1V3a1 1 0 011-1z" strokeLinejoin="round" />
                          <path d="M14 2v6h6" strokeLinejoin="round" />
                        </svg>
                        <label style={{ fontSize: 11, color: "var(--aos-text-secondary)", fontWeight: 500 }}>
                          artifacts · 产物列表
                        </label>
                        <span
                          style={{
                            padding: "0 6px",
                            borderRadius: 4,
                            fontSize: 9,
                            background: "var(--aos-gray-100)",
                            color: "var(--aos-text-secondary)",
                            marginLeft: "auto",
                          }}
                        >
                          3 项
                        </span>
                      </div>
                      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                        {ARTIFACTS.map((a, i) => (
                          <div
                            key={i}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: 8,
                              borderRadius: 2,
                              background: "var(--aos-surface)",
                              border: "1px solid var(--aos-border)",
                              padding: "6px 10px",
                            }}
                          >
                            <span
                              style={{
                                width: 6,
                                height: 6,
                                borderRadius: "50%",
                                background: a.color,
                                flexShrink: 0,
                              }}
                            />
                            <span
                              style={{
                                fontFamily: "monospace",
                                fontSize: 11,
                                color: "var(--aos-text)",
                                flex: 1,
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                              }}
                            >
                              {a.name}
                            </span>
                            <span style={{ fontSize: 9, color: "var(--aos-text-tertiary)" }}>{a.type}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* 开放问题 */}
                    <div>
                      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--aos-text-secondary)" strokeWidth="1.5">
                          <circle cx="12" cy="12" r="9" />
                          <path
                            d="M9.5 9a2.5 2.5 0 015 0c0 1.5-2.5 2-2.5 3.5"
                            strokeLinecap="round"
                          />
                          <path d="M12 17v.5" strokeLinecap="round" />
                        </svg>
                        <label style={{ fontSize: 11, color: "var(--aos-text-secondary)", fontWeight: 500 }}>
                          open_questions · 待确认项
                        </label>
                        <span
                          style={{
                            padding: "0 6px",
                            borderRadius: 4,
                            fontSize: 9,
                            background: "var(--aos-amber-bg)",
                            color: "var(--aos-amber-600)",
                            marginLeft: "auto",
                          }}
                        >
                          1 项
                        </span>
                      </div>
                      <div
                        style={{
                          borderRadius: 2,
                          background: "var(--aos-amber-bg)",
                          border: "1px solid var(--aos-amber-border)",
                          padding: 10,
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                          <span style={{ fontSize: 10, color: "var(--aos-amber-600)", fontWeight: 500, flexShrink: 0 }}>Q1</span>
                          <div style={{ fontSize: 11, color: "var(--aos-text-secondary)", lineHeight: 1.5 }}>
                            客户历史退款率 22% 是否需要人工复核？建议由风控主管确认后再执行 escalate。
                          </div>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 8 }}>
                          <span style={{ fontSize: 9, color: "var(--aos-text-tertiary)" }}>下一步：</span>
                          <span style={{ fontSize: 10, color: "var(--aos-indigo-600)" }}>→ 传递给风控审批 Agent</span>
                        </div>
                      </div>
                    </div>

                    {/* 传递目标 */}
                    <div style={{ paddingTop: 8, borderTop: "1px solid var(--aos-gray-100)" }}>
                      <label style={{ display: "block", fontSize: 11, color: "var(--aos-text-secondary)", marginBottom: 8, fontWeight: 500 }}>
                        handoff_to · 传递目标
                      </label>
                      <select
                        style={{
                          width: "100%",
                          padding: "6px 12px",
                          fontSize: 12,
                          borderRadius: 2,
                          border: "1px solid var(--aos-border)",
                          background: "var(--aos-surface)",
                          color: "var(--aos-text)",
                        }}
                      >
                        <option>风控审批 Agent（risk-approver）</option>
                        <option>人工审批台（Draft Inbox）</option>
                        <option>外部 Webhook</option>
                      </select>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8 }}>
                        <input type="checkbox" defaultChecked style={{ width: 14, height: 14 }} />
                        <span style={{ fontSize: 10, color: "var(--aos-text-secondary)" }}>包含完整运行 trace（Token 用量 / 延迟）</span>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
                        <input type="checkbox" defaultChecked style={{ width: 14, height: 14 }} />
                        <span style={{ fontSize: 10, color: "var(--aos-text-secondary)" }}>自动生成交接摘要（LLM 总结）</span>
                      </div>
                    </div>
                  </div>
                )}

                {/* LLM 块配置 */}
                {selectedBlock?.kind === "use_llm" && (
                  <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 16 }}>
                    <div>
                      <label style={{ display: "block", fontSize: 11, color: "var(--aos-text-secondary)", marginBottom: 6, fontWeight: 500 }}>
                        模型
                      </label>
                      <select style={selectStyle}>
                        <option>私有-强 (Claude Opus)</option>
                        <option selected>私有-中 (GPT-4o)</option>
                        <option>私有-轻 (GPT-4o-mini)</option>
                        <option>开源-Llama3-70B</option>
                      </select>
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: 11, color: "var(--aos-text-secondary)", marginBottom: 6, fontWeight: 500 }}>
                        System Prompt
                      </label>
                      <textarea
                        value={llmPrompt}
                        onChange={(e) => setLlmPrompt(e.target.value)}
                        rows={6}
                        style={{
                          width: "100%",
                          padding: "8px 10px",
                          fontSize: 11,
                          fontFamily: "monospace",
                          borderRadius: 2,
                          border: "1px solid var(--aos-border)",
                          background: "var(--aos-surface)",
                          resize: "vertical",
                        }}
                      />
                    </div>
                    <div style={{ display: "flex", gap: 12 }}>
                      <div style={{ flex: 1 }}>
                        <label style={{ display: "block", fontSize: 11, color: "var(--aos-text-secondary)", marginBottom: 6, fontWeight: 500 }}>
                          Temperature
                        </label>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <input type="range" min="0" max="1" step="0.1" defaultValue="0.3" style={{ flex: 1 }} />
                          <span style={{ fontSize: 11, color: "var(--aos-text-secondary)", minWidth: 24 }}>0.3</span>
                        </div>
                      </div>
                      <div style={{ flex: 1 }}>
                        <label style={{ display: "block", fontSize: 11, color: "var(--aos-text-secondary)", marginBottom: 6, fontWeight: 500 }}>
                          Max Tokens
                        </label>
                        <input
                          type="number"
                          defaultValue="512"
                          style={{
                            width: "100%",
                            padding: "6px 8px",
                            fontSize: 12,
                            borderRadius: 2,
                            border: "1px solid var(--aos-border)",
                            background: "var(--aos-surface)",
                          }}
                        />
                      </div>
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: 11, color: "var(--aos-text-secondary)", marginBottom: 6, fontWeight: 500 }}>
                        输出变量
                      </label>
                      <input
                        type="text"
                        defaultValue="risk_assessment"
                        placeholder="如：risk_assessment"
                        style={{
                          width: "100%",
                          padding: "6px 10px",
                          fontSize: 12,
                          borderRadius: 2,
                          border: "1px solid var(--aos-border)",
                          background: "var(--aos-surface)",
                        }}
                      />
                    </div>
                    <div
                      style={{
                        padding: "6px 10px",
                        background: "var(--aos-accent-light)",
                        border: "1px solid var(--aos-accent-border)",
                        borderRadius: 2,
                        fontSize: 10,
                        color: "var(--aos-blue-600)",
                        fontFamily: "monospace",
                      }}
                    >
                      🔧 LogicEngine.use_llm → ModelRouter.route() → L3 RegisteredModel.call()
                    </div>
                  </div>
                )}

                {/* 通用块配置（其他类型简略显示）*/}
                {selectedBlock && selectedBlock.kind !== "use_llm" && selectedId !== "handoff" && (
                  <div style={{ marginTop: 12 }}>
                    <div
                      style={{
                        padding: 12,
                        borderRadius: 2,
                        border: "1px solid var(--aos-border)",
                        background: "var(--aos-surface)",
                        fontSize: 12,
                        color: "var(--aos-text-secondary)",
                      }}
                    >
                      选中「{KIND_META[selectedBlock.kind].label}」块的属性配置区。
                      <br />
                      详细字段与视觉稿 {selectedBlock.kind === "input" ? "输入源选择" : "配置表单"} 一致。
                    </div>
                  </div>
                )}
              </div>

              {/* ③ 预览区 */}
              <div style={{ overflowY: "auto", padding: 16 }}>
                <div
                  style={{
                    fontSize: 10,
                    color: "var(--aos-text-tertiary)",
                    textTransform: "uppercase",
                    letterSpacing: "0.05em",
                    marginBottom: 12,
                  }}
                >
                  ③ 预览 · 单次运行
                </div>

                {err && (
                  <div
                    style={{
                      background: "var(--aos-red-bg)",
                      border: "1px solid var(--aos-red-border)",
                      borderRadius: 2,
                      padding: 12,
                      marginBottom: 12,
                      fontSize: 12,
                      color: "var(--aos-red)",
                    }}
                  >
                    {err}
                  </div>
                )}

                {runResult && (
                  <div
                    style={{
                      borderRadius: 2,
                      border: "1px solid var(--aos-green-border)",
                      background: "var(--aos-green-bg)",
                      padding: 12,
                      fontSize: 12,
                    }}
                  >
                    <div style={{ color: "var(--aos-green-600)", fontWeight: 500, marginBottom: 8 }}>
                      运行 {runResult.runId} · 16:42
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 11 }}>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span style={{ color: "var(--aos-text-secondary)" }}>输入：</span>
                        <span style={{ fontFamily: "monospace", color: "var(--aos-text-secondary)" }}>{runResult.input}</span>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span style={{ color: "var(--aos-text-secondary)" }}>状态：</span>
                        <span style={{ color: "var(--aos-text-secondary)" }}>
                          已完成 · {runResult.amount} · {runResult.currency}
                        </span>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span style={{ color: "var(--aos-text-secondary)" }}>风险：</span>
                        <span style={{ color: "var(--aos-green-600)", fontWeight: 500 }}>{runResult.risk}</span>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span style={{ color: "var(--aos-text-secondary)" }}>原因：</span>
                        <span style={{ color: "var(--aos-text-secondary)" }}>{runResult.reason}</span>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span style={{ color: "var(--aos-text-secondary)" }}>延迟：</span>
                        <span style={{ color: "var(--aos-text-secondary)" }}>{runResult.duration}</span>
                      </div>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span style={{ color: "var(--aos-text-secondary)" }}>Token：</span>
                        <span style={{ color: "var(--aos-text-secondary)" }}>入 {runResult.tokensIn} · 出 {runResult.tokensOut}</span>
                      </div>
                    </div>
                  </div>
                )}

                <button
                  type="button"
                  onClick={() => void runLogic()}
                  disabled={running}
                  style={{
                    width: "100%",
                    marginTop: 12,
                    padding: "8px 16px",
                    fontSize: 12,
                    borderRadius: 2,
                    border: "1px solid var(--aos-amber-border)",
                    background: "var(--aos-amber-bg)",
                    color: "var(--aos-amber-600)",
                    cursor: running ? "wait" : "pointer",
                  }}
                >
                  {running ? "运行中…" : "重新运行"}
                </button>

                <div style={{ marginTop: 16, paddingTop: 12, borderTop: "1px solid var(--aos-gray-100)" }}>
                  <div style={{ fontSize: 11, color: "var(--aos-text-secondary)", fontWeight: 500, marginBottom: 8 }}>
                    跳转
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    <Link
                      to="/aip/drafts"
                      style={{ fontSize: 12, color: "var(--aos-indigo-600)", textDecoration: "none" }}
                    >
                      Draft 审批台 →
                    </Link>
                    <Link
                      to="/aip/observability"
                      style={{ fontSize: 12, color: "var(--aos-indigo-600)", textDecoration: "none" }}
                    >
                      可观测性 →
                    </Link>
                    <Link
                      to="/aip/tools"
                      style={{ fontSize: 12, color: "var(--aos-indigo-600)", textDecoration: "none" }}
                    >
                      工具面板 →
                    </Link>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 自动化 Tab */}
        {tab === "auto" && (
          <div style={{ flex: 1, overflowY: "auto", padding: 24 }}>
            <div style={{ maxWidth: 768, margin: "0 auto" }}>
              <h2 style={{ fontSize: 18, fontWeight: 600, color: "var(--aos-text)", margin: "0 0 4px" }}>
                自动化 Uses
              </h2>
              <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", margin: "0 0 16px" }}>
                绑定调度或事件触发 · 创建 Automation 任务
              </p>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 12 }}>
                <div
                  style={{
                    borderRadius: 2,
                    border: "1px solid var(--aos-border)",
                    background: "var(--aos-surface)",
                    padding: 16,
                  }}
                >
                  <div style={{ fontSize: 12, color: "var(--aos-green-600)", fontWeight: 500 }}>每 15 分钟</div>
                  <p style={{ fontSize: 11, color: "var(--aos-text-secondary)", margin: "4px 0 0", lineHeight: 1.5 }}>
                    对所有 pending 订单执行风险评估
                  </p>
                </div>
                <div
                  style={{
                    borderRadius: 2,
                    border: "1px solid var(--aos-border)",
                    background: "var(--aos-surface)",
                    padding: 16,
                  }}
                >
                  <div style={{ fontSize: 12, color: "var(--aos-amber-600)", fontWeight: 500 }}>Order 创建事件</div>
                  <p style={{ fontSize: 11, color: "var(--aos-text-secondary)", margin: "4px 0 0", lineHeight: 1.5 }}>
                    新订单 webhook → 自动风险分诊
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 运行历史 Tab */}
        {tab === "history" && (
          <div style={{ flex: 1, overflowY: "auto", padding: 24 }}>
            <div style={{ maxWidth: 768, margin: "0 auto" }}>
              <h2 style={{ fontSize: 18, fontWeight: 600, color: "var(--aos-text)", margin: "0 0 16px" }}>
                运行历史
              </h2>
              <div
                style={{
                  borderRadius: 2,
                  border: "1px solid var(--aos-border)",
                  background: "var(--aos-surface)",
                  overflow: "hidden",
                }}
              >
                <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ background: "var(--aos-surface-hover)", textAlign: "left" }}>
                      <th style={{ padding: "10px 16px", fontWeight: 500, color: "var(--aos-text-secondary)", fontSize: 11 }}>运行</th>
                      <th style={{ padding: "10px 16px", fontWeight: 500, color: "var(--aos-text-secondary)", fontSize: 11 }}>状态</th>
                      <th style={{ padding: "10px 16px", fontWeight: 500, color: "var(--aos-text-secondary)", fontSize: 11 }}>耗时</th>
                      <th style={{ padding: "10px 16px", fontWeight: 500, color: "var(--aos-text-secondary)", fontSize: 11 }}>输入</th>
                      <th style={{ padding: "10px 16px", fontWeight: 500, color: "var(--aos-text-secondary)", fontSize: 11 }}>结果</th>
                    </tr>
                  </thead>
                  <tbody>
                    {HISTORY_DATA.map((h) => (
                      <tr key={h.id} style={{ borderTop: "1px solid var(--aos-gray-100)" }}>
                        <td style={{ padding: "10px 16px", fontFamily: "monospace", color: "var(--aos-text)" }}>{h.id}</td>
                        <td style={{ padding: "10px 16px" }}>
                          <span
                            style={{
                              padding: "2px 8px",
                              borderRadius: 4,
                              fontSize: 11,
                              background: h.status === "success" ? "var(--aos-green-bg)" : "var(--aos-red-bg)",
                              color: h.status === "success" ? "var(--aos-green-700)" : "var(--aos-red)",
                            }}
                          >
                            {h.status === "success" ? "成功" : "失败"}
                          </span>
                        </td>
                        <td style={{ padding: "10px 16px", color: "var(--aos-text)" }}>{h.duration}</td>
                        <td style={{ padding: "10px 16px", fontFamily: "monospace", color: "var(--aos-text)" }}>
                          {h.input}
                        </td>
                        <td style={{ padding: "10px 16px" }}>
                          <span style={{ color: h.resultTone === "green" ? "var(--aos-green-600)" : "var(--aos-red)" }}>
                            {h.result}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </PageChrome>
  );
}

const selectStyle = {
  width: "100%",
  padding: "6px 10px",
  fontSize: 12,
  borderRadius: 2,
  border: "1px solid var(--aos-border)",
  background: "var(--aos-surface)",
  color: "var(--aos-text)",
} as const;
