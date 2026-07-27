import { useMemo, useState } from "react";
import { PageChrome } from "../../components/PageChrome";
import { apiPost } from "../../api/client";
import { useJsonGet } from "./shared";
import {
  // 常量与类型
  MOCK_AGENTS,
  MOCK_MODELS,
  HITL_PULSE_ANIMATION_NAME,
  HITL_PULSE_STYLE_TEXT,
  SOURCE_FILTERS,
  SOURCE_LABELS,
  SOURCE_BADGE_STYLE,
  TOOL_KIND_LABEL,
  TOOL_KIND_STYLE,
  type AgentItem,
  type AgentSource,
  type AgentTool,
  type AgentStatus,
  type CatalogModel,
  type SourceFilter,
  type WizardDraft,
  // 纯函数
  filterAgents,
  statusLabel,
  statusStyle,
  toolStateLabel,
  toolStateStyle,
  isHitlPending,
  toggleTool,
  approveHitl,
  rejectHitl,
  countToolStates,
  extractPromptVars,
  renderPrompt,
  validateStep1,
  validateStep2,
  canCreateAgent,
  draftToAgent,
  formatCalls,
  parseModelsPayload,
  resolveModelLabel,
  generateTrialReply,
} from "./agentsCore";

// -------------------- 试运行消息类型 --------------------

interface TrialMessage {
  role: "user" | "assistant";
  content: string;
}

// -------------------- 4 步向导 Modal --------------------

const WIZARD_ICONS = ["💬", "⚙", "⚠", "📊", "📄", "📦", "🎬", "🔗"];
const WIZARD_SOURCES: { value: AgentSource; label: string }[] = [
  { value: "platform", label: "平台内创建" },
  { value: "plugin", label: "插件市场" },
  { value: "external", label: "外部接入" },
];
const WIZARD_STEP_LABELS = ["基础信息", "模型选择", "系统提示词", "工具箱"];

function CreateAgentWizard({
  models,
  onClose,
  onCreate,
}: {
  models: CatalogModel[];
  onClose: () => void;
  onCreate: (agent: AgentItem) => void;
}) {
  const [step, setStep] = useState(1);
  const [draft, setDraft] = useState<WizardDraft>({
    name: "",
    description: "",
    icon: "",
    source: "platform",
    modelId: models[0]?.id ?? "",
    prompt: "",
  });
  const [selectedTools, setSelectedTools] = useState<Set<string>>(
    new Set(["Object Query", "Request Clarification"]),
  );

  const modelList = models.length > 0 ? models : MOCK_MODELS;

  function next() {
    if (step === 1) {
      const errs = validateStep1(draft);
      if (errs.length > 0) {
        alert(errs.join("\n"));
        return;
      }
    }
    if (step === 2) {
      const errs = validateStep2(draft);
      if (errs.length > 0) {
        alert(errs.join("\n"));
        return;
      }
    }
    setStep((s) => Math.min(4, s + 1));
  }
  function prev() {
    setStep((s) => Math.max(1, s - 1));
  }
  function finish() {
    if (!canCreateAgent(draft)) {
      alert("请先完成必填项");
      return;
    }
    const toolList: AgentTool[] = Array.from(selectedTools).map((name, i) => ({
      id: `t-${Date.now()}-${i}`,
      name,
      kind: name.includes("HTTP")
        ? "HTTP"
        : name.includes("MCP")
          ? "MCP"
          : name.includes("Function")
            ? "Function"
            : "API",
      state: "on",
    }));
    const agent = draftToAgent(draft, () => `ag-${Date.now().toString(36)}`);
    onCreate({ ...agent, tools: toolList });
  }

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 50,
        background: "rgba(0,0,0,0.4)",
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "center",
        padding: "24px 16px",
        overflow: "auto",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        role="dialog"
        aria-label="新建智能体向导"
        style={{
          background: "var(--aos-surface)",
          borderRadius: 16,
          boxShadow: "0 25px 50px -12px rgba(0,0,0,0.25)",
          width: "100%",
          maxWidth: 768,
          maxHeight: "90vh",
          overflow: "auto",
        }}
      >
        {/* 头部 + 步进器 */}
        <div
          style={{
            position: "sticky",
            top: 0,
            zIndex: 1,
            background: "var(--aos-surface)",
            borderBottom: "1px solid var(--aos-border)",
            padding: "16px 24px",
            borderRadius: "16px 16px 0 0",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <div>
              <h2 style={{ fontSize: 16, fontWeight: 600, color: "var(--aos-text)", margin: 0 }}>
                新建智能体
              </h2>
              <p style={{ fontSize: 10, color: "var(--aos-text-secondary)", margin: "2px 0 0 0" }}>
                通过四步配置创建一个新的 AI Agent
              </p>
            </div>
            <button
              onClick={onClose}
              aria-label="关闭向导"
              style={{
                width: 32,
                height: 32,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                borderRadius: 8,
                color: "var(--aos-text-tertiary)",
                background: "transparent",
                border: "none",
                cursor: "pointer",
                fontSize: 16,
              }}
            >
              ×
            </button>
          </div>
          <div style={{ display: "flex", alignItems: "center", marginTop: 12 }}>
            {[1, 2, 3, 4].map((s, i) => {
              const isActive = step === s;
              const isDone = step > s;
              return (
                <div key={s} style={{ display: "flex", alignItems: "center" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div
                      style={{
                        width: 28,
                        height: 28,
                        borderRadius: "50%",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontSize: 10,
                        fontWeight: 500,
                        background: isDone || isActive ? "var(--aos-indigo-600)" : "var(--aos-border)",
                        color: isDone || isActive ? "var(--aos-surface)" : "var(--aos-text-secondary)",
                      }}
                    >
                      {isDone ? "✓" : s}
                    </div>
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: isActive ? 500 : 400,
                        color: isActive || isDone ? "var(--aos-indigo-600)" : "var(--aos-text-tertiary)",
                      }}
                    >
                      {WIZARD_STEP_LABELS[i]}
                    </span>
                  </div>
                  {i < 3 && (
                    <div style={{ width: 48, height: 1, background: "var(--aos-border)", margin: "0 8px" }} />
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* 步骤内容 */}
        <div style={{ padding: "20px 24px" }}>
          {/* Step 1: 基础信息 */}
          {step === 1 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div>
                <h3 style={{ fontSize: 12, fontWeight: 600, color: "var(--aos-text)", margin: "0 0 4px 0" }}>
                  第一步：填写智能体基础信息
                </h3>
                <p style={{ fontSize: 10, color: "var(--aos-text-secondary)", margin: 0 }}>
                  设定名称、图标、来源与用途描述。
                </p>
              </div>
              <label style={{ fontSize: 10, fontWeight: 500, color: "var(--aos-text)", display: "flex", flexDirection: "column", gap: 4 }}>
                智能体名称 <span style={{ color: "var(--aos-red)" }}>*</span>
                <input
                  value={draft.name}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                  placeholder="例：售后退换货 Buddy"
                  style={inputStyle}
                />
              </label>
              <div>
                <div style={{ fontSize: 10, fontWeight: 500, color: "var(--aos-text)", marginBottom: 6 }}>
                  图标 <span style={{ color: "var(--aos-red)" }}>*</span>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(8, 1fr)", gap: 8 }}>
                  {WIZARD_ICONS.map((ic) => {
                    const sel = draft.icon === ic;
                    return (
                      <button
                        key={ic}
                        type="button"
                        onClick={() => setDraft({ ...draft, icon: ic })}
                        style={{
                          width: 36,
                          height: 36,
                          borderRadius: 8,
                          background: sel ? "var(--aos-indigo-bg)" : "var(--aos-surface-hover)",
                          border: `2px solid ${sel ? "var(--aos-indigo)" : "var(--aos-border)"}`,
                          cursor: "pointer",
                          fontSize: 16,
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                        }}
                      >
                        {ic}
                      </button>
                    );
                  })}
                </div>
              </div>
              <div>
                <div style={{ fontSize: 10, fontWeight: 500, color: "var(--aos-text)", marginBottom: 6 }}>
                  来源
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  {WIZARD_SOURCES.map((s) => {
                    const sel = draft.source === s.value;
                    return (
                      <button
                        key={s.value}
                        type="button"
                        onClick={() => setDraft({ ...draft, source: s.value })}
                        style={{
                          padding: "4px 12px",
                          borderRadius: 999,
                          fontSize: 10,
                          fontWeight: sel ? 500 : 400,
                          background: sel ? "var(--aos-indigo-bg)" : "var(--aos-surface)",
                          color: sel ? "var(--aos-indigo-600)" : "var(--aos-text-secondary)",
                          border: `1px solid ${sel ? "var(--aos-indigo-border)" : "var(--aos-border)"}`,
                          cursor: "pointer",
                        }}
                      >
                        {s.label}
                      </button>
                    );
                  })}
                </div>
              </div>
              <label style={{ fontSize: 10, fontWeight: 500, color: "var(--aos-text)", display: "flex", flexDirection: "column", gap: 4 }}>
                用途描述
                <textarea
                  value={draft.description}
                  onChange={(e) => setDraft({ ...draft, description: e.target.value })}
                  placeholder="一句话说明这个智能体的职责和适用场景…"
                  rows={3}
                  style={{ ...inputStyle, resize: "none" }}
                />
              </label>
            </div>
          )}

          {/* Step 2: 模型选择（从 /v1/aip/model-catalog 或 MOCK） */}
          {step === 2 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div>
                <h3 style={{ fontSize: 12, fontWeight: 600, color: "var(--aos-text)", margin: "0 0 4px 0" }}>
                  第二步：选择 LLM 模型
                </h3>
                <p style={{ fontSize: 10, color: "var(--aos-text-secondary)", margin: 0 }}>
                  从模型目录中选择 Agent 使用的语言模型。
                </p>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
                {modelList.map((m) => {
                  const sel = draft.modelId === m.id;
                  return (
                    <button
                      key={m.id}
                      type="button"
                      onClick={() => setDraft({ ...draft, modelId: m.id })}
                      style={{
                        borderRadius: 8,
                        border: `2px solid ${sel ? "var(--aos-indigo)" : "var(--aos-border)"}`,
                        background: sel ? "var(--aos-indigo-bg)" : "var(--aos-surface)",
                        padding: "8px 10px",
                        cursor: "pointer",
                        textAlign: "left",
                      }}
                    >
                      <div style={{ fontSize: 12, fontWeight: 500, color: "var(--aos-text)" }}>{m.id}</div>
                      <div style={{ fontSize: 9, color: "var(--aos-text-secondary)", marginTop: 2 }}>
                        {(m.kind ?? "text") === "text" ? "文本" : m.kind} · {m.provider || "默认供应商"}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* Step 3: 系统提示词 + 变量插值 */}
          {step === 3 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div>
                <h3 style={{ fontSize: 12, fontWeight: 600, color: "var(--aos-text)", margin: "0 0 4px 0" }}>
                  第三步：编写系统提示词
                </h3>
                <p style={{ fontSize: 10, color: "var(--aos-text-secondary)", margin: 0 }}>
                  支持变量插值 <code>{"${user.name}"}</code> / <code>{"${context.foo}"}</code>。
                </p>
              </div>
              <label style={{ fontSize: 10, fontWeight: 500, color: "var(--aos-text)", display: "flex", flexDirection: "column", gap: 4 }}>
                系统提示词 <span style={{ color: "var(--aos-red)" }}>*</span>
                <textarea
                  value={draft.prompt}
                  onChange={(e) => setDraft({ ...draft, prompt: e.target.value })}
                  placeholder={
                    "你是" +
                    (draft.name || "[智能体名称]") +
                    "。优先读 ${user.order}.status 与 ${context.wiki}.sla…"
                  }
                  rows={6}
                  style={{ ...inputStyle, fontFamily: "monospace", resize: "none" }}
                />
              </label>
              {/* 变量预览 */}
              <div>
                <div style={{ fontSize: 10, fontWeight: 500, color: "var(--aos-text)", marginBottom: 6 }}>
                  变量预览
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {extractPromptVars(draft.prompt).length === 0 && (
                    <span style={{ fontSize: 10, color: "var(--aos-text-tertiary)" }}>
                      暂无变量（示例：<code>{"${user.name}"}</code>）
                    </span>
                  )}
                  {extractPromptVars(draft.prompt).map((v) => (
                    <span
                      key={v.raw}
                      style={{
                        padding: "3px 8px",
                        borderRadius: 4,
                        fontSize: 9,
                        background: v.scope === "user" ? "var(--aos-accent-light)" : "var(--aos-indigo-bg)",
                        color: v.scope === "user" ? "var(--aos-blue-600)" : "var(--aos-purple-600)",
                        border: `1px solid ${v.scope === "user" ? "var(--aos-accent-border)" : "var(--aos-indigo-border)"}`,
                      }}
                    >
                      {v.raw}
                    </span>
                  ))}
                </div>
              </div>
              {/* 渲染预览 */}
              {extractPromptVars(draft.prompt).length > 0 && (
                <div
                  style={{
                    padding: 10,
                    borderRadius: 8,
                    background: "var(--aos-surface-hover)",
                    border: "1px dashed var(--aos-border)",
                    fontSize: 10,
                    color: "var(--aos-text-secondary)",
                    fontFamily: "monospace",
                  }}
                >
                  <div style={{ fontWeight: 500, marginBottom: 4, color: "var(--aos-text)" }}>
                    渲染预览（示例变量）：
                  </div>
                  {renderPrompt(draft.prompt, {
                    user: { name: "张三", order: "ORD-123" },
                    context: { wiki: "WikiDoc", sla: "SLA-24h" },
                  })}
                </div>
              )}
            </div>
          )}

          {/* Step 4: 工具箱 */}
          {step === 4 && (
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div>
                <h3 style={{ fontSize: 12, fontWeight: 600, color: "var(--aos-text)", margin: "0 0 4px 0" }}>
                  第四步：选择初始工具集
                </h3>
                <p style={{ fontSize: 10, color: "var(--aos-text-secondary)", margin: 0 }}>
                  勾选 Agent 创建后可调用的工具，后续可在「工具箱」Tab 调整。
                </p>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {[
                  { name: "Object Query · 对象查询", kind: "API" as const, desc: "读取本体数据的基础能力" },
                  { name: "Request Clarification · 澄清追问", kind: "API" as const, desc: "向用户追问不明确的参数" },
                  { name: "Action · 动作执行", kind: "Function" as const, desc: "写回操作（需 HITL 审批）" },
                  { name: "Function · 函数调用", kind: "Function" as const, desc: "调用 AIP Logic 注册的函数" },
                  { name: "MCP · 知识检索", kind: "MCP" as const, desc: "通过 MCP 协议检索知识库" },
                  { name: "HTTP · 外部接口", kind: "HTTP" as const, desc: "调用外部 HTTP API" },
                ].map((t) => {
                  const checked = selectedTools.has(t.name);
                  const ks = TOOL_KIND_STYLE[t.kind];
                  return (
                    <label
                      key={t.name}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                        padding: "8px 12px",
                        borderRadius: 8,
                        border: `1px solid ${checked ? "var(--aos-indigo-border)" : "var(--aos-border)"}`,
                        background: checked ? "var(--aos-indigo-bg)" : "var(--aos-surface)",
                        cursor: "pointer",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={(e) => {
                          const next = new Set(selectedTools);
                          if (e.target.checked) next.add(t.name);
                          else next.delete(t.name);
                          setSelectedTools(next);
                        }}
                        style={{ accentColor: "var(--aos-indigo)" }}
                      />
                      <span style={{ fontSize: 11, fontWeight: 500, color: "var(--aos-text)" }}>{t.name}</span>
                      <span
                        style={{
                          padding: "1px 6px",
                          borderRadius: 3,
                          fontSize: 9,
                          background: ks.bg,
                          color: ks.text,
                        }}
                      >
                        {TOOL_KIND_LABEL[t.kind]}
                      </span>
                      <span style={{ fontSize: 9, color: "var(--aos-text-tertiary)", marginLeft: "auto" }}>{t.desc}</span>
                    </label>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* 底部操作栏 */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "12px 24px",
            borderTop: "1px solid var(--aos-border)",
          }}
        >
          <span style={{ fontSize: 10, color: "var(--aos-text-tertiary)" }}>第 {step} / 4 步</span>
          <div style={{ display: "flex", gap: 6 }}>
            <button onClick={onClose} style={btnGhost}>取消</button>
            <button
              onClick={prev}
              disabled={step === 1}
              style={{
                ...btnGhost,
                visibility: step === 1 ? "hidden" : "visible",
              }}
            >
              上一步
            </button>
            {step < 4 ? (
              <button onClick={next} style={btnPrimary}>下一步</button>
            ) : (
              <button onClick={finish} style={btnSuccess}>完成创建</button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// -------------------- 主页面 --------------------

export function AgentsPage() {
  // 数据：Agent 列表（本地状态，支持新建后追加） + 模型目录
  const [agents, setAgents] = useState<AgentItem[]>(MOCK_AGENTS);
  const modelsApi = useJsonGet<{ items?: unknown[] } | unknown[]>("/v1/aip/models");
  const models: CatalogModel[] = useMemo(
    () => parseModelsPayload(modelsApi.data ?? MOCK_MODELS),
    [modelsApi.data],
  );

  const [selectedId, setSelectedId] = useState(MOCK_AGENTS[0].id);
  const [activeTab, setActiveTab] = useState<"prompt" | "tools" | "try" | "publish">("prompt");
  const [showWizard, setShowWizard] = useState(false);

  // 左侧列表状态
  const [keyword, setKeyword] = useState("");
  const [sourceFilter, setSourceFilter] = useState<SourceFilter>("all");

  // 试运行状态
  const [trialInput, setTrialInput] = useState("");
  const [trialMessages, setTrialMessages] = useState<TrialMessage[]>([]);

  // 发布历史
  const [publishHistory] = useState([
    { env: "prod", version: "v1.2.0", time: "2025-07-20 14:32", status: "已发布" },
    { env: "staging", version: "v1.3.0-rc1", time: "2025-07-25 09:15", status: "灰度中" },
    { env: "dev", version: "v1.3.0-dev", time: "2025-07-27 10:08", status: "构建中" },
  ]);

  const selected = agents.find((a) => a.id === selectedId) ?? agents[0];
  const filtered = filterAgents(agents, sourceFilter, keyword);
  const toolCounts = countToolStates(selected.tools);
  const promptVars = extractPromptVars(selected.prompt);

  function handleCreate(agent: AgentItem) {
    setAgents((prev) => [agent, ...prev]);
    setSelectedId(agent.id);
    setShowWizard(false);
  }

  function handleToggleTool(toolId: string) {
    setAgents((prev) =>
      prev.map((a) =>
        a.id === selected.id
          ? {
              ...a,
              tools: a.tools.map((t) => (t.id === toolId ? toggleTool(t) : t)),
            }
          : a,
      ),
    );
  }

  function handleApproveHitl(toolId: string) {
    setAgents((prev) =>
      prev.map((a) =>
        a.id === selected.id
          ? {
              ...a,
              tools: a.tools.map((t) =>
                t.id === toolId ? approveHitl(t) : t,
              ),
            }
          : a,
      ),
    );
  }

  function handleRejectHitl(toolId: string) {
    setAgents((prev) =>
      prev.map((a) =>
        a.id === selected.id
          ? {
              ...a,
              tools: a.tools.map((t) =>
                t.id === toolId ? rejectHitl(t) : t,
              ),
            }
          : a,
      ),
    );
  }

  async function handleSendTrial() {
    const text = trialInput.trim();
    if (!text) return;
    const userMsg: TrialMessage = { role: "user", content: text };
    const replyMsg: TrialMessage = {
      role: "assistant",
      content: generateTrialReply(selected, text),
    };
    setTrialMessages((prev) => [...prev, userMsg, replyMsg]);
    setTrialInput("");
    // 尝试调用后端 chat（失败静默，已有 mock 回复兜底）
    try {
      await apiPost("/v1/aip/agents/trial", {
        agentId: selected.id,
        message: text,
      });
    } catch {
      /* 后端未就绪时静默使用 mock 回复 */
    }
  }

  return (
    <PageChrome title="对话机器人" lede="4 步向导创建智能体 · 提示词变量插值 · 工具箱 HITL 确认 · 试运行">
      {/* 注入 HITL 脉冲动画 */}
      <style dangerouslySetInnerHTML={{ __html: HITL_PULSE_STYLE_TEXT }} />
      <div style={{ display: "flex", height: "calc(100vh - 120px)", minHeight: 0 }}>
        {/* ===== 左侧 Agent 列表 256px ===== */}
        <aside
          style={{
            width: 256,
            flexShrink: 0,
            borderRight: "1px solid var(--aos-border)",
            background: "var(--aos-surface)",
            overflow: "auto",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* 搜索框 */}
          <div style={{ padding: 12, borderBottom: "1px solid var(--aos-gray-100)" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 500, color: "var(--aos-text)" }}>智能体列表</span>
              <span style={{ fontSize: 9, color: "var(--aos-text-tertiary)" }}>{agents.length} 个</span>
            </div>
            <input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="搜索名称 / 描述…"
              style={{
                width: "100%",
                padding: "6px 10px",
                borderRadius: 8,
                border: "1px solid var(--aos-border)",
                fontSize: 11,
                outline: "none",
                boxSizing: "border-box",
                marginBottom: 8,
              }}
            />
            {/* 来源筛选 Tab */}
            <div style={{ display: "flex", gap: 4, marginBottom: 8 }}>
              {SOURCE_FILTERS.map((f) => {
                const sel = sourceFilter === f;
                const label =
                  f === "all" ? "全部" : SOURCE_LABELS[f as AgentSource];
                return (
                  <button
                    key={f}
                    onClick={() => setSourceFilter(f)}
                    style={{
                      flex: 1,
                      padding: "4px 0",
                      fontSize: 10,
                      fontWeight: sel ? 500 : 400,
                      color: sel ? "var(--aos-indigo-600)" : "var(--aos-text-secondary)",
                      background: sel ? "var(--aos-indigo-bg)" : "transparent",
                      border: sel ? "1px solid var(--aos-indigo-border)" : "1px solid transparent",
                      borderRadius: 6,
                      cursor: "pointer",
                    }}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
            <button
              onClick={() => setShowWizard(true)}
              style={{
                width: "100%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 6,
                padding: "8px 12px",
                borderRadius: 8,
                fontSize: 12,
                fontWeight: 500,
                color: "var(--text-on-brand)",
                background: "var(--aos-indigo-600)",
                border: "none",
                cursor: "pointer",
              }}
            >
              <span style={{ fontSize: 14, lineHeight: 1 }}>+</span>
              <span>新建智能体</span>
            </button>
          </div>

          {/* Agent 卡片列表 */}
          <div style={{ flex: 1, overflow: "auto" }}>
            {filtered.length === 0 && (
              <div style={{ padding: 24, textAlign: "center", fontSize: 11, color: "var(--aos-text-tertiary)" }}>
                未匹配到智能体
              </div>
            )}
            {filtered.map((a) => {
              const isSelected = a.id === selectedId;
              const sc = statusStyle(a.status);
              const ss = SOURCE_BADGE_STYLE[a.source];
              return (
                <div
                  key={a.id}
                  onClick={() => setSelectedId(a.id)}
                  style={{
                    padding: 12,
                    borderBottom: "1px solid var(--aos-surface-hover)",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 8,
                    background: isSelected ? "var(--aos-indigo-bg)" : "transparent",
                    borderLeft: isSelected ? "2px solid var(--aos-indigo)" : "2px solid transparent",
                  }}
                >
                  <div
                    style={{
                      width: 32,
                      height: 32,
                      borderRadius: 8,
                      background: "var(--aos-gray-100)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                      fontSize: 14,
                    }}
                  >
                    {a.icon}
                  </div>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div
                      style={{
                        fontSize: 12,
                        fontWeight: 500,
                        color: "var(--aos-text)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {a.name}
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 4, marginTop: 3 }}>
                      {/* 来源标签 */}
                      <span
                        style={{
                          padding: "1px 6px",
                          borderRadius: 3,
                          fontSize: 9,
                          background: ss.bg,
                          color: ss.text,
                        }}
                      >
                        {SOURCE_LABELS[a.source]}
                      </span>
                      {/* 状态 */}
                      <span
                        style={{
                          padding: "1px 6px",
                          borderRadius: 3,
                          fontSize: 9,
                          background: sc.bg,
                          color: sc.text,
                        }}
                      >
                        {statusLabel(a.status)}
                      </span>
                    </div>
                    {/* 调用次数 */}
                    <div style={{ fontSize: 9, color: "var(--aos-text-tertiary)", marginTop: 3 }}>
                      调用 {formatCalls(a.calls)} 次 · {a.tools.length} 工具
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </aside>

        {/* ===== 右侧 4 Tab 详情面板 ===== */}
        <div style={{ flex: 1, overflow: "auto", minWidth: 0 }}>
          <div style={{ maxWidth: 768, margin: "0 auto", padding: 24 }}>
            {/* 标题行 */}
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 16 }}>
              <div>
                <h1 style={{ fontSize: 18, fontWeight: 600, color: "var(--aos-text)", margin: 0 }}>
                  {selected.icon} {selected.name}
                </h1>
                <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", margin: "4px 0 0 0" }}>
                  {selected.description}
                </p>
                <div style={{ fontSize: 10, color: "var(--aos-text-tertiary)", marginTop: 4 }}>
                  模型：<span style={{ color: "var(--aos-text)", fontWeight: 500 }}>{resolveModelLabel(selected, models)}</span>
                  {" · "}累计调用 {formatCalls(selected.calls)} 次
                </div>
              </div>
            </div>

            {/* Tab 导航 */}
            <div style={{ borderBottom: "1px solid var(--aos-border)", display: "flex", gap: 24, marginBottom: 16 }}>
              {([
                { key: "prompt", label: "提示词", count: undefined },
                { key: "tools", label: "工具箱", count: selected.tools.length },
                { key: "try", label: "试运行", count: undefined },
                { key: "publish", label: "发布", count: undefined },
              ] as const).map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  style={{
                    padding: "10px 0",
                    fontSize: 12,
                    fontWeight: activeTab === tab.key ? 500 : 400,
                    color: activeTab === tab.key ? "var(--aos-indigo-600)" : "var(--aos-text-secondary)",
                    borderBottom:
                      activeTab === tab.key ? "2px solid var(--aos-indigo-600)" : "2px solid transparent",
                    background: "transparent",
                    cursor: "pointer",
                  }}
                >
                  {tab.label}
                  {tab.count != null && (
                    <span style={{ marginLeft: 4, fontSize: 10, color: "var(--aos-text-tertiary)" }}>
                      {tab.count}
                    </span>
                  )}
                </button>
              ))}
            </div>

            {/* ===== Tab 1: 提示词 ===== */}
            {activeTab === "prompt" && (
              <div style={cardStyle}>
                <label style={{ fontSize: 11, color: "var(--aos-text-secondary)" }}>系统提示词</label>
                <textarea
                  readOnly
                  value={selected.prompt}
                  style={{
                    width: "100%",
                    height: 128,
                    borderRadius: 8,
                    background: "var(--aos-bg)",
                    border: "1px solid var(--aos-border)",
                    padding: 12,
                    fontSize: 12,
                    color: "var(--aos-text)",
                    outline: "none",
                    resize: "none",
                    boxSizing: "border-box",
                    fontFamily: "monospace",
                    lineHeight: 1.5,
                  }}
                />
                {/* 变量预览 */}
                <div>
                  <div style={{ fontSize: 10, fontWeight: 500, color: "var(--aos-text)", marginBottom: 6 }}>
                    变量预览（$user / $context）
                  </div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {promptVars.length === 0 && (
                      <span style={{ fontSize: 10, color: "var(--aos-text-tertiary)" }}>本提示词未引用变量</span>
                    )}
                    {promptVars.map((v) => (
                      <span
                        key={v.raw}
                        style={{
                          padding: "4px 8px",
                          borderRadius: 4,
                          fontSize: 9,
                          background: v.scope === "user" ? "var(--aos-accent-light)" : "var(--aos-indigo-bg)",
                          color: v.scope === "user" ? "var(--aos-blue-600)" : "var(--aos-purple-600)",
                          border: `1px solid ${v.scope === "user" ? "var(--aos-accent-border)" : "var(--aos-indigo-border)"}`,
                        }}
                      >
                        {v.raw}
                      </span>
                    ))}
                  </div>
                </div>
                {/* 渲染预览 */}
                {promptVars.length > 0 && (
                  <div
                    style={{
                      padding: 10,
                      borderRadius: 8,
                      background: "var(--aos-surface-hover)",
                      border: "1px dashed var(--aos-border)",
                      fontSize: 10,
                      color: "var(--aos-text-secondary)",
                      fontFamily: "monospace",
                    }}
                  >
                    <div style={{ fontWeight: 500, marginBottom: 4, color: "var(--aos-text)" }}>
                      渲染示例（user.name=张三, context.wiki=WikiDoc）：
                    </div>
                    {renderPrompt(selected.prompt, {
                      user: { name: "张三", order: "ORD-123" },
                      context: { wiki: "WikiDoc", sla: "SLA-24h", risk: "RiskScanner", erp: "ErpBridge", brand: "BrandX" },
                    })}
                  </div>
                )}
              </div>
            )}

            {/* ===== Tab 2: 工具箱 ===== */}
            {activeTab === "tools" && (
              <div style={cardStyle}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span style={{ fontSize: 12, fontWeight: 500, color: "var(--aos-text)" }}>已启用工具</span>
                  <span style={{ fontSize: 10, color: "var(--aos-text-secondary)" }}>
                    已开 {toolCounts.on} · 推荐 {toolCounts.recommended} · 禁用 {toolCounts.disabled} ·
                    HITL 确认中 {toolCounts.hitl}
                  </span>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {selected.tools.length === 0 && (
                    <div style={{ padding: 16, textAlign: "center", fontSize: 11, color: "var(--aos-text-tertiary)" }}>
                      该智能体暂未配置工具
                    </div>
                  )}
                  {selected.tools.map((t) => {
                    const ks = TOOL_KIND_STYLE[t.kind];
                    const ts = toolStateStyle(t.state);
                    const hitl = isHitlPending(t);
                    return (
                      <div
                        key={t.id}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          border: `1px solid ${hitl ? "var(--aos-amber-border)" : "var(--aos-border)"}`,
                          background: hitl ? "var(--aos-amber-bg)" : "var(--aos-surface)",
                          borderRadius: 8,
                          padding: "8px 12px",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          {/* 开关按钮 */}
                          <ToggleSwitch
                            state={t.state}
                            onToggle={() => handleToggleTool(t.id)}
                          />
                          <div>
                            <span style={{ fontSize: 12, color: "var(--aos-text)", fontWeight: 500 }}>
                              {t.name}
                            </span>
                            <div style={{ display: "flex", gap: 4, marginTop: 2 }}>
                              {/* kind 标签 */}
                              <span
                                style={{
                                  padding: "1px 6px",
                                  borderRadius: 3,
                                  fontSize: 9,
                                  background: ks.bg,
                                  color: ks.text,
                                }}
                              >
                                {TOOL_KIND_LABEL[t.kind]}
                              </span>
                              {/* 状态徽章（含 HITL 脉冲动画） */}
                              <span
                                className={hitl ? HITL_PULSE_ANIMATION_NAME : undefined}
                                style={{
                                  padding: "1px 6px",
                                  borderRadius: 3,
                                  fontSize: 9,
                                  background: ts.bg,
                                  color: ts.text,
                                  fontWeight: hitl ? 600 : 400,
                                }}
                              >
                                {toolStateLabel(t.state)}
                                {hitl && t.hitlCallId ? ` · ${t.hitlCallId}` : ""}
                              </span>
                            </div>
                          </div>
                        </div>
                        {/* HITL 确认按钮 */}
                        {hitl && (
                          <div style={{ display: "flex", gap: 4 }}>
                            <button
                              onClick={() => handleApproveHitl(t.id)}
                              style={{
                                padding: "3px 10px",
                                borderRadius: 6,
                                fontSize: 10,
                                fontWeight: 500,
                                color: "var(--text-on-brand)",
                                background: "var(--aos-green-600)",
                                border: "none",
                                cursor: "pointer",
                              }}
                            >
                              批准
                            </button>
                            <button
                              onClick={() => handleRejectHitl(t.id)}
                              style={{
                                padding: "3px 10px",
                                borderRadius: 6,
                                fontSize: 10,
                                fontWeight: 500,
                                color: "var(--aos-red)",
                                background: "var(--aos-surface)",
                                border: "1px solid var(--aos-red-border)",
                                cursor: "pointer",
                              }}
                            >
                              拒绝
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* ===== Tab 3: 试运行 ===== */}
            {activeTab === "try" && (
              <div style={{ ...cardStyle, padding: 0 }}>
                <div
                  style={{
                    padding: "10px 14px",
                    borderBottom: "1px solid var(--aos-gray-100)",
                    fontSize: 12,
                    fontWeight: 500,
                    color: "var(--aos-text)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  <span>试运行 · {selected.name}</span>
                  {trialMessages.length > 0 && (
                    <button
                      onClick={() => setTrialMessages([])}
                      style={btnGhostSmall}
                    >
                      清空
                    </button>
                  )}
                </div>
                <div
                  style={{
                    height: 320,
                    overflow: "auto",
                    padding: 14,
                    display: "flex",
                    flexDirection: "column",
                    gap: 10,
                    background: "var(--aos-surface-hover)",
                  }}
                >
                  {trialMessages.length === 0 && (
                    <div style={{ margin: "auto", textAlign: "center", color: "var(--aos-text-tertiary)", fontSize: 11 }}>
                      发送一条消息开始测试 Agent
                    </div>
                  )}
                  {trialMessages.map((m, i) => (
                    <div
                      key={i}
                      style={{
                        alignSelf: m.role === "user" ? "flex-end" : "flex-start",
                        maxWidth: "80%",
                        padding: "8px 12px",
                        borderRadius: 10,
                        fontSize: 12,
                        lineHeight: 1.5,
                        background:
                          m.role === "user" ? "var(--aos-indigo-600)" : "var(--aos-surface)",
                        color: m.role === "user" ? "var(--aos-surface)" : "var(--aos-text)",
                        border:
                          m.role === "assistant"
                            ? "1px solid var(--aos-border)"
                            : "none",
                      }}
                    >
                      {m.role === "assistant" && (
                        <div style={{ fontSize: 9, color: "var(--aos-text-secondary)", marginBottom: 2 }}>
                          {selected.name}
                        </div>
                      )}
                      {m.content}
                    </div>
                  ))}
                </div>
                <div
                  style={{
                    display: "flex",
                    gap: 8,
                    padding: "10px 14px",
                    borderTop: "1px solid var(--aos-gray-100)",
                  }}
                >
                  <input
                    value={trialInput}
                    onChange={(e) => setTrialInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        handleSendTrial();
                      }
                    }}
                    placeholder={`向 ${selected.name} 发送消息…`}
                    style={{
                      flex: 1,
                      padding: "8px 12px",
                      borderRadius: 8,
                      border: "1px solid var(--aos-border)",
                      fontSize: 12,
                      outline: "none",
                    }}
                  />
                  <button onClick={handleSendTrial} style={btnPrimary}>
                    发送
                  </button>
                </div>
              </div>
            )}

            {/* ===== Tab 4: 发布 ===== */}
            {activeTab === "publish" && (
              <div style={cardStyle}>
                <h2 style={{ fontSize: 13, fontWeight: 500, color: "var(--aos-text)", margin: "0 0 12px 0" }}>
                  发布管理
                </h2>
                {/* 环境选择 */}
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 10, fontWeight: 500, color: "var(--aos-text)", marginBottom: 6 }}>
                    目标环境
                  </div>
                  <div style={{ display: "flex", gap: 6 }}>
                    {[
                      { env: "dev", label: "开发", color: "var(--aos-text-tertiary)" },
                      { env: "staging", label: "预发", color: "var(--aos-amber-600)" },
                      { env: "prod", label: "生产", color: "var(--aos-red)" },
                    ].map((e) => (
                      <span
                        key={e.env}
                        style={{
                          padding: "4px 12px",
                          borderRadius: 6,
                          fontSize: 10,
                          fontWeight: 500,
                          border: `1px solid ${e.color}40`,
                          color: e.color,
                          background: `${e.color}0A`,
                        }}
                      >
                        {e.label}
                      </span>
                    ))}
                  </div>
                </div>
                {/* 发布门控提示 */}
                {selected.status !== "active" && (
                  <div
                    style={{
                      padding: 10,
                      borderRadius: 8,
                      background: "var(--aos-amber-bg)",
                      border: "1px solid var(--aos-amber-border)",
                      fontSize: 10,
                      color: "var(--aos-amber-700)",
                      marginBottom: 12,
                    }}
                  >
                    ⚠ 当前状态为 {statusLabel(selected.status)}，发布前需通过 Evals 门控并切到 active。
                  </div>
                )}
                {/* 发布历史 */}
                <div>
                  <div style={{ fontSize: 10, fontWeight: 500, color: "var(--aos-text)", marginBottom: 6 }}>
                    发布历史
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    {publishHistory.map((h, i) => (
                      <div
                        key={i}
                        style={{
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "space-between",
                          padding: "8px 12px",
                          borderRadius: 8,
                          border: "1px solid var(--aos-border)",
                          fontSize: 11,
                        }}
                      >
                        <div>
                          <span style={{ color: "var(--aos-text)", fontWeight: 500 }}>{h.version}</span>
                          <span
                            style={{
                              marginLeft: 8,
                              padding: "1px 6px",
                              borderRadius: 3,
                              fontSize: 9,
                              background: "var(--aos-gray-100)",
                              color: "var(--aos-text-secondary)",
                            }}
                          >
                            {h.env}
                          </span>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                          <span style={{ fontSize: 10, color: "var(--aos-text-tertiary)" }}>{h.time}</span>
                          <span
                            style={{
                              padding: "1px 6px",
                              borderRadius: 3,
                              fontSize: 9,
                              background:
                                h.status === "已发布"
                                  ? "var(--aos-green-bg)"
                                  : h.status === "灰度中"
                                    ? "var(--aos-amber-bg)"
                                    : "var(--aos-accent-light)",
                              color:
                                h.status === "已发布"
                                  ? "var(--aos-green-700)"
                                  : h.status === "灰度中"
                                    ? "var(--aos-amber-600)"
                                    : "var(--aos-blue-600)",
                            }}
                          >
                            {h.status}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 4 步创建向导 */}
      {showWizard && (
        <CreateAgentWizard
          models={models}
          onClose={() => setShowWizard(false)}
          onCreate={handleCreate}
        />
      )}
    </PageChrome>
  );
}

// -------------------- 内部组件：开关 --------------------

function ToggleSwitch({
  state,
  onToggle,
}: {
  state: AgentTool["state"];
  onToggle: () => void;
}) {
  const on = state === "on" || state === "recommended" || state === "hitl";
  let bg = "var(--aos-border)";
  if (state === "on") bg = "var(--aos-green-600)";
  else if (state === "recommended") bg = "var(--aos-amber-600)";
  else if (state === "hitl") bg = "var(--aos-amber)";
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={state === "hitl"}
      aria-label={on ? "关闭工具" : "开启工具"}
      style={{
        width: 32,
        height: 18,
        borderRadius: 999,
        background: bg,
        border: "none",
        cursor: state === "hitl" ? "not-allowed" : "pointer",
        position: "relative",
        flexShrink: 0,
        opacity: state === "hitl" ? 0.85 : 1,
        transition: "background 0.2s",
      }}
    >
      <span
        style={{
          position: "absolute",
          top: 2,
          left: on ? 16 : 2,
          width: 14,
          height: 14,
          borderRadius: "50%",
          background: "var(--aos-surface)",
          boxShadow: "0 1px 2px rgba(0,0,0,0.2)",
          transition: "left 0.2s",
        }}
      />
    </button>
  );
}

// -------------------- 样式常量 --------------------

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "6px 12px",
  borderRadius: 8,
  border: "1px solid var(--aos-border-strong)",
  fontSize: 12,
  outline: "none",
  boxSizing: "border-box",
  color: "var(--aos-text)",
};

const cardStyle: React.CSSProperties = {
  borderRadius: 12,
  border: "1px solid var(--aos-border)",
  background: "var(--aos-surface)",
  padding: 20,
  display: "flex",
  flexDirection: "column",
  gap: 12,
};

const btnPrimary: React.CSSProperties = {
  padding: "6px 20px",
  fontSize: 12,
  fontWeight: 500,
  borderRadius: 8,
  border: "none",
  background: "var(--aos-indigo-600)",
  color: "var(--text-on-brand)",
  cursor: "pointer",
};

const btnSuccess: React.CSSProperties = {
  ...btnPrimary,
  background: "var(--aos-green-600)",
};

const btnGhost: React.CSSProperties = {
  padding: "6px 20px",
  fontSize: 12,
  borderRadius: 8,
  border: "1px solid var(--aos-border-strong)",
  background: "var(--aos-surface)",
  color: "var(--aos-text)",
  cursor: "pointer",
};

const btnGhostSmall: React.CSSProperties = {
  padding: "3px 10px",
  fontSize: 10,
  borderRadius: 6,
  border: "1px solid var(--aos-border)",
  background: "var(--aos-surface)",
  color: "var(--aos-text-secondary)",
  cursor: "pointer",
};

// 保留 AgentStatus 类型引用（用于将来扩展状态过滤）
export type { AgentStatus };
