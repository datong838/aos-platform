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

export type ActionTypePayload = Pick<
  ActionType,
  "id" | "name" | "objectType" | "parameters" | "requiredMarkings" | "submissionCriteria"
>;

/* ────────────── Constants ────────────── */

export const ACTION_STATUS_LABELS: Record<ActionStatus, string> = {
  draft: "草稿",
  submitted: "已提交",
  validated: "已验证",
  enabled: "已启用",
  disabled: "已禁用",
};

export const ACTION_STATUS_COLORS: Record<ActionStatus, string> = {
  draft: "var(--aos-text-secondary)",
  submitted: "var(--aos-accent)",
  validated: "var(--aos-purple-600)",
  enabled: "var(--aos-green)",
  disabled: "var(--aos-red)",
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

export function normalizeActionType(row: Partial<ActionType>): ActionType {
  const base = emptyForm(typeof row.objectType === "string" ? row.objectType : "WorkOrder");
  const status = row.status && Object.prototype.hasOwnProperty.call(ACTION_STATUS_LABELS, row.status)
    ? row.status
    : "draft";
  return {
    ...base,
    ...row,
    id: typeof row.id === "string" ? row.id : "",
    name: typeof row.name === "string" ? row.name : "",
    objectType: typeof row.objectType === "string" ? row.objectType : base.objectType,
    description: typeof row.description === "string" ? row.description : "",
    parameters: Array.isArray(row.parameters) ? row.parameters : [],
    requiredMarkings: Array.isArray(row.requiredMarkings) ? row.requiredMarkings : [],
    submissionCriteria: Array.isArray(row.submissionCriteria) ? row.submissionCriteria : [],
    status,
    automations: Array.isArray(row.automations) ? row.automations : [],
  };
}

export function toActionTypePayload(
  form: ActionType,
  parameters: ActionType["parameters"],
  requiredMarkings: string[],
  submissionCriteria: ActionType["submissionCriteria"],
): ActionTypePayload {
  return {
    id: form.id.trim(),
    name: form.name.trim(),
    objectType: form.objectType.trim() || "WorkOrder",
    parameters,
    requiredMarkings,
    submissionCriteria,
  };
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

/* ────────────── W4-C8b · overview helpers ────────────── */

export type RuleKindBadge = "Create" | "Modify" | "Delete" | "Link" | "Action";

export type OverviewInputItem = {
  name: string;
  type: string;
  required: boolean;
  desc: string;
};

export type OverviewRuleItem = {
  id: string;
  title: string;
  kind: RuleKindBadge;
  targetOt: string;
  summary: string;
  source: "remote" | "criteria";
};

export type RemoteActionRule = {
  id?: string;
  name?: string;
  kind?: string;
  target_otd_id?: string;
  condition?: string;
  enabled?: boolean;
};

export function deriveActionRid(id: string): string {
  const safe = (id || "").trim() || "unknown";
  return `ri.actions.main.action-type.${safe}`;
}

export function parseJsonArraySafe<T>(text: string, fallback: T[]): T[] {
  try {
    const parsed = JSON.parse(text) as unknown;
    return Array.isArray(parsed) ? (parsed as T[]) : fallback;
  } catch {
    return fallback;
  }
}

export function paramTypeBadge(type?: string): string {
  const t = (type || "string").trim().toLowerCase();
  if (!t) return "string";
  return t;
}

export function ruleKindBadge(kind?: string): RuleKindBadge {
  const k = (kind || "").trim().toLowerCase();
  if (k === "create") return "Create";
  if (k === "modify" || k === "update" || k === "set" || k === "required" || k === "eq" || k === "neq") {
    return "Modify";
  }
  if (k === "delete" || k === "remove") return "Delete";
  if (k === "link" || k === "unlink") return "Link";
  return "Action";
}

export function buildOverviewInputs(
  parameters: ActionType["parameters"] | null | undefined,
): OverviewInputItem[] {
  return (parameters || [])
    .filter((p) => p && typeof p.name === "string" && p.name.trim())
    .map((p) => ({
      name: p.name.trim(),
      type: paramTypeBadge(p.type),
      required: Boolean(p.required),
      desc: p.required ? "Required input" : "Optional input",
    }));
}

export function buildOverviewRules(
  criteria: ActionType["submissionCriteria"] | null | undefined,
  objectType: string,
  remoteRules?: RemoteActionRule[] | null,
): OverviewRuleItem[] {
  const ot = (objectType || "").trim() || "Object";
  const remote = (remoteRules || [])
    .filter((r) => r && (r.name || r.id))
    .map((r, idx) => ({
      id: r.id || `remote-${idx}`,
      title: (r.name || r.id || `Rule ${idx + 1}`).trim(),
      kind: ruleKindBadge(r.kind),
      targetOt: (r.target_otd_id || ot).trim() || ot,
      summary: (r.condition || "").trim() || (r.enabled === false ? "disabled" : "always"),
      source: "remote" as const,
    }));
  if (remote.length > 0) return remote;

  return (criteria || [])
    .filter((c) => c && (c.field || c.op))
    .map((c, idx) => {
      const field = (c.field || "").trim() || `rule-${idx + 1}`;
      const op = (c.op || "").trim() || "action";
      return {
        id: `crit-${idx}-${field}`,
        title: `${op} · ${field}`,
        kind: ruleKindBadge(op),
        targetOt: ot,
        summary: `submissionCriteria · ${op}${field ? ` on ${field}` : ""}`,
        source: "criteria" as const,
      };
    });
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
  const [remoteRules, setRemoteRules] = useState<RemoteActionRule[]>([]);
  const [rulesDegraded, setRulesDegraded] = useState(false);

  useEffect(() => {
    if (isNew) {
      const base = emptyForm(sp.get("ot") || "WorkOrder");
      setForm(base);
      setParamJson(JSON.stringify(base.parameters, null, 2));
      setMarkingsText(base.requiredMarkings.join(", "));
      setCriteriaJson(JSON.stringify(base.submissionCriteria, null, 2));
      setPayloadJson(defaultPayloadFromParams(base.parameters));
      setDescription(base.description);
      setRemoteRules([]);
      setRulesDegraded(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const row = await apiGet<Partial<ActionType>>(`/v1/actions/types/${encodeURIComponent(actionId)}`);
        if (cancelled) return;
        const normalized = normalizeActionType(row);
        setForm(normalized);
        setParamJson(JSON.stringify(normalized.parameters, null, 2));
        setMarkingsText(normalized.requiredMarkings.join(", "));
        setCriteriaJson(JSON.stringify(normalized.submissionCriteria, null, 2));
        setPayloadJson(defaultPayloadFromParams(normalized.parameters));
        setDescription(normalized.description);
      } catch (e) {
        if (!cancelled) setErr(String((e as Error).message || e));
      }
      // W4-C8b：远程规则可选；失败静默降级到 submissionCriteria 派生
      try {
        const res = await apiGet<{ items?: RemoteActionRule[] }>(
          `/v1/action-rules?action_type_id=${encodeURIComponent(actionId)}`,
        );
        if (cancelled) return;
        setRemoteRules(Array.isArray(res.items) ? res.items : []);
        setRulesDegraded(false);
      } catch {
        if (!cancelled) {
          setRemoteRules([]);
          setRulesDegraded(true);
        }
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
      const body = toActionTypePayload(form, parameters, requiredMarkings, submissionCriteria);
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

  const currentStep = getSubmissionStep(form.status);
  const currentStepIdx = stepIndex(currentStep);
  const editable = isEditable(form.status);
  const liveParams = parseJsonArraySafe<ActionType["parameters"][number]>(paramJson, form.parameters || []);
  const liveCriteria = parseJsonArraySafe<ActionType["submissionCriteria"][number]>(
    criteriaJson,
    form.submissionCriteria || [],
  );
  const paramSummary = summarizeParameters(liveParams);
  const overviewInputs = buildOverviewInputs(liveParams);
  const overviewRules = buildOverviewRules(liveCriteria, form.objectType, remoteRules);
  const actionRid = deriveActionRid(form.id || actionId);

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
                  disabled
                  title="Action Type DTO 暂不支持工作流状态写入"
                >
                  提交审核（只读）
                </button>
              )}
              {!isNew && canTransitionTo(form.status, "validated") && (
                <button
                  type="button"
                  style={actionStyles.transitionBtn}
                  disabled
                  title="Action Type DTO 暂不支持工作流状态写入"
                >
                  验证 →
                </button>
              )}
              {!isNew && canTransitionTo(form.status, "enabled") && (
                <button
                  type="button"
                  style={{ ...actionStyles.transitionBtn, borderColor: "var(--aos-green)", color: "var(--aos-green)" }}
                  disabled
                  title="Action Type DTO 暂不支持工作流状态写入"
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
                    readOnly
                    disabled
                    aria-label="Action Type 描述（当前只读）"
                    placeholder="后端 DTO 暂不提供描述字段"
                  />
                </div>
              </div>
              <div style={actionStyles.infoRow}>
                <div style={actionStyles.infoKey}>所属 Ontology</div>
                <div style={actionStyles.infoValue}>{form.objectType || "—"}</div>
              </div>
              <div style={actionStyles.infoRow}>
                <div style={actionStyles.infoKey}>RID</div>
                <div style={actionStyles.infoValue}>
                  <code className="at-rid">{actionRid}</code>
                </div>
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

                {/* W4-C8b：Input + Rules 双列可视化 */}
                <div className="at-overview" data-testid="at-overview">
                  <div className="at-overview-head">
                    <span>Action overview</span>
                    {rulesDegraded && (
                      <span className="at-overview-degrade">规则 API 不可用 · 已用 criteria 派生</span>
                    )}
                  </div>
                  <div className="at-overview-cols">
                    <div className="at-overview-col">
                      <div className="at-overview-col-head">Input</div>
                      {overviewInputs.length === 0 ? (
                        <p className="at-overview-empty">暂无参数 · 可在 Parameters 编辑 JSON</p>
                      ) : (
                        overviewInputs.map((item) => (
                          <div key={item.name} className="at-overview-item">
                            <div className="at-overview-item-icon" aria-hidden>
                              I
                            </div>
                            <div className="at-overview-item-body">
                              <div className="at-overview-item-title">
                                {item.name}
                                <span className={`at-kind-badge at-type-badge`}>{item.type}</span>
                                {item.required && <span className="at-req-badge">required</span>}
                              </div>
                              <div className="at-overview-item-desc">{item.desc}</div>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                    <div className="at-overview-col">
                      <div className="at-overview-col-head">Rules</div>
                      {overviewRules.length === 0 ? (
                        <p className="at-overview-empty">暂无规则 · 可在 Rules 编辑 criteria</p>
                      ) : (
                        <div className="at-rule-flow">
                          {overviewRules.map((rule, idx) => (
                            <div key={rule.id} className="at-rule-flow-step">
                              {idx > 0 && <div className="at-rule-flow-arrow" aria-hidden />}
                              <div className="at-overview-item">
                                <div className="at-overview-item-icon" aria-hidden>
                                  R
                                </div>
                                <div className="at-overview-item-body">
                                  <div className="at-overview-item-title">
                                    {rule.title}
                                    <span className={`at-kind-badge at-kind-${rule.kind.toLowerCase()}`}>
                                      {rule.kind}
                                    </span>
                                    <span className="at-ot-badge">{rule.targetOt}</span>
                                  </div>
                                  <div className="at-overview-item-desc">{rule.summary}</div>
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeSection === "rules" && (
              <div style={actionStyles.sectionCard}>
                <h3 style={actionStyles.sectionTitle}>Submission Criteria (Rules)</h3>
                <BpBanner tone="info">
                  试跑调用已保存的 submissionCriteria / markings（不是表单草稿）。改 criteria 后请先保存再试跑。
                </BpBanner>
                <div className="at-rule-flow at-rule-flow--panel" data-testid="at-rules-flow">
                  {overviewRules.length === 0 ? (
                    <p className="at-overview-empty">派生预览为空</p>
                  ) : (
                    overviewRules.map((rule, idx) => (
                      <div key={rule.id} className="at-rule-flow-step">
                        {idx > 0 && <div className="at-rule-flow-arrow" aria-hidden />}
                        <div className="at-overview-item">
                          <span className={`at-kind-badge at-kind-${rule.kind.toLowerCase()}`}>{rule.kind}</span>
                          <div className="at-overview-item-body">
                            <div className="at-overview-item-title">
                              {rule.title}
                              <span className="at-ot-badge">{rule.targetOt}</span>
                            </div>
                            <div className="at-overview-item-desc">{rule.summary}</div>
                          </div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
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
                <div className="at-param-table-wrap" data-testid="at-param-table">
                  <table className="at-param-table">
                    <thead>
                      <tr>
                        <th>Name</th>
                        <th>Type</th>
                        <th>Required</th>
                      </tr>
                    </thead>
                    <tbody>
                      {overviewInputs.length === 0 ? (
                        <tr>
                          <td colSpan={3} className="at-overview-empty">
                            无参数 · 编辑下方 JSON
                          </td>
                        </tr>
                      ) : (
                        overviewInputs.map((p) => (
                          <tr key={p.name}>
                            <td>{p.name}</td>
                            <td>
                              <span className="at-kind-badge at-type-badge">{p.type}</span>
                            </td>
                            <td>{p.required ? "yes" : "no"}</td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
                <textarea
                  className="aos-input"
                  rows={8}
                  value={paramJson}
                  onChange={(e) => setParamJson(e.target.value)}
                  disabled={!editable}
                  style={{ fontFamily: "ui-monospace, monospace", fontSize: "0.8rem", marginTop: "0.5rem" }}
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
                <h3 style={actionStyles.sectionTitle}>User Interface · 当前只读/规划中</h3>
                <BpBanner tone="info">
                  Action Type DTO 暂未提供表单 UI 配置字段；以下控件仅展示规划，不会写入服务端。
                </BpBanner>
                <p style={actionStyles.mutedText}>
                  当前使用已保存的 parameters 展示输入字段；布局与确认步骤需等待正式契约。
                </p>
                <div style={actionStyles.formGrid}>
                  <label className="ont-form-field">
                    <span>表单布局（规划）</span>
                    <select
                      className="aos-input"
                      value="automatic"
                      disabled
                      data-testid="action-ui-layout"
                      aria-label="表单布局（当前只读）"
                    >
                      <option value="automatic">按 parameters 自动布局</option>
                    </select>
                  </label>
                  <label style={actionStyles.capItem}>
                    <input type="checkbox" checked={false} disabled readOnly />
                    <span style={{ fontSize: "0.75rem" }}>提交前确认（规划）</span>
                  </label>
                </div>
              </div>
            )}

            {activeSection === "capabilities" && (
              <div style={actionStyles.sectionCard}>
                <h3 style={actionStyles.sectionTitle}>Capabilities · 当前只读/规划中</h3>
                <BpBanner tone="info">
                  Action Type DTO 暂未提供 capabilities 字段；统一显示“未配置”，不会写入服务端。
                </BpBanner>
                <p style={actionStyles.mutedText}>
                  声明此 Action 可以执行的能力（读对象、写对象、调用函数、发送通知等）。
                </p>
                <div style={actionStyles.capGrid}>
                  {["readObjects", "writeObjects", "executeFunction", "sendNotification", "createDraft", "publishBranch"].map((cap) => (
                    <label key={cap} style={actionStyles.capItem}>
                      <input
                        type="checkbox"
                        checked={false}
                        disabled
                        readOnly
                        data-testid="action-capability"
                      />
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
  sideNav: { width: 220, flexShrink: 0, borderRight: "1px solid var(--aos-border)", padding: "0.5rem" },
  backLink: { display: "flex", alignItems: "center", gap: "4px", fontSize: "0.75rem", color: "var(--aos-text-secondary)", textDecoration: "none", marginBottom: "0.5rem" },
  typeNameRow: { display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" },
  typeIcon: { fontSize: "1.1rem" },
  typeName: { fontWeight: 600, fontSize: "0.85rem", color: "var(--aos-text)" },
  navSection: { display: "flex", flexDirection: "column" as const, gap: "1px" },
  navItem: { display: "flex", alignItems: "center", gap: "6px", padding: "5px 8px", fontSize: "0.75rem", border: "none", background: "transparent", color: "var(--aos-text-secondary)", cursor: "pointer", borderRadius: "4px", textAlign: "left" as const },
  navItemActive: { display: "flex", alignItems: "center", gap: "6px", padding: "5px 8px", fontSize: "0.75rem", border: "none", background: "var(--aos-accent-light)", color: "var(--aos-accent)", cursor: "pointer", borderRadius: "4px", fontWeight: 600, textAlign: "left" as const },
  main: { flex: 1, minWidth: 0 },
  statusBar: { display: "flex", alignItems: "center", gap: "0.75rem", padding: "0.5rem 0", borderBottom: "1px solid var(--aos-border)", marginBottom: "0.75rem" },
  statusInfo: { display: "flex", alignItems: "center", gap: "0.5rem", flex: 1 },
  statusBadge: { padding: "2px 8px", borderRadius: "4px", fontSize: "0.7rem", fontWeight: 600 },
  mutedText: { fontSize: "0.75rem", color: "var(--aos-text-tertiary)" },
  monoText: { fontFamily: "ui-monospace, monospace", fontSize: "0.75rem", color: "var(--aos-text-secondary)" },
  transitionBtn: { padding: "4px 12px", fontSize: "0.7rem", border: "1px solid var(--aos-border-strong)", borderRadius: "2px", background: "var(--aos-surface)", color: "var(--aos-text-secondary)", cursor: "pointer", fontWeight: 500 },
  pipeline: { display: "flex", gap: "0.5rem", marginBottom: "0.75rem", flexWrap: "wrap" },
  pipelineStep: { display: "flex", alignItems: "center", gap: "6px", padding: "6px 10px", borderRadius: "2px", border: "1px solid var(--aos-border)", background: "var(--aos-surface)" },
  pipelineStepDone: { borderColor: "var(--aos-green-border)", background: "var(--aos-green-bg)" },
  pipelineStepCurrent: { borderColor: "var(--aos-accent)", boxShadow: "0 0 0 2px var(--aos-accent-light)" },
  pipelineDot: { width: 20, height: 20, borderRadius: "50%", background: "var(--aos-gray-100)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.65rem", fontWeight: 600, color: "var(--aos-text-secondary)" },
  pipelineLabel: { fontSize: "0.7rem", fontWeight: 600, color: "var(--aos-text)" },
  pipelineDesc: { fontSize: "0.6rem", color: "var(--aos-text-tertiary)" },
  infoCard: { border: "1px solid var(--aos-border)", borderRadius: "2px", background: "var(--aos-surface)", marginBottom: "0.75rem" },
  infoRow: { display: "flex", padding: "0.4rem 0.75rem", borderBottom: "1px solid var(--aos-border)", gap: "0.5rem", alignItems: "flex-start" },
  infoKey: { width: 120, fontSize: "0.7rem", fontWeight: 600, color: "var(--aos-text-secondary)", flexShrink: 0 },
  infoValue: { flex: 1, fontSize: "0.75rem", color: "var(--aos-text-secondary)" },
  sectionCard: { border: "1px solid var(--aos-border)", borderRadius: "2px", background: "var(--aos-surface)", padding: "0.75rem" },
  sectionTitle: { fontSize: "0.85rem", fontWeight: 600, color: "var(--aos-text)", marginBottom: "0.5rem" },
  formGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" },
  capGrid: { display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "4px", marginTop: "0.5rem" },
  capItem: { display: "flex", alignItems: "center", gap: "4px", padding: "4px", fontSize: "0.7rem" },
  autoRow: { display: "flex", alignItems: "center", justifyContent: "space-between", padding: "4px 8px", borderBottom: "1px solid var(--aos-border)", fontSize: "0.75rem" },
  autoTrigger: { fontFamily: "ui-monospace, monospace", color: "var(--aos-text-secondary)" },
  autoEnabled: { color: "var(--aos-green)", fontWeight: 600 },
  autoDisabled: { color: "var(--aos-red)", fontWeight: 600 },
};
