/**
 * 226 · 新建智能体向导 — 严格对齐 foundry/html/agents.html
 * 四步：基础信息 → 能力配置 → 安全等级 → 确认创建
 */
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  MOCK_MODELS,
  WIZARD_BUILTIN_TOOLS,
  WIZARD_DOMAINS,
  WIZARD_EXTERNAL_TOOLS,
  WIZARD_ICON_KEYS,
  WIZARD_MATURITY_LEVELS,
  WIZARD_ONTOLOGY_OPTIONS,
  canCreateAgent,
  draftToAgent,
  emptyWizardDraft,
  levelSummaryLabel,
  modelDisplayBlurb,
  modelDisplayName,
  validateStep1,
  validateStep2,
  validateStep3,
  type AgentItem,
  type AgentTool,
  type CatalogModel,
  type MaturityLevel,
  type WizardIconKey,
} from "./agentsCore";

const STEP_LABELS = ["基础信息", "能力配置", "安全等级", "确认创建"] as const;

function WizardIconSvg({ name }: { name: WizardIconKey }) {
  const common = {
    width: 20,
    height: 20,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.5,
  } as const;
  switch (name) {
    case "chat":
      return (
        <svg {...common}>
          <path
            d="M21 11.5a8.5 8.5 0 01-8.5 8.5H5l-3 3V11.5A8.5 8.5 0 0110.5 3h2A8.5 8.5 0 0121 11.5z"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      );
    case "tool":
      return (
        <svg {...common}>
          <path
            d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      );
    case "alert":
      return (
        <svg {...common}>
          <path
            d="M12 9v4M12 17h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      );
    case "chart":
      return (
        <svg {...common}>
          <rect x="3" y="5" width="18" height="14" rx="1" />
          <path d="M3 10h18M9 10v9M15 10v9" />
        </svg>
      );
    case "doc":
      return (
        <svg {...common}>
          <path
            d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" strokeLinecap="round" />
        </svg>
      );
    case "box":
      return (
        <svg {...common}>
          <path
            d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      );
  }
}

export function CreateAgentWizard({
  models,
  onClose,
  onCreate,
}: {
  models: CatalogModel[];
  onClose: () => void;
  onCreate: (agent: AgentItem) => void;
}) {
  const modelList = useMemo(() => {
    const list = models.length > 0 ? models : MOCK_MODELS;
    // 视觉稿优先展示 3 张旗舰卡；不足时用 MOCK 补齐
    if (list.length >= 3) return list.slice(0, 6);
    const ids = new Set(list.map((m) => m.id));
    return [...list, ...MOCK_MODELS.filter((m) => !ids.has(m.id))];
  }, [models]);

  const [step, setStep] = useState(1);
  const [draft, setDraft] = useState(() => emptyWizardDraft(modelList[0]?.id ?? ""));
  const [selectedTools, setSelectedTools] = useState<Set<string>>(
    () => new Set(WIZARD_BUILTIN_TOOLS.filter((t) => t.defaultOn).map((t) => t.name)),
  );
  const [toolTab, setToolTab] = useState<"builtin" | "external">("builtin");

  function patch<K extends keyof typeof draft>(key: K, value: (typeof draft)[K]) {
    setDraft((d) => ({ ...d, [key]: value }));
  }

  function toggleOntology(id: string) {
    setDraft((d) => ({
      ...d,
      ontology: d.ontology.includes(id)
        ? d.ontology.filter((x) => x !== id)
        : [...d.ontology, id],
    }));
  }

  function toggleTool(name: string, enabled: boolean) {
    setSelectedTools((prev) => {
      const next = new Set(prev);
      if (enabled) next.add(name);
      else next.delete(name);
      return next;
    });
  }

  function next() {
    if (step === 1) {
      const errs = validateStep1(draft);
      if (errs.length) {
        alert(errs.join("\n"));
        return;
      }
    }
    if (step === 2) {
      const errs = validateStep2(draft);
      if (errs.length) {
        alert(errs.join("\n"));
        return;
      }
    }
    if (step === 3) {
      const errs = validateStep3(draft);
      if (errs.length) {
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
          : name.includes("Function") || name.includes("Action")
            ? "Function"
            : "API",
      state: "on",
    }));
    const agent = draftToAgent(draft, () => `ag-${Date.now().toString(36)}`);
    onCreate({ ...agent, tools: toolList });
  }

  const selectedModel = modelList.find((m) => m.id === draft.modelId) || modelList[0];

  return (
    <div
      className="ag-wiz-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="ag-wiz-dialog" role="dialog" aria-label="新建智能体向导">
        <header className="ag-wiz-head">
          <div className="ag-wiz-head-row">
            <div>
              <h2 className="ag-wiz-title">新建智能体</h2>
              <p className="ag-wiz-sub">通过四步配置创建一个新的 AI Agent</p>
            </div>
            <button type="button" className="ag-wiz-close" aria-label="关闭向导" onClick={onClose}>
              ×
            </button>
          </div>
          <div className="ag-wiz-stepper">
            {STEP_LABELS.map((label, i) => {
              const s = i + 1;
              const isActive = step === s;
              const isDone = step > s;
              return (
                <div key={label} className="ag-wiz-step-item">
                  <div className="ag-wiz-step-node">
                    <div
                      className={`ag-wiz-step-dot${isActive ? " is-active" : ""}${isDone ? " is-done" : ""}`}
                    >
                      {isDone ? "✓" : s}
                    </div>
                    <span className={`ag-wiz-step-label${isActive || isDone ? " is-on" : ""}`}>
                      {label}
                    </span>
                  </div>
                  {i < 3 ? <div className="ag-wiz-step-line" /> : null}
                </div>
              );
            })}
          </div>
        </header>

        <div className="ag-wiz-body">
          {step === 1 && (
            <section className="ag-wiz-section">
              <h3 className="ag-wiz-h3">第一步：填写智能体基础信息</h3>
              <p className="ag-wiz-hint">设定名称、图标、业务域和用途描述。</p>

              <label className="ag-wiz-field">
                <span>
                  智能体名称 <em>*</em>
                </span>
                <input
                  value={draft.name}
                  onChange={(e) => patch("name", e.target.value)}
                  placeholder="例：售后退换货 Buddy"
                  maxLength={20}
                />
                <small>3-20 个字符，在同一项目内唯一</small>
              </label>

              <div className="ag-wiz-field">
                <span>
                  图标 <em>*</em>
                </span>
                <div className="ag-wiz-icons">
                  {WIZARD_ICON_KEYS.map((ic) => {
                    const sel = draft.icon === ic.key;
                    return (
                      <button
                        key={ic.key}
                        type="button"
                        title={ic.title}
                        className={`ag-wiz-icon-btn${sel ? " is-selected" : ""}`}
                        onClick={() => patch("icon", ic.key)}
                      >
                        <WizardIconSvg name={ic.key} />
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="ag-wiz-field">
                <span>
                  业务域 <em>*</em>
                </span>
                <div className="ag-wiz-chips">
                  {WIZARD_DOMAINS.map((d) => {
                    const sel = draft.domain === d;
                    return (
                      <button
                        key={d}
                        type="button"
                        className={`ag-wiz-chip${sel ? " is-selected" : ""}`}
                        onClick={() => patch("domain", d)}
                      >
                        {d}
                      </button>
                    );
                  })}
                </div>
              </div>

              <label className="ag-wiz-field">
                <span>用途描述</span>
                <textarea
                  value={draft.description}
                  onChange={(e) => patch("description", e.target.value)}
                  placeholder="一句话说明这个智能体的职责和适用场景…"
                  rows={3}
                />
              </label>
            </section>
          )}

          {step === 2 && (
            <section className="ag-wiz-section">
              <h3 className="ag-wiz-h3">第二步：配置智能体能力</h3>
              <p className="ag-wiz-hint">选择模型、编写系统提示词、勾选初始工具集。</p>

              <div className="ag-wiz-field">
                <span>
                  LLM 模型 <em>*</em>
                </span>
                <div className="ag-wiz-model-grid">
                  {modelList.slice(0, 3).map((m) => {
                    const sel = draft.modelId === m.id;
                    return (
                      <button
                        key={m.id}
                        type="button"
                        className={`ag-wiz-model-card${sel ? " is-selected" : ""}`}
                        onClick={() => patch("modelId", m.id)}
                      >
                        <div className="ag-wiz-model-name">{modelDisplayName(m)}</div>
                        <div className="ag-wiz-model-blurb">{modelDisplayBlurb(m)}</div>
                      </button>
                    );
                  })}
                </div>
                <Link to="/aip/model-catalog" className="ag-wiz-link">
                  在模型目录中浏览全部 →
                </Link>
              </div>

              <label className="ag-wiz-field">
                <span>
                  系统提示词 (System Prompt) <em>*</em>
                </span>
                <textarea
                  value={draft.prompt}
                  onChange={(e) => patch("prompt", e.target.value)}
                  placeholder={`你是${draft.name || "[智能体名称]"}。你的职责是…优先读 Object 与 Wiki 结构化字段，禁止臆造字段。写回操作必须走 Action / Draft 审批。`}
                  rows={5}
                />
                <div className="ag-wiz-prompt-meta">
                  <span>可用变量：/Order.status /Wiki.sla</span>
                  <button
                    type="button"
                    className="ag-wiz-link-btn"
                    onClick={() =>
                      patch(
                        "prompt",
                        `你是${draft.name || "智能体助手"}。优先读 Object 与 Wiki 结构化字段，禁止臆造字段。写回必须走 Action / Draft。`,
                      )
                    }
                  >
                    AI 辅助生成提示词 →
                  </button>
                </div>
              </label>

              <div className="ag-wiz-field">
                <span>本体上下文（Agent 可访问的对象类型）</span>
                <div className="ag-wiz-box">
                  {WIZARD_ONTOLOGY_OPTIONS.map((o) => (
                    <label key={o.id} className="ag-wiz-check-row">
                      <input
                        type="checkbox"
                        checked={draft.ontology.includes(o.id)}
                        onChange={() => toggleOntology(o.id)}
                      />
                      <span className="ag-wiz-check-label">{o.label}</span>
                      <span className="ag-wiz-check-hint">— {o.hint}</span>
                    </label>
                  ))}
                  <Link to="/ontology" className="ag-wiz-link">
                    在本体管理中查看全部对象类型 →
                  </Link>
                </div>
              </div>

              <div className="ag-wiz-field">
                <div className="ag-wiz-field-row">
                  <span>初始工具集（可后续在工具面板中调整）</span>
                  <Link to="/aip/tools" className="ag-wiz-link">
                    管理全部工具 →
                  </Link>
                </div>
                <div className="ag-wiz-tool-shell">
                  <div className="ag-wiz-tool-tabs">
                    <button
                      type="button"
                      className={`ag-wiz-tool-tab${toolTab === "builtin" ? " is-active" : ""}`}
                      onClick={() => setToolTab("builtin")}
                    >
                      平台内置 <span>{WIZARD_BUILTIN_TOOLS.length} 项</span>
                    </button>
                    <button
                      type="button"
                      className={`ag-wiz-tool-tab${toolTab === "external" ? " is-active" : ""}`}
                      onClick={() => setToolTab("external")}
                    >
                      外部工具扩展 <span>{WIZARD_EXTERNAL_TOOLS.length} 项可用</span>
                    </button>
                  </div>
                  <div className="ag-wiz-tool-panel">
                    {toolTab === "external" ? (
                      <p className="ag-wiz-tool-intro">
                        通过标准 Manifest 注册的扩展能力，经安全扫描后方可挂载
                      </p>
                    ) : null}
                    {toolTab === "builtin"
                      ? WIZARD_BUILTIN_TOOLS.map((t) => (
                          <label key={t.name} className="ag-wiz-tool-row">
                            <span className="ag-wiz-tool-left">
                              <input
                                type="checkbox"
                                checked={selectedTools.has(t.name)}
                                onChange={(e) => toggleTool(t.name, e.target.checked)}
                              />
                              <strong>{t.name}</strong>
                            </span>
                            <span className="ag-wiz-check-hint">{t.desc}</span>
                          </label>
                        ))
                      : WIZARD_EXTERNAL_TOOLS.map((t) => (
                          <label
                            key={t.name}
                            className={`ag-wiz-tool-row${t.disabled ? " is-disabled" : ""}`}
                          >
                            <span className="ag-wiz-tool-left">
                              <input
                                type="checkbox"
                                disabled={t.disabled}
                                checked={!t.disabled && selectedTools.has(t.name)}
                                onChange={(e) => toggleTool(t.name, e.target.checked)}
                              />
                              <strong>{t.name}</strong>
                              <span className={`ag-wiz-badge is-${t.badgeTone}`}>{t.badge}</span>
                            </span>
                            <span className="ag-wiz-check-hint">{t.desc}</span>
                          </label>
                        ))}
                    {toolTab === "external" ? (
                      <Link to="/aip/capability-import" className="ag-wiz-link">
                        + 注册新的扩展工具 →
                      </Link>
                    ) : null}
                  </div>
                </div>
              </div>
            </section>
          )}

          {step === 3 && (
            <section className="ag-wiz-section">
              <h3 className="ag-wiz-h3">第三步：设定安全等级与护栏</h3>
              <p className="ag-wiz-hint">
                根据智能体的写回权限，选择成熟度等级。可后续通过「成熟度楼梯」升级。
              </p>

              <div className="ag-wiz-field">
                <span>
                  成熟度等级 <em>*</em>
                </span>
                <div className="ag-wiz-levels">
                  {WIZARD_MATURITY_LEVELS.map((lv) => {
                    const sel = draft.level === lv.id;
                    return (
                      <button
                        key={lv.id}
                        type="button"
                        className={`ag-wiz-level${sel ? " is-selected" : ""}${lv.risk ? " is-risk" : ""}`}
                        onClick={() => patch("level", lv.id)}
                      >
                        <span className="ag-wiz-level-radio" aria-hidden>
                          {sel ? "●" : "○"}
                        </span>
                        <span className="ag-wiz-level-body">
                          <span className="ag-wiz-level-title">
                            <span className={`ag-wiz-level-tag is-${lv.id.toLowerCase()}`}>{lv.id}</span>
                            {lv.title}
                            {lv.recommended ? <span className="ag-wiz-rec">推荐</span> : null}
                            {lv.risk ? <span className="ag-wiz-risk">高风险</span> : null}
                          </span>
                          <span className={`ag-wiz-level-desc${lv.risk ? " is-risk" : ""}`}>{lv.desc}</span>
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="ag-wiz-field">
                <span>安全护栏</span>
                <div className="ag-wiz-box">
                  <label className="ag-wiz-guard-row">
                    <span>禁止臆造字段（强制结构化优先）</span>
                    <input
                      type="checkbox"
                      checked={draft.guardNoInvent}
                      onChange={(e) => patch("guardNoInvent", e.target.checked)}
                    />
                  </label>
                  <div className="ag-wiz-guard-row">
                    <span>Token 上限（防超量调用）</span>
                    <span className="ag-wiz-check-hint">10,000 tokens/会话</span>
                  </div>
                  <div className="ag-wiz-guard-row">
                    <span>速率限制（防 DDoS）</span>
                    <span className="ag-wiz-check-hint">30 次/分钟</span>
                  </div>
                  <label className="ag-wiz-guard-row">
                    <span>创建后自动进入 Draft 审批台</span>
                    <input
                      type="checkbox"
                      checked={draft.guardAutoDraft}
                      onChange={(e) => patch("guardAutoDraft", e.target.checked)}
                    />
                  </label>
                </div>
                <Link to="/aip/maturity" className="ag-wiz-link">
                  在成熟度楼梯中查看详细等级说明 →
                </Link>
              </div>
            </section>
          )}

          {step === 4 && (
            <section className="ag-wiz-section">
              <h3 className="ag-wiz-h3">第四步：确认配置并创建</h3>
              <p className="ag-wiz-hint">检查以下配置，创建后可在编辑器中进一步调整。</p>

              <div className="ag-wiz-summary">
                <div className="ag-wiz-summary-head">
                  <div className="ag-wiz-summary-icon">
                    <WizardIconSvg name={(draft.icon as WizardIconKey) || "chat"} />
                  </div>
                  <div>
                    <div className="ag-wiz-summary-name">{draft.name.trim() || "未命名智能体"}</div>
                    <div className="ag-wiz-summary-meta">
                      {draft.domain} · {MATURITY_SHORT(draft.level)}
                    </div>
                  </div>
                  <span className="ag-wiz-summary-badge">Draft</span>
                </div>
                <div className="ag-wiz-summary-body">
                  <div className="ag-wiz-kv">
                    <span>模型</span>
                    <span>{selectedModel ? modelDisplayName(selectedModel) : draft.modelId}</span>
                  </div>
                  <div className="ag-wiz-kv">
                    <span>提示词</span>
                    <span className="ag-wiz-clamp">{draft.prompt || "—"}</span>
                  </div>
                  <div className="ag-wiz-kv">
                    <span>本体上下文</span>
                    <span className="ag-wiz-tags">
                      {draft.ontology.length
                        ? draft.ontology.map((o) => (
                            <span key={o} className="ag-wiz-tag is-blue">
                              {o}
                            </span>
                          ))
                        : "—"}
                    </span>
                  </div>
                  <div className="ag-wiz-kv">
                    <span>初始工具</span>
                    <span className="ag-wiz-tags">
                      {Array.from(selectedTools).map((t) => (
                        <span key={t} className="ag-wiz-tag is-green">
                          {t.split(" · ")[0]}
                        </span>
                      ))}
                    </span>
                  </div>
                  <div className="ag-wiz-kv">
                    <span>安全等级</span>
                    <span className="ag-wiz-tag is-indigo">{levelSummaryLabel(draft.level)}</span>
                  </div>
                  <div className="ag-wiz-kv">
                    <span>护栏</span>
                    <span>
                      {[
                        draft.guardNoInvent ? "禁止臆造" : null,
                        "10K tokens",
                        "30 次/分",
                        draft.guardAutoDraft ? "自动入 Draft" : null,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                  </div>
                </div>
              </div>

              <div className="ag-wiz-after">
                <strong>创建后你需要：</strong>
                <ol>
                  <li>在「试运行」Tab 中验证 Agent 对话效果</li>
                  <li>通过 Evals 门控测试（至少通过率 ≥ 80%）</li>
                  <li>根据需要通过「成熟度楼梯」升级安全等级</li>
                  <li>在 Workshop 画布中将 Agent 组件拖入页面</li>
                </ol>
              </div>
            </section>
          )}
        </div>

        <footer className="ag-wiz-foot">
          <span className="ag-wiz-step-count">
            第 {step} / 4 步
          </span>
          <div className="ag-wiz-foot-actions">
            <button type="button" className="ag-wiz-btn-ghost" onClick={onClose}>
              取消
            </button>
            {step > 1 ? (
              <button type="button" className="ag-wiz-btn-ghost" onClick={prev}>
                上一步
              </button>
            ) : null}
            {step < 4 ? (
              <button type="button" className="ag-wiz-btn-primary" onClick={next}>
                下一步
              </button>
            ) : (
              <button type="button" className="ag-wiz-btn-success" onClick={finish}>
                创建智能体
              </button>
            )}
          </div>
        </footer>
      </div>
    </div>
  );
}

function MATURITY_SHORT(level: MaturityLevel): string {
  const map: Record<MaturityLevel, string> = {
    L0: "L0 只读",
    L1: "L1 Draft",
    L2: "L2 HITL",
    L3: "L3 Capability",
    L4: "L4 无人值守",
  };
  return map[level];
}
