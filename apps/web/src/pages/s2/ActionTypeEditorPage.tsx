import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { apiGet, apiPost, apiPut } from "../../api/client";
import { S2Chrome } from "./shared";
import { BpBanner, BpToolbar } from "./blueprintUi";

/* ────────────── Types ────────────── */

export type ActionStatus = "draft" | "submitted" | "validated" | "enabled" | "disabled";
export type ActionSubmissionStep = "editing" | "submitted" | "validated" | "enabled";

export type ActionType = {
  id: string;
  name: string;
  objectType: string;
  description: string;
  parameters: { name: string; type?: string; required?: boolean }[];
  requiredMarkings: string[];
  submissionCriteria: { field?: string; op?: string }[];
  status: ActionStatus;
  automations: { id: string; trigger: string; enabled: boolean }[];
};

/* ────────────── Constants ────────────── */

export const ACTION_STATUS_LABELS: Record<ActionStatus, string> = {
  draft: "草稿",
  submitted: "已提交",
  validated: "已验证",
  enabled: "已启用",
  disabled: "已禁用",
};

export const ACTION_STATUS_COLORS: Record<ActionStatus, string> = {
  draft: "#6B7280",
  submitted: "#3B82F6",
  validated: "#8B5CF6",
  enabled: "#22C55E",
  disabled: "#EF4444",
};

export const SUBMISSION_STEPS: { key: ActionSubmissionStep; label: string; description: string }[] = [
  { key: "editing", label: "编辑中", description: "草稿状态，可自由修改" },
  { key: "submitted", label: "已提交", description: "提交审核，等待校验" },
  { key: "validated", label: "已验证", description: "通过试跑校验" },
  { key: "enabled", label: "已启用", description: "上线运行中" },
];

export const ACTION_NAV_SECTIONS = [
  { key: "overview", label: "Overview" },
  { key: "rules", label: "Rules" },
  { key: "parameters", label: "Parameters" },
  { key: "ui", label: "User Interface" },
  { key: "capabilities", label: "Capabilities" },
  { key: "security", label: "Security & Submission Criteria" },
  { key: "automations", label: "Automations" },
  { key: "history", label: "History" },
] as const;

/* ────────────── Pure functions ────────────── */

export const emptyForm = (ot = "WorkOrder"): ActionType => ({
  id: "",
  name: "",
  objectType: ot,
  description: "",
  parameters: [{ name: "reason", type: "string", required: true }],
  requiredMarkings: ["public"],
  submissionCriteria: [{ field: "reason", op: "required" }],
  status: "draft",
  automations: [],
});

export function defaultPayloadFromParams(parameters: ActionType["parameters"]): string {
  const obj: Record<string, string> = {};
  for (const p of parameters || []) {
    if (p?.name) obj[p.name] = p.required ? "sample" : "";
  }
  if (Object.keys(obj).length === 0) obj.reason = "ok";
  return JSON.stringify(obj, null, 2);
}

export function validateActionType(form: ActionType): string[] {
  const errors: string[] = [];
  if (!form.id || !form.id.trim()) errors.push("id 不能为空");
  if (form.id && !/^[a-zA-Z_][a-zA-Z0-9_-]*$/.test(form.id))
    errors.push("id 必须以字母或下划线开头，只允许字母、数字、下划线、连字符");
  if (!form.name || !form.name.trim()) errors.push("name 不能为空");
  if (!form.objectType || !form.objectType.trim()) errors.push("objectType 不能为空");
  const nameSet = new Set<string>();
  for (const p of form.parameters || []) {
    if (!p.name || !p.name.trim()) errors.push("parameter name 不能为空");
    if (p.name && nameSet.has(p.name)) errors.push(`parameter name "${p.name}" 重复`);
    nameSet.add(p.name);
  }
  return errors;
}

export function canTransitionTo(current: ActionStatus, target: ActionStatus): boolean {
  const transitions: Record<ActionStatus, ActionStatus[]> = {
    draft: ["submitted", "disabled"],
    submitted: ["validated", "draft"],
    validated: ["enabled", "submitted"],
    enabled: ["disabled"],
    disabled: ["draft"],
  };
  return (transitions[current] || []).includes(target);
}

export function getSubmissionStep(status: ActionStatus): ActionSubmissionStep {
  if (status === "draft") return "editing";
  if (status === "submitted") return "submitted";
  if (status === "validated") return "validated";
  if (status === "enabled") return "enabled";
  return "editing";
}

export function stepIndex(step: ActionSubmissionStep): number {
  return SUBMISSION_STEPS.findIndex((s) => s.key === step);
}

export function isEditable(status: ActionStatus): boolean {
  return status === "draft" || status === "disabled";
}

export function parseMarkings(text: string): string[] {
  return text
    .split(/[,，\s]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export function summarizeParameters(parameters: ActionType["parameters"]): {
  total: number;
  required: number;
  optional: number;
} {
  const total = parameters.length;
  const required = parameters.filter((p) => p.required).length;
  return { total, required, optional: total - required };
}

/* ────────────── Component ────────────── */

export function ActionTypeEditorPage() {
  const { actionId = "new" } = useParams();
  const [sp] = useSearchParams();
  const navigate = useNavigate();
  const isNew = actionId === "new";
  const [form, setForm] = useState<ActionType>(() => emptyForm(sp.get("ot") || "WorkOrder"));
  const [paramJson, setParamJson] = useState("[]");
  const [markingsText, setMarkingsText] = useState("public");
  const [criteriaJson, setCriteriaJson] = useState("[]");
  const [payloadJson, setPayloadJson] = useState('{\n  "reason": "ok"\n}');
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [validateBusy, setValidateBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [validateMsg, setValidateMsg] = useState("");
  const [validateErr, setValidateErr] = useState("");
  const [activeSection, setActiveSection] = useState<string>("overview");

  useEffect(() => {
    if (isNew) {
      const base = emptyForm(sp.get("ot") || "WorkOrder");
      setForm(base);
      setParamJson(JSON.stringify(base.parameters, null, 2));
      setMarkingsText(base.requiredMarkings.join(", "));
      setCriteriaJson(JSON.stringify(base.submissionCriteria, null, 2));
      setPayloadJson(defaultPayloadFromParams(base.parameters));
      setDescription(base.description);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const row = await apiGet<ActionType>(`/v1/actions/types/${encodeURIComponent(actionId)}`);
        if (cancelled) return;
        setForm(row);
        setParamJson(JSON.stringify(row.parameters || [], null, 2));
        setMarkingsText((row.requiredMarkings || []).join(", "));
        setCriteriaJson(JSON.stringify(row.submissionCriteria || [], null, 2));
        setPayloadJson(defaultPayloadFromParams(row.parameters || []));
        setDescription(row.description || "");
      } catch (e) {
        if (!cancelled) setErr(String((e as Error).message || e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [actionId, isNew, sp]);

  function patch<K extends keyof ActionType>(key: K, value: ActionType[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function save() {
    setBusy(true);
    setMsg("");
    setErr("");
    try {
      const id = form.id.trim();
      const mergedForm = { ...form, description, id };
      const errors = validateActionType(mergedForm);
      if (errors.length > 0) throw new Error(errors.join("; "));
      let parameters: ActionType["parameters"];
      let submissionCriteria: ActionType["submissionCriteria"];
      try {
        parameters = JSON.parse(paramJson) as ActionType["parameters"];
        if (!Array.isArray(parameters)) throw new Error("parameters 须为数组");
      } catch {
        throw new Error("parameters JSON 无效");
      }
      try {
        submissionCriteria = JSON.parse(criteriaJson) as ActionType["submissionCriteria"];
        if (!Array.isArray(submissionCriteria)) throw new Error("criteria 须为数组");
      } catch {
        throw new Error("submissionCriteria JSON 无效");
      }
      const requiredMarkings = parseMarkings(markingsText);
      const body = {
        ...mergedForm,
        id,
        name: form.name.trim(),
        objectType: form.objectType.trim() || "WorkOrder",
        parameters,
        requiredMarkings,
        submissionCriteria,
      };
      if (isNew) {
        await apiPost("/v1/actions/types", body);
        setMsg(`已创建 ${id}`);
        navigate(`/ontology/action-types/${encodeURIComponent(id)}`, { replace: true });
      } else {
        await apiPut(`/v1/actions/types/${encodeURIComponent(id)}`, body);
        setMsg("已保存");
      }
    } catch (e) {
      setErr(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  async function runValidate() {
    setValidateBusy(true);
    setValidateMsg("");
    setValidateErr("");
    try {
      const id = form.id.trim();
      if (!id || isNew) throw new Error("请先创建并保存 Action Type");
      let payload: Record<string, unknown>;
      try {
        payload = JSON.parse(payloadJson) as Record<string, unknown>;
        if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
          throw new Error("payload 须为对象");
        }
      } catch {
        throw new Error("试跑 payload JSON 无效");
      }
      const res = await apiPost<{ ok?: boolean; actionTypeId?: string }>("/v1/actions/validate", {
        actionTypeId: id,
        payload,
      });
      setValidateMsg(res.ok ? `校验通过 · ${res.actionTypeId || id}` : "校验返回非 ok");
    } catch (e) {
      const errObj = e as Error & { body?: { details?: unknown; message?: string } };
      const details = errObj.body?.details;
      const detailText =
        details != null ? ` · ${typeof details === "string" ? details : JSON.stringify(details)}` : "";
      setValidateErr(`${errObj.message || String(e)}${detailText}`);
    } finally {
      setValidateBusy(false);
    }
  }

  async function transitionStatus(target: ActionStatus) {
    if (!canTransitionTo(form.status, target)) {
      setErr(`不允许从 ${ACTION_STATUS_LABELS[form.status]} 转换到 ${ACTION_STATUS_LABELS[target]}`);
      return;
    }
    setBusy(true);
    setErr("");
    try {
      const updated = await apiPut<ActionType>(`/v1/actions/types/${encodeURIComponent(form.id)}`, {
        ...form,
        status: target,
      });
      setForm(updated);
      setMsg(`状态已更新为 ${ACTION_STATUS_LABELS[target]}`);
    } catch (e) {
      setErr(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  const currentStep = getSubmissionStep(form.status);
  const currentStepIdx = stepIndex(currentStep);
  const editable = isEditable(form.status);
  const paramSummary = summarizeParameters(form.parameters);

  return (
    <S2Chrome
      title={isNew ? "新建 Action Type" : `Action Type · ${form.id}`}
      lede="元数据编辑 · 试跑基于已保存 criteria · 参数以 JSON 轻量维护"
    >
      <div className="ont-page">
        <BpToolbar>
          <Link to="/ontology" className="btn-nav">
            ← 发现
          </Link>
          {form.objectType && (
            <Link
              to={`/ontology/object-types/${encodeURIComponent(form.objectType)}`}
              className="btn-nav"
            >
              所属 OT →
            </Link>
          )}
          <button type="button" className="btn-primary" disabled={busy || !editable} onClick={() => void save()}>
            {busy ? "保存中…" : isNew ? "创建" : "保存"}
          </button>
          {!isNew && (
            <button
              type="button"
              className="btn-nav"
              disabled={validateBusy || busy}
              onClick={() => void runValidate()}
            >
              {validateBusy ? "校验中…" : "试跑校验"}
            </button>
          )}
        </BpToolbar>
        {msg && <p className="bp-prop-ok">{msg}</p>}
        {err && <p className="error">{err}</p>}

        <div style={actionStyles.layout}>
          {/* 左侧导航 */}
          <aside style={actionStyles.sideNav}>
            <Link to="/ontology" style={actionStyles.backLink}>
              ← Home
            </Link>
            <div style={actionStyles.typeNameRow}>
              <span style={actionStyles.typeIcon}>⚡</span>
              <span style={actionStyles.typeName}>{form.name || form.id || "新建 Action"}</span>
            </div>
            <div style={actionStyles.navSection}>
              {ACTION_NAV_SECTIONS.map((sec) => (
                <button
                  key={sec.key}
                  type="button"
                  style={activeSection === sec.key ? actionStyles.navItemActive : actionStyles.navItem}
                  onClick={() => setActiveSection(sec.key)}
                >
                  {sec.label}
                </button>
              ))}
            </div>
          </aside>

          {/* 右侧主区 */}
          <section style={actionStyles.main}>
            {/* 状态条 */}
            <div style={actionStyles.statusBar}>
              <div style={actionStyles.statusInfo}>
                <span
                  style={{
                    ...actionStyles.statusBadge,
                    background: `${ACTION_STATUS_COLORS[form.status]}20`,
                    color: ACTION_STATUS_COLORS[form.status],
                  }}
                >
                  {ACTION_STATUS_LABELS[form.status]}
                </span>
                <span style={actionStyles.mutedText}>API name:</span>
                <code style={actionStyles.monoText}>{form.id || "—"}</code>
              </div>
              {!isNew && editable && canTransitionTo(form.status, "submitted") && (
                <button
                  type="button"
                  style={actionStyles.transitionBtn}
                  disabled={busy}
                  onClick={() => void transitionStatus("submitted")}
                >
                  提交审核 →
                </button>
              )}
              {!isNew && canTransitionTo(form.status, "validated") && (
                <button
                  type="button"
                  style={actionStyles.transitionBtn}
                  disabled={busy}
                  onClick={() => void transitionStatus("validated")}
                >
                  验证 →
                </button>
              )}
              {!isNew && canTransitionTo(form.status, "enabled") && (
                <button
                  type="button"
                  style={{ ...actionStyles.transitionBtn, borderColor: "#22C55E", color: "#22C55E" }}
                  disabled={busy}
                  onClick={() => void transitionStatus("enabled")}
                >
                  启用 →
                </button>
              )}
            </div>

            {/* 提交流水线 */}
            <div style={actionStyles.pipeline}>
              {SUBMISSION_STEPS.map((step, idx) => (
                <div
                  key={step.key}
                  style={{
                    ...actionStyles.pipelineStep,
                    ...(idx <= currentStepIdx ? actionStyles.pipelineStepDone : {}),
                    ...(idx === currentStepIdx ? actionStyles.pipelineStepCurrent : {}),
                  }}
                >
                  <div style={actionStyles.pipelineDot}>
                    {idx < currentStepIdx ? "✓" : idx + 1}
                  </div>
                  <div>
                    <div style={actionStyles.pipelineLabel}>{step.label}</div>
                    <div style={actionStyles.pipelineDesc}>{step.description}</div>
                  </div>
                </div>
              ))}
            </div>

            {/* 信息卡 */}
            <div style={actionStyles.infoCard}>
              <div style={actionStyles.infoRow}>
                <div style={actionStyles.infoKey}>Description</div>
                <div style={actionStyles.infoValue}>
                  <textarea
                    className="aos-input"
                    style={{ minHeight: 60, fontSize: "0.8rem" }}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    disabled={!editable}
                    placeholder="Action Type 描述信息"
                  />
                </div>
              </div>
              <div style={actionStyles.infoRow}>
                <div style={actionStyles.infoKey}>所属 Ontology</div>
                <div style={actionStyles.infoValue}>{form.objectType || "—"}</div>
              </div>
              <div style={actionStyles.infoRow}>
                <div style={actionStyles.infoKey}>参数统计</div>
                <div style={actionStyles.infoValue}>
                  共 {paramSummary.total} 个 · 必需 {paramSummary.required} · 可选 {paramSummary.optional}
                </div>
              </div>
            </div>

            {/* 分区块内容 */}
            {activeSection === "overview" && (
              <div style={actionStyles.sectionCard}>
                <h3 style={actionStyles.sectionTitle}>Action type overview</h3>
                <div style={actionStyles.formGrid}>
                  <label className="ont-form-field">
                    <span>id</span>
                    <input
                      className="aos-input"
                      value={form.id}
                      disabled={!isNew}
                      onChange={(e) => patch("id", e.target.value)}
                      placeholder="CloseWorkOrder"
                    />
                  </label>
                  <label className="ont-form-field">
                    <span>name</span>
                    <input
                      className="aos-input"
                      value={form.name}
                      onChange={(e) => patch("name", e.target.value)}
                      disabled={!editable}
                    />
                  </label>
                  <label className="ont-form-field">
                    <span>objectType</span>
                    <input
                      className="aos-input"
                      value={form.objectType}
                      onChange={(e) => patch("objectType", e.target.value)}
                      disabled={!editable}
                    />
                  </label>
                  <label className="ont-form-field">
                    <span>requiredMarkings（逗号分隔）</span>
                    <input
                      className="aos-input"
                      value={markingsText}
                      onChange={(e) => setMarkingsText(e.target.value)}
                      disabled={!editable}
                    />
                  </label>
                </div>
              </div>
            )}

            {activeSection === "rules" && (
              <div style={actionStyles.sectionCard}>
                <h3 style={actionStyles.sectionTitle}>Submission Criteria (Rules)</h3>
                <BpBanner tone="info">
                  试跑调用已保存的 submissionCriteria / markings（不是表单草稿）。改 criteria 后请先保存再试跑。
                </BpBanner>
                <textarea
                  className="aos-input"
                  rows={6}
                  value={criteriaJson}
                  onChange={(e) => setCriteriaJson(e.target.value)}
                  disabled={!editable}
                  style={{ fontFamily: "ui-monospace, monospace", fontSize: "0.8rem", marginTop: "0.5rem" }}
                />
              </div>
            )}

            {activeSection === "parameters" && (
              <div style={actionStyles.sectionCard}>
                <h3 style={actionStyles.sectionTitle}>Parameters</h3>
                <textarea
                  className="aos-input"
                  rows={8}
                  value={paramJson}
                  onChange={(e) => setParamJson(e.target.value)}
                  disabled={!editable}
                  style={{ fontFamily: "ui-monospace, monospace", fontSize: "0.8rem" }}
                />
                {!isNew && (
                  <>
                    <h4 style={{ ...actionStyles.sectionTitle, fontSize: "0.8rem", marginTop: "1rem" }}>
                      试跑 payload（JSON）· 不落库
                    </h4>
                    <textarea
                      className="aos-input"
                      rows={5}
                      value={payloadJson}
                      onChange={(e) => setPayloadJson(e.target.value)}
                      style={{ fontFamily: "ui-monospace, monospace", fontSize: "0.8rem" }}
                    />
                    <button
                      type="button"
                      className="btn-nav"
                      disabled={validateBusy || busy}
                      onClick={() => void runValidate()}
                      style={{ marginTop: "0.5rem" }}
                    >
                      {validateBusy ? "校验中…" : "试跑校验（已保存规则）"}
                    </button>
                    {validateMsg && <p className="bp-prop-ok">{validateMsg}</p>}
                    {validateErr && <p className="error">{validateErr}</p>}
                  </>
                )}
              </div>
            )}

            {activeSection === "ui" && (
              <div style={actionStyles.sectionCard}>
                <h3 style={actionStyles.sectionTitle}>User Interface</h3>
                <p style={actionStyles.mutedText}>
                  为此 Action 配置表单 UI（字段顺序、默认值、条件可见性）。当前版本使用 JSON parameters 管理字段定义。
                </p>
              </div>
            )}

            {activeSection === "capabilities" && (
              <div style={actionStyles.sectionCard}>
                <h3 style={actionStyles.sectionTitle}>Capabilities</h3>
                <p style={actionStyles.mutedText}>
                  声明此 Action 可以执行的能力（读对象、写对象、调用函数、发送通知等）。
                </p>
                <div style={actionStyles.capGrid}>
                  {["readObjects", "writeObjects", "executeFunction", "sendNotification", "createDraft", "publishBranch"].map((cap) => (
                    <label key={cap} style={actionStyles.capItem}>
                      <input type="checkbox" disabled={!editable} />
                      <span style={{ fontSize: "0.75rem" }}>{cap}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}

            {activeSection === "security" && (
              <div style={actionStyles.sectionCard}>
                <h3 style={actionStyles.sectionTitle}>Security & Submission Criteria</h3>
                <BpBanner tone="warn">
                  修改 objectType 会影响 Draft 绑定。requiredMarkings 控制标记级权限。
                </BpBanner>
                <label className="ont-form-field" style={{ marginTop: "0.5rem" }}>
                  <span>requiredMarkings</span>
                  <input
                    className="aos-input"
                    value={markingsText}
                    onChange={(e) => setMarkingsText(e.target.value)}
                    disabled={!editable}
                  />
                </label>
              </div>
            )}

            {activeSection === "automations" && (
              <div style={actionStyles.sectionCard}>
                <h3 style={actionStyles.sectionTitle}>Automations</h3>
                <p style={actionStyles.mutedText}>
                  配置触发器（对象变更、定时、手动）自动调用此 Action。
                </p>
                {form.automations.length === 0 ? (
                  <p style={actionStyles.mutedText}>暂无自动化规则</p>
                ) : (
                  form.automations.map((a) => (
                    <div key={a.id} style={actionStyles.autoRow}>
                      <span style={actionStyles.autoTrigger}>{a.trigger}</span>
                      <span style={a.enabled ? actionStyles.autoEnabled : actionStyles.autoDisabled}>
                        {a.enabled ? "启用" : "禁用"}
                      </span>
                    </div>
                  ))
                )}
              </div>
            )}

            {activeSection === "history" && (
              <div style={actionStyles.sectionCard}>
                <h3 style={actionStyles.sectionTitle}>History</h3>
                <p style={actionStyles.mutedText}>查看此 Action Type 的修改历史和状态转换记录。</p>
              </div>
            )}
          </section>
        </div>
      </div>
    </S2Chrome>
  );
}

/* ────────────── Styles ────────────── */

const actionStyles: Record<string, React.CSSProperties> = {
  layout: { display: "flex", gap: "0.75rem", minHeight: "60vh" },
  sideNav: { width: 220, flexShrink: 0, borderRight: "1px solid var(--aos-border, #E5E7EB)", padding: "0.5rem" },
  backLink: { display: "flex", alignItems: "center", gap: "4px", fontSize: "0.75rem", color: "var(--aos-text-muted, #6B7280)", textDecoration: "none", marginBottom: "0.5rem" },
  typeNameRow: { display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" },
  typeIcon: { fontSize: "1.1rem" },
  typeName: { fontWeight: 600, fontSize: "0.85rem", color: "var(--aos-text, #111827)" },
  navSection: { display: "flex", flexDirection: "column" as const, gap: "1px" },
  navItem: { display: "flex", alignItems: "center", gap: "6px", padding: "5px 8px", fontSize: "0.75rem", border: "none", background: "transparent", color: "var(--aos-text-muted, #6B7280)", cursor: "pointer", borderRadius: "4px", textAlign: "left" as const },
  navItemActive: { display: "flex", alignItems: "center", gap: "6px", padding: "5px 8px", fontSize: "0.75rem", border: "none", background: "var(--aos-accent-bg, #EEF2FF)", color: "var(--aos-accent, #4F46E5)", cursor: "pointer", borderRadius: "4px", fontWeight: 600, textAlign: "left" as const },
  main: { flex: 1, minWidth: 0 },
  statusBar: { display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.5rem 0", borderBottom: "1px solid var(--aos-border, #E5E7EB)", marginBottom: "0.75rem" },
  statusInfo: { display: "flex", alignItems: "center", gap: "0.5rem", flex: 1 },
  statusBadge: { padding: "2px 8px", borderRadius: "4px", fontSize: "0.7rem", fontWeight: 600 },
  mutedText: { fontSize: "0.75rem", color: "var(--aos-text-muted, #9CA3AF)" },
  monoText: { fontFamily: "ui-monospace, monospace", fontSize: "0.75rem", color: "var(--aos-text, #374151)" },
  transitionBtn: { padding: "4px 12px", fontSize: "0.7rem", border: "1px solid var(--aos-border, #D1D5DB)", borderRadius: "6px", background: "var(--aos-surface, #fff)", color: "var(--aos-text, #374151)", cursor: "pointer", fontWeight: 500 },
  pipeline: { display: "flex", gap: "0.5rem", marginBottom: "0.75rem", flexWrap: "wrap" },
  pipelineStep: { display: "flex", alignItems: "center", gap: "6px", padding: "6px 10px", borderRadius: "6px", border: "1px solid var(--aos-border, #E5E7EB)", background: "var(--aos-surface, #fff)" },
  pipelineStepDone: { borderColor: "var(--aos-success-border, #86EFAC)", background: "var(--aos-success-bg, #F0FDF4)" },
  pipelineStepCurrent: { borderColor: "var(--aos-accent, #4F46E5)", boxShadow: "0 0 0 2px var(--aos-accent-bg, #EEF2FF)" },
  pipelineDot: { width: 20, height: 20, borderRadius: "50%", background: "var(--aos-surface-hover, #F3F4F6)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.65rem", fontWeight: 600, color: "var(--aos-text-muted, #6B7280)" },
  pipelineLabel: { fontSize: "0.7rem", fontWeight: 600, color: "var(--aos-text, #111827)" },
  pipelineDesc: { fontSize: "0.6rem", color: "var(--aos-text-muted, #9CA3AF)" },
  infoCard: { border: "1px solid var(--aos-border, #E5E7EB)", borderRadius: "8px", background: "var(--aos-surface, #fff)", marginBottom: "0.75rem" },
  infoRow: { display: "flex", padding: "0.4rem 0.75rem", borderBottom: "1px solid var(--aos-border, #E5E7EB)", gap: "0.5rem", alignItems: "flex-start" },
  infoKey: { width: 120, fontSize: "0.7rem", fontWeight: 600, color: "var(--aos-text-muted, #6B7280)", flexShrink: 0 },
  infoValue: { flex: 1, fontSize: "0.75rem", color: "var(--aos-text, #374151)" },
  sectionCard: { border: "1px solid var(--aos-border, #E5E7EB)", borderRadius: "8px", background: "var(--aos-surface, #fff)", padding: "0.75rem" },
  sectionTitle: { fontSize: "0.85rem", fontWeight: 600, color: "var(--aos-text, #111827)", marginBottom: "0.5rem" },
  formGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" },
  capGrid: { display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "4px", marginTop: "0.5rem" },
  capItem: { display: "flex", alignItems: "center", gap: "4px", padding: "4px", fontSize: "0.7rem" },
  autoRow: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "4px 8px", borderBottom: "1px solid var(--aos-border, #E5E7EB)", fontSize: "0.75rem" },
  autoTrigger: { fontFamily: "ui-monospace, monospace", color: "var(--aos-text, #374151)" },
  autoEnabled: { color: "#22C55E", fontWeight: 600 },
  autoDisabled: { color: "#EF4444", fontWeight: 600 },
};
