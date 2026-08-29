import { useState, useEffect, useMemo, useCallback } from "react";
import { PageChrome } from "../../components/PageChrome";
import { BpToolbar } from "../../components/bp/BpToolbar";
import { apiDelete, apiGet, apiPost, apiPut } from "../../api/client";

/* ============================================================================
 * 类型定义
 * ========================================================================== */

type EventStatus = "active" | "draft" | "paused";

type EventItem = {
  id: string;
  name: string;
  description?: string;
  triggerId: TriggerId;
  actionId: ActionId;
  params: Record<string, string>;
  status: EventStatus;
  idempotent: boolean;
  idempotencyKey?: string;
  isNew?: boolean;
};

type ModuleEventApiItem = {
  id: string;
  moduleId?: string;
  name?: string;
  trigger?: { type?: string; params?: Record<string, string>; [key: string]: unknown };
  action?: {
    type?: string;
    params?: Record<string, string>;
    description?: string;
    idempotent?: boolean;
    idempotencyKey?: string;
    [key: string]: unknown;
  };
  enabled?: boolean;
};

type TriggerId =
  | "pageLoad"
  | "dataChange"
  | "timer"
  | "userAction"
  | "apiCallback"
  | "manual";

type ActionId =
  | "showMessage"
  | "navigate"
  | "callApi"
  | "updateData"
  | "sendNotification"
  | "openOverlay"
  | "exportData";

/* ============================================================================
 * 常量 & 纯函数（便于测试）
 * ========================================================================== */

/** 6 个触发器卡片（单选） */
export const TRIGGERS: { id: TriggerId; name: string; icon: string; desc: string }[] = [
  { id: "pageLoad", name: "页面加载", icon: "🕐", desc: "页面首次渲染完成时触发" },
  { id: "dataChange", name: "数据变更", icon: "📊", desc: "绑定的数据集发生变化时触发" },
  { id: "timer", name: "定时触发", icon: "⏰", desc: "按固定时间间隔自动触发" },
  { id: "userAction", name: "用户操作", icon: "🖱", desc: "点击、输入、选择等用户行为" },
  { id: "apiCallback", name: "API 回调", icon: "🔌", desc: "外部 API 请求完成时回调" },
  { id: "manual", name: "手动触发", icon: "✋", desc: "用户主动点击按钮触发" },
];

/** 5 个动作卡片（单选） */
export const ACTIONS: { id: ActionId; name: string; icon: string; desc: string; color: string }[] = [
  { id: "showMessage", name: "显示消息", icon: "💬", desc: "Toast 提示 / Alert 弹窗", color: "blue" },
  { id: "navigate", name: "跳转页面", icon: "🔀", desc: "导航到其他 Module / 外部链接", color: "purple" },
  { id: "callApi", name: "调用 API", icon: "⚡", desc: "执行 Ontology Action 或接口", color: "green" },
  { id: "updateData", name: "更新数据", icon: "📝", desc: "写入/修改变量或数据集", color: "yellow" },
  { id: "sendNotification", name: "发送通知", icon: "📡", desc: "邮件 / 站内信 / Webhook", color: "red" },
  { id: "openOverlay", name: "打开浮层", icon: "▣", desc: "打开 Overlay / Modal", color: "purple" },
  { id: "exportData", name: "导出数据", icon: "⇩", desc: "导出当前数据集", color: "blue" },
];

/** 触发器 ID → 中文标签 */
export const TRIGGER_LABEL: Record<TriggerId, string> = {
  pageLoad: "页面加载",
  dataChange: "数据变更",
  timer: "定时触发",
  userAction: "用户操作",
  apiCallback: "API 回调",
  manual: "手动触发",
};

/** 动作 ID → 中文标签 */
export const ACTION_LABEL: Record<ActionId, string> = {
  showMessage: "显示消息",
  navigate: "跳转页面",
  callApi: "调用 API",
  updateData: "更新数据",
  sendNotification: "发送通知",
  openOverlay: "打开浮层",
  exportData: "导出数据",
};

/** 状态 ID → 中文标签 + 颜色 */
export const STATUS_META: Record<EventStatus, { label: string; bg: string; color: string }> = {
  active: { label: "运行中", bg: "#D1FAE5", color: "#065F47" },
  draft: { label: "草稿", bg: "#FEF3C7", color: "#92400E" },
  paused: { label: "已暂停", bg: "#F3F4F6", color: "#6B7280" },
};

/** 根据触发器 + 动作组合，生成动态参数字段定义（纯函数，便于测试）*/
export type ParamField = {
  key: string;
  label: string;
  placeholder: string;
  required: boolean;
  type: "text" | "number" | "select";
  options?: { value: string; label: string }[];
};

export function getParamFields(triggerId: TriggerId | null, actionId: ActionId | null): ParamField[] {
  const fields: ParamField[] = [];

  /* 触发器相关参数 */
  if (triggerId === "timer") {
    fields.push({ key: "interval", label: "触发间隔（秒）", placeholder: "60", required: true, type: "number" });
  }
  if (triggerId === "userAction") {
    fields.push({
      key: "eventType",
      label: "用户事件类型",
      placeholder: "",
      required: true,
      type: "select",
      options: [
        { value: "click", label: "click（点击）" },
        { value: "change", label: "change（值变化）" },
        { value: "submit", label: "submit（提交）" },
      ],
    });
    fields.push({ key: "widgetId", label: "绑定 Widget", placeholder: "w_button_assign", required: true, type: "text" });
  }
  if (triggerId === "apiCallback") {
    fields.push({ key: "apiEndpoint", label: "API 端点", placeholder: "/v1/orders/{id}/assign", required: true, type: "text" });
  }
  if (triggerId === "dataChange") {
    fields.push({ key: "variableId", label: "变更变量", placeholder: "orders", required: true, type: "text" });
  }

  /* 动作相关参数 */
  if (actionId === "showMessage") {
    fields.push({
      key: "messageType",
      label: "消息类型",
      placeholder: "",
      required: true,
      type: "select",
      options: [
        { value: "toast", label: "Toast 轻提示" },
        { value: "alert", label: "Alert 弹窗" },
        { value: "banner", label: "Banner 横幅" },
      ],
    });
    fields.push({ key: "messageContent", label: "消息内容", placeholder: "订单已创建", required: true, type: "text" });
  }
  if (actionId === "navigate") {
    fields.push({ key: "targetRoute", label: "目标路由", placeholder: "/orders/{row.id}", required: true, type: "text" });
    fields.push({
      key: "openIn",
      label: "打开方式",
      placeholder: "",
      required: false,
      type: "select",
      options: [
        { value: "self", label: "当前页" },
        { value: "tab", label: "新标签页" },
        { value: "modal", label: "模态框" },
      ],
    });
  }
  if (actionId === "callApi") {
    fields.push({ key: "apiAction", label: "Action 标识", placeholder: "assignWorkOrder", required: true, type: "text" });
    fields.push({ key: "payload", label: "请求参数（JSON）", placeholder: '{"orderId": "${row.id}"}', required: false, type: "text" });
  }
  if (actionId === "updateData") {
    fields.push({ key: "targetVar", label: "目标变量", placeholder: "selectedWorkOrderId", required: true, type: "text" });
    fields.push({ key: "valueExpr", label: "赋值表达式", placeholder: "${row.id} 或固定值", required: true, type: "text" });
  }
  if (actionId === "sendNotification") {
    fields.push({
      key: "channel",
      label: "通知渠道",
      placeholder: "",
      required: true,
      type: "select",
      options: [
        { value: "email", label: "邮件" },
        { value: "inApp", label: "站内信" },
        { value: "webhook", label: "Webhook" },
      ],
    });
    fields.push({ key: "recipient", label: "接收方", placeholder: "ops-team 或 user@com", required: true, type: "text" });
  }
  if (actionId === "openOverlay") {
    fields.push({ key: "overlayId", label: "浮层标识", placeholder: "order-detail", required: true, type: "text" });
  }
  if (actionId === "exportData") {
    fields.push({ key: "datasetId", label: "数据集标识", placeholder: "orders", required: true, type: "text" });
  }

  return fields;
}

/** 根据参数生成幂等键（纯函数，便于测试 · 对齐 ACT-07）*/
export function buildIdempotencyKey(
  actionId: ActionId | null,
  widgetId?: string,
  params?: Record<string, string>,
): string {
  if (!actionId) return "";
  const base = actionId;
  const widget = widgetId || "global";
  const paramHash = params
    ? Object.values(params).join("_").slice(0, 16)
    : "";
  return `${base}:${widget}:${paramHash || "auto"}`;
}

/** 校验向导每一步是否可继续（纯函数，便于测试）*/
export function canProceed(
  step: number,
  data: { name: string; triggerId: TriggerId | null; actionId: ActionId | null; params: Record<string, string> },
): boolean {
  if (step === 1) return data.name.trim().length > 0;
  if (step === 2) return data.triggerId !== null;
  if (step === 3) return data.actionId !== null;
  if (step === 4) {
    const fields = getParamFields(data.triggerId, data.actionId);
    return fields.every((f) => !f.required || (data.params[f.key] || "").trim().length > 0);
  }
  return true;
}

const TRIGGER_API_TO_UI: Record<string, TriggerId> = {
  on_load: "pageLoad",
  on_change: "dataChange",
  interval: "timer",
  on_click: "userAction",
  on_select: "userAction",
  custom: "manual",
};

const ACTION_API_TO_UI: Record<string, ActionId> = {
  show_message: "showMessage",
  show_notification: "showMessage",
  navigate: "navigate",
  call_function: "callApi",
  query: "callApi",
  set_variable: "updateData",
  open_overlay: "openOverlay",
  export_data: "exportData",
};

export function apiEventToEventItem(item: ModuleEventApiItem): EventItem {
  const triggerType = String(item.trigger?.type || "pageLoad");
  const actionType = String(item.action?.type || "showMessage");
  const triggerId = TRIGGERS.some((entry) => entry.id === triggerType)
    ? triggerType as TriggerId
    : TRIGGER_API_TO_UI[triggerType];
  const savedUiAction = String(item.action?.uiType || "");
  const actionId = ACTIONS.some((entry) => entry.id === savedUiAction)
    ? savedUiAction as ActionId
    : ACTIONS.some((entry) => entry.id === actionType)
      ? actionType as ActionId
      : ACTION_API_TO_UI[actionType];
  if (!triggerId) throw new Error(`不支持的事件触发器类型：${triggerType}`);
  if (!actionId) throw new Error(`不支持的事件动作类型：${actionType}`);
  const triggerParams: Record<string, string> = { ...(item.trigger?.params || {}) };
  if (!item.trigger?.params) {
    for (const [key, value] of Object.entries(item.trigger || {})) {
      if (key !== "type" && typeof value === "string") triggerParams[key] = value;
    }
  }
  const actionParams: Record<string, string> = { ...(item.action?.params || {}) };
  for (const [key, value] of Object.entries(item.action || {})) {
    if (!["type", "params", "description", "idempotent", "idempotencyKey", "uiType"].includes(key) && typeof value === "string") {
      actionParams[key] = value;
    }
  }
  return {
    id: item.id,
    name: item.name || item.id,
    description: String(item.action?.description || ""),
    triggerId,
    actionId,
    params: { ...triggerParams, ...actionParams },
    status: item.enabled === false ? "paused" : "active",
    idempotent: item.action?.idempotent === true,
    idempotencyKey: item.action?.idempotencyKey,
  };
}

export function eventCreatePayload(input: {
  name: string;
  description: string;
  triggerId: TriggerId;
  actionId: ActionId;
  params: Record<string, string>;
  idempotent: boolean;
  idempotencyKey?: string;
}) {
  const triggerType = input.triggerId === "pageLoad"
    ? "on_load"
    : input.triggerId === "dataChange"
      ? "on_change"
      : input.triggerId === "timer"
        ? "interval"
        : input.triggerId === "userAction"
          ? input.params.eventType === "change" ? "on_change" : "on_click"
          : "custom";
  const actionType: Record<ActionId, string> = {
    showMessage: "show_notification",
    navigate: "navigate",
    callApi: "call_function",
    updateData: "set_variable",
    sendNotification: "show_notification",
    openOverlay: "open_overlay",
    exportData: "export_data",
  };
  const target = input.actionId === "navigate"
    ? input.params.targetRoute
    : input.actionId === "callApi"
      ? input.params.apiAction
      : input.actionId === "updateData"
        ? input.params.targetVar
        : input.actionId === "openOverlay"
          ? input.params.overlayId
          : input.actionId === "exportData"
            ? input.params.datasetId
            : undefined;
  const triggerRequired = triggerType === "on_click"
    ? input.params.widgetId
    : triggerType === "on_change"
      ? input.params.variableId || input.params.widgetId
      : triggerType === "interval"
        ? input.params.interval
        : triggerType === "custom"
          ? input.params.apiEndpoint || input.params.eventType || "manual"
          : "ok";
  if (!String(triggerRequired || "").trim()) throw new Error(`触发器 ${triggerType} 缺少 catalog 必填字段`);
  if (triggerType === "interval" && !Number.isFinite(Number(input.params.interval))) {
    throw new Error("触发器 interval 的 value 必须是数值");
  }
  if (["navigate", "call_function", "set_variable", "open_overlay"].includes(actionType[input.actionId]) && !target?.trim()) {
    throw new Error(`动作 ${actionType[input.actionId]} 缺少 catalog 必填 target`);
  }
  return {
    name: input.name,
    trigger: {
      type: triggerType,
      params: input.params,
      ...(triggerType === "on_click" ? { widgetId: input.params.widgetId || "" } : {}),
      ...(triggerType === "on_change" ? { variableId: input.params.variableId || input.params.widgetId || "" } : {}),
      ...(triggerType === "interval" ? { value: Number(input.params.interval), unit: "seconds" } : {}),
      ...(triggerType === "custom" ? { expression: input.params.apiEndpoint || input.params.eventType || "manual" } : {}),
    },
    action: {
      type: actionType[input.actionId],
      uiType: input.actionId,
      params: input.params,
      ...(target ? { target } : {}),
      description: input.description,
      idempotent: input.idempotent,
      idempotencyKey: input.idempotencyKey,
    },
    enabled: false,
  };
}

export const MOCK_EVENTS: EventItem[] = [
  {
    id: "e1",
    name: "选中订单写入变量",
    description: "表格行选中时，将 orderId 写入全局变量",
    triggerId: "userAction",
    actionId: "updateData",
    params: { eventType: "click", widgetId: "w_table_orders", targetVar: "selectedWorkOrderId", valueExpr: "${row.id}" },
    status: "active",
    idempotent: true,
    idempotencyKey: "updateData:w_table_orders:click_${row.id}",
  },
  {
    id: "e2",
    name: "派单按钮调用 Action",
    description: "点击派单按钮触发 assignWorkOrder",
    triggerId: "userAction",
    actionId: "callApi",
    params: { eventType: "click", widgetId: "w_button_assign", apiAction: "assignWorkOrder", payload: '{"orderId":"${selectedWorkOrderId}"}' },
    status: "active",
    idempotent: true,
    idempotencyKey: "callApi:w_button_assign:assignWorkOrder",
  },
  {
    id: "e3",
    name: "筛选器变更刷新数据",
    description: "国家筛选器变化时刷新订单数据集",
    triggerId: "dataChange",
    actionId: "updateData",
    params: { targetVar: "inboxFilter", valueExpr: "${filter.value}" },
    status: "active",
    idempotent: false,
  },
];

/* ============================================================================
 * Page Component
 * ========================================================================== */

export function EventsPage() {
  const [modules, setModules] = useState<Array<{ id: string; name?: string }>>([]);
  const [moduleId, setModuleId] = useState("");
  const [moduleLoading, setModuleLoading] = useState(true);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");

  /* 向导状态 */
  const [wizardOpen, setWizardOpen] = useState(false);
  const [step, setStep] = useState(1);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [triggerId, setTriggerId] = useState<TriggerId | null>(null);
  const [actionId, setActionId] = useState<ActionId | null>(null);
  const [params, setParams] = useState<Record<string, string>>({});
  const [enableIdempotency, setEnableIdempotency] = useState(true);
  const [idempotencyKey, setIdempotencyKey] = useState("");

  useEffect(() => {
    let cancelled = false;
    setModuleLoading(true);
    apiGet<{ items?: Array<{ id: string; name?: string }> }>("/v1/modules")
      .then((result) => {
        if (cancelled) return;
        const items = (result.items || []).filter((item) => item.id);
        setModules(items);
        setModuleId((current) => current && items.some((item) => item.id === current) ? current : items[0]?.id || "");
      })
      .catch((e) => {
        if (!cancelled) setErr(`应用目录加载失败：${String((e as Error).message || e)}`);
      })
      .finally(() => {
        if (!cancelled) setModuleLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const reloadEvents = useCallback(async () => {
    if (!moduleId) {
      setEvents([]);
      setLoading(false);
      return [];
    }
    setLoading(true);
    setErr("");
    try {
      const res = await apiGet<{ items?: ModuleEventApiItem[] }>(`/v1/modules/${moduleId}/events`);
      const mapped = (res.items || []).map(apiEventToEventItem);
      setEvents(mapped);
      return mapped;
    } catch (e) {
      setErr(`事件列表加载失败：${String((e as Error).message || e)}`);
      throw e;
    } finally {
      setLoading(false);
    }
  }, [moduleId]);

  useEffect(() => {
    if (moduleLoading) return;
    void reloadEvents().catch(() => undefined);
  }, [moduleLoading, reloadEvents]);

  function openWizard() {
    if (!moduleId) return;
    setWizardOpen(true);
    setStep(1);
    setName("");
    setDescription("");
    setTriggerId(null);
    setActionId(null);
    setParams({});
    setEnableIdempotency(true);
    setIdempotencyKey("");
  }

  function closeWizard() {
    setWizardOpen(false);
  }

  function canNext() {
    return canProceed(step, { name, triggerId, actionId, params });
  }

  function nextStep() {
    if (!canNext()) return;
    setStep((s) => Math.min(s + 1, 5));
  }

  function prevStep() {
    setStep((s) => Math.max(s - 1, 1));
  }

  async function confirmCreate() {
    const key = enableIdempotency
      ? (idempotencyKey || buildIdempotencyKey(actionId, params.widgetId, params))
      : undefined;
    setBusyId("create");
    setErr("");
    setMsg("");
    try {
      const created = await apiPost<{ ok?: boolean; item?: ModuleEventApiItem }>(`/v1/modules/${moduleId}/events`, eventCreatePayload({
        name: name.trim(),
        description: description.trim(),
        triggerId: triggerId!,
        actionId: actionId!,
        params,
        idempotent: enableIdempotency,
        idempotencyKey: key,
      }));
      if (created.ok !== true || !created.item?.id || (created.item.moduleId && created.item.moduleId !== moduleId)) {
        throw new Error("创建 API 未返回可信 ok/item");
      }
      const fresh = await reloadEvents();
      if (!fresh.some((event) => event.id === created.item!.id)) {
        throw new Error("创建后重读未找到新事件");
      }
      setMsg(`事件“${name.trim()}”已创建并从服务端重读`);
      closeWizard();
    } catch (e) {
      setErr(`创建事件失败：${String((e as Error).message || e)}`);
    } finally {
      setBusyId(null);
    }
  }

  async function toggleStatus(event: EventItem) {
    const enabled = event.status !== "active";
    setBusyId(event.id);
    setErr("");
    setMsg("");
    try {
      const updated = await apiPut<{ ok?: boolean; item?: ModuleEventApiItem }>(
        `/v1/modules/${moduleId}/events/${encodeURIComponent(event.id)}`,
        { enabled },
      );
      if (updated.ok !== true || updated.item?.id !== event.id || updated.item.enabled !== enabled) {
        throw new Error("更新 API 回包与目标状态不一致");
      }
      const fresh = await reloadEvents();
      const reloaded = fresh.find((item) => item.id === event.id);
      if (!reloaded || (reloaded.status === "active") !== enabled) {
        throw new Error("更新后重读状态不一致");
      }
      setMsg(`事件“${event.name}”已${enabled ? "启用" : "暂停"}`);
    } catch (e) {
      setErr(`${enabled ? "启用" : "暂停"}事件失败：${String((e as Error).message || e)}`);
    } finally {
      setBusyId(null);
    }
  }

  async function deleteEvent(event: EventItem) {
    setBusyId(event.id);
    setErr("");
    setMsg("");
    try {
      const deleted = await apiDelete<{ ok?: boolean }>(`/v1/modules/${moduleId}/events/${encodeURIComponent(event.id)}`);
      if (deleted.ok !== true) throw new Error("删除 API 未返回 ok=true");
      const fresh = await reloadEvents();
      if (fresh.some((item) => item.id === event.id)) throw new Error("删除后重读仍存在该事件");
      setMsg(`事件“${event.name}”已删除`);
    } catch (e) {
      setErr(`删除事件失败：${String((e as Error).message || e)}`);
    } finally {
      setBusyId(null);
    }
  }

  /* 动态参数字段（step 4 用）*/
  const paramFields = useMemo(() => getParamFields(triggerId, actionId), [triggerId, actionId]);

  return (
    <PageChrome title="事件配置" lede="当前应用 · 组件事件、业务动作与重复提交保护">
      <div className="ev-page">
        {/* 226 G4：无页内搜索；表头侧放 + 添加事件（对齐稿） */}
        <BpToolbar
          actions={
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <label style={{ fontSize: 12, color: "#6B7280" }}>
                目标应用{" "}
                <select
                  aria-label="事件目标应用"
                  value={moduleId}
                  disabled={moduleLoading || modules.length === 0}
                  onChange={(event) => {
                    setEvents([]);
                    setModuleId(event.target.value);
                    setWizardOpen(false);
                  }}
                >
                  {modules.length === 0 && <option value="">当前工作区暂无应用</option>}
                  {modules.map((item) => <option key={item.id} value={item.id}>{item.name || "未命名应用"}</option>)}
                </select>
              </label>
              <button type="button" className="p-btn p-btn-primary p-btn-sm" onClick={openWizard} disabled={!moduleId || moduleLoading}>
                + 添加事件
              </button>
            </div>
          }
          count={events.length}
        />

        {msg && <p className="bp-prop-ok" role="status">{msg}</p>}
        {err && <p className="error" role="alert">{err}</p>}

        {/* === 上半区：事件列表表格 === */}
        <div style={{ background: "var(--aos-surface)", borderRadius: 2, border: "1px solid var(--aos-border)", marginTop: 16, overflow: "hidden" }}>
          <div style={{ padding: "12px 16px", borderBottom: "1px solid #F3F4F6", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: "#111827" }}>已注册事件（{events.length}）</span>
            {loading && <span style={{ fontSize: 11, color: "#9CA3AF" }}>加载中…</span>}
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: "2px solid #E5E7EB", background: "#FAFAFA" }}>
                <th style={{ textAlign: "left", padding: "10px 16px", fontSize: 11, fontWeight: 600, color: "#6B7280", textTransform: "uppercase", letterSpacing: "0.05em" }}>事件名</th>
                <th style={{ textAlign: "left", padding: "10px 16px", fontSize: 11, fontWeight: 600, color: "#6B7280", textTransform: "uppercase", letterSpacing: "0.05em" }}>触发器</th>
                <th style={{ textAlign: "left", padding: "10px 16px", fontSize: 11, fontWeight: 600, color: "#6B7280", textTransform: "uppercase", letterSpacing: "0.05em" }}>动作</th>
                <th style={{ textAlign: "left", padding: "10px 16px", fontSize: 11, fontWeight: 600, color: "#6B7280", textTransform: "uppercase", letterSpacing: "0.05em" }}>状态</th>
                <th style={{ textAlign: "right", padding: "10px 16px", fontSize: 11, fontWeight: 600, color: "#6B7280", textTransform: "uppercase", letterSpacing: "0.05em" }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => {
                const sm = STATUS_META[e.status];
                return (
                  <tr key={e.id} style={{ borderBottom: "1px solid #F3F4F6", background: e.isNew ? "#EFF6FF" : undefined }}>
                    <td style={{ padding: "12px 16px" }}>
                      <div style={{ fontWeight: 500, color: "#111827" }}>
                        {e.name}
                        {e.isNew && (
                          <span style={{ fontSize: 9, background: "#DBEAFE", color: "#1E40AF", padding: "1px 4px", borderRadius: 2, marginLeft: 6 }}>新增</span>
                        )}
                      </div>
                      {e.description && <div style={{ fontSize: 11, color: "#9CA3AF", marginTop: 2 }}>{e.description}</div>}
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      <span style={{ fontSize: 12, color: "var(--aos-accent)" }}>{TRIGGER_LABEL[e.triggerId]}</span>
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      <span style={{ fontSize: 12, color: "#10B981" }}>{ACTION_LABEL[e.actionId]}</span>
                      {e.idempotent && (
                        <span style={{ fontSize: 9, background: "#FEF3C7", color: "#92400E", padding: "1px 4px", borderRadius: 2, marginLeft: 4 }} title={e.idempotencyKey}>
                          幂等
                        </span>
                      )}
                    </td>
                    <td style={{ padding: "12px 16px" }}>
                      <span style={{ background: sm.bg, color: sm.color, padding: "2px 8px", borderRadius: 2, fontSize: 11, fontWeight: 500 }}>
                        {sm.label}
                      </span>
                    </td>
                    <td style={{ padding: "12px 16px", textAlign: "right" }}>
                      <button
                        disabled={busyId === e.id}
                        onClick={() => void toggleStatus(e)}
                        style={{
                          fontSize: 11,
                          color: e.status === "active" ? "#9CA3AF" : "#10B981",
                          background: "none",
                          border: "none",
                          cursor: "pointer",
                          marginRight: 8,
                        }}
                      >
                        {e.status === "active" ? "暂停" : "启用"}
                      </button>
                      <button
                        disabled={busyId === e.id}
                        onClick={() => void deleteEvent(e)}
                        style={{
                          fontSize: 11,
                          color: "#EF4444",
                          background: "none",
                          border: "none",
                          cursor: "pointer",
                        }}
                      >
                        删除
                      </button>
                    </td>
                  </tr>
                );
              })}
              {events.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ padding: 32, textAlign: "center", color: "#9CA3AF", fontSize: 13 }}>
                    {loading || moduleLoading
                      ? "加载事件列表中…"
                      : moduleId
                        ? "当前应用暂无事件，可使用右上角“添加事件”创建停用草稿"
                        : "请先新建或选择真实应用，再配置事件"}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* 幂等护栏提示 */}
        <div style={{ marginTop: 12, padding: 12, borderRadius: 2, background: "var(--aos-amber-bg)", border: "1px solid var(--aos-amber-border)", fontSize: 12 }}>
          <strong style={{ color: "#92400E" }}>重复提交保护：</strong>
          <span style={{ color: "#78350F" }}>写操作事件（调用服务或更新数据）须配置唯一键，防止双击或重试导致重复提交。</span>
        </div>

        {moduleId && (
          <details style={{ marginTop: 12, fontSize: 11, color: "#6B7280" }}>
            <summary style={{ cursor: "pointer" }}>查看事件接口审计信息</summary>
            <div style={{ marginTop: 6 }}>/v1/modules/{moduleId}/events</div>
          </details>
        )}

        {/* === 下半区：5 步创建向导 === */}
        {wizardOpen && (
          <div
            style={{
              marginTop: 16,
              background: "#fff",
              borderRadius: 2,
              border: "1px solid #E5E7EB",
              overflow: "hidden",
            }}
          >
            {/* 向导头部 */}
            <div style={{ padding: "16px 20px", borderBottom: "1px solid #E5E7EB", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: "#111827" }}>创建事件绑定 · 5 步向导</div>
                <div style={{ fontSize: 11, color: "#9CA3AF", marginTop: 2 }}>名称 → 触发器 → 动作 → 参数 → 确认</div>
              </div>
              <button onClick={closeWizard} style={{ background: "none", border: "none", cursor: "pointer", color: "#9CA3AF", fontSize: 16 }}>✕</button>
            </div>

            {/* 步骤指示器 */}
            <div style={{ padding: "12px 20px", borderBottom: "1px solid #F3F4F6", display: "flex", alignItems: "center", gap: 4 }}>
              {[
                { n: 1, label: "名称" },
                { n: 2, label: "触发器" },
                { n: 3, label: "动作" },
                { n: 4, label: "参数" },
                { n: 5, label: "确认" },
              ].map((s, idx) => {
                const isActive = step >= s.n;
                return (
                  <div key={s.n} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                    <span style={{
                      width: 22,
                      height: 22,
                      borderRadius: "50%",
                      background: isActive ? "var(--aos-accent)" : "#E5E7EB",
                      color: isActive ? "#fff" : "#9CA3AF",
                      fontSize: 11,
                      fontWeight: 600,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}>
                      {step > s.n ? "✓" : s.n}
                    </span>
                    <span style={{
                      fontSize: 11,
                      color: isActive ? "var(--aos-accent)" : "#9CA3AF",
                      fontWeight: step === s.n ? 600 : 400,
                      marginRight: 4,
                    }}>
                      {s.label}
                    </span>
                    {idx < 4 && <span style={{ color: "#D1D5DB", fontSize: 10 }}>→</span>}
                  </div>
                );
              })}
            </div>

            {/* 步骤内容 */}
            <div style={{ padding: "20px", minHeight: 240 }}>
              {/* Step 1：事件名称 + 描述 */}
              {step === 1 && (
                <div className="st-stack-sm">
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 600, color: "#374151", display: "block", marginBottom: 6 }}>
                      事件名称 <span style={{ color: "#EF4444" }}>*</span>
                    </label>
                    <input
                      type="text"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="如：选中订单写入变量"
                      style={inputStyle(name.trim().length === 0)}
                      autoFocus
                    />
                  </div>
                  <div>
                    <label style={{ fontSize: 13, fontWeight: 600, color: "#374151", display: "block", marginBottom: 6 }}>描述（选填）</label>
                    <textarea
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      placeholder="说明这个事件的作用…"
                      style={{ ...inputStyle(false), minHeight: 60, resize: "vertical" }}
                    />
                  </div>
                </div>
              )}

              {/* Step 2：选择触发器（6 卡片单选）*/}
              {step === 2 && (
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 12 }}>选择触发器（单选）</div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
                    {TRIGGERS.map((t) => (
                      <div
                        key={t.id}
                        onClick={() => setTriggerId(t.id)}
                        style={{
                          padding: 14,
                          borderRadius: 2,
                          border: `1.5px solid ${triggerId === t.id ? "var(--aos-accent)" : "#E5E7EB"}`,
                          background: triggerId === t.id ? "#EFF6FF" : "#fff",
                          cursor: "pointer",
                          transition: "all 0.15s",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                          <span style={{ fontSize: 18 }}>{t.icon}</span>
                          <span style={{ fontSize: 13, fontWeight: 600, color: triggerId === t.id ? "var(--aos-accent)" : "#111827" }}>{t.name}</span>
                          {triggerId === t.id && <span style={{ marginLeft: "auto", color: "var(--aos-accent)", fontSize: 14 }}>●</span>}
                        </div>
                        <div style={{ fontSize: 11, color: "#6B7280" }}>{t.desc}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Step 3：选择动作（5 卡片单选）*/}
              {step === 3 && (
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 12 }}>选择动作（单选）</div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                    {ACTIONS.map((a) => (
                      <div
                        key={a.id}
                        onClick={() => setActionId(a.id)}
                        style={{
                          padding: 12,
                          borderRadius: 2,
                          border: `1.5px solid ${actionId === a.id ? "#10B981" : "#E5E7EB"}`,
                          background: actionId === a.id ? "#ECFDF5" : "#fff",
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          gap: 10,
                        }}
                      >
                        <span style={{
                          width: 32,
                          height: 32,
                          borderRadius: 2,
                          background: actionBg(a.color),
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontSize: 16,
                        }}>
                          {a.icon}
                        </span>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 13, fontWeight: 600, color: actionId === a.id ? "#10B981" : "#111827" }}>{a.name}</div>
                          <div style={{ fontSize: 10, color: "#6B7280" }}>{a.desc}</div>
                        </div>
                        {actionId === a.id && <span style={{ color: "#10B981", fontSize: 14 }}>●</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Step 4：动态参数表单 */}
              {step === 4 && (
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 12 }}>
                    动态参数配置
                    <span style={{ marginLeft: 8, fontSize: 11, color: "#9CA3AF" }}>
                      （基于「{TRIGGER_LABEL[triggerId!]}」+「{ACTION_LABEL[actionId!]}」生成）
                    </span>
                  </div>

                  {paramFields.length === 0 ? (
                    <div style={{ padding: 20, textAlign: "center", color: "#9CA3AF", fontSize: 12 }}>
                      当前触发器 + 动作组合无需额外参数
                    </div>
                  ) : (
                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                      {paramFields.map((f) => (
                        <div key={f.key}>
                          <label style={{ fontSize: 12, fontWeight: 500, color: "#374151", display: "block", marginBottom: 4 }}>
                            {f.label} {f.required && <span style={{ color: "#EF4444" }}>*</span>}
                          </label>
                          {f.type === "select" ? (
                            <select
                              value={params[f.key] || ""}
                              onChange={(e) => setParams((p) => ({ ...p, [f.key]: e.target.value }))}
                              style={inputStyle(false)}
                            >
                              <option value="">请选择…</option>
                              {f.options!.map((o) => (
                                <option key={o.value} value={o.value}>{o.label}</option>
                              ))}
                            </select>
                          ) : (
                            <input
                              type={f.type === "number" ? "number" : "text"}
                              value={params[f.key] || ""}
                              onChange={(e) => setParams((p) => ({ ...p, [f.key]: e.target.value }))}
                              placeholder={f.placeholder}
                              style={inputStyle(f.required && !(params[f.key] || "").trim())}
                            />
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* 幂等键配置（写操作必填）*/}
                  {(actionId === "callApi" || actionId === "updateData") && (
                    <div style={{ marginTop: 16, padding: 12, borderRadius: 2, background: "var(--aos-amber-bg)", border: "1px solid var(--aos-amber-border)" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                        <input
                          type="checkbox"
                          checked={enableIdempotency}
                          onChange={(e) => setEnableIdempotency(e.target.checked)}
                          style={{ accentColor: "#F59E0B", width: 14, height: 14 }}
                        />
                        <label style={{ fontSize: 12, fontWeight: 600, color: "#92400E", cursor: "pointer" }}>
                          启用幂等键（写操作推荐）
                        </label>
                      </div>
                      <input
                        type="text"
                        value={idempotencyKey}
                        onChange={(e) => setIdempotencyKey(e.target.value)}
                        placeholder={buildIdempotencyKey(actionId, params.widgetId, params)}
                        disabled={!enableIdempotency}
                        style={{
                          ...inputStyle(false),
                          fontFamily: "monospace",
                          fontSize: 11,
                          background: enableIdempotency ? "#FFFEF7" : "#F3F4F6",
                          opacity: enableIdempotency ? 1 : 0.5,
                        }}
                      />
                    </div>
                  )}
                </div>
              )}

              {/* Step 5：预览确认 */}
              {step === 5 && (
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "#374151", marginBottom: 12 }}>事件配置摘要</div>
                  <div style={{
                    padding: 16,
                    borderRadius: 2,
                    background: "#F9FAFB",
                    border: "1px solid #E5E7EB",
                    fontSize: 12,
                    lineHeight: 1.8,
                  }}>
                    <div><strong style={{ color: "#374151", display: "inline-block", width: 100 }}>事件名称：</strong><span style={{ color: "#111827", fontWeight: 600 }}>{name}</span></div>
                    {description && <div><strong style={{ color: "#374151", display: "inline-block", width: 100 }}>描述：</strong><span style={{ color: "#6B7280" }}>{description}</span></div>}
                    <div><strong style={{ color: "#374151", display: "inline-block", width: 100 }}>触发器：</strong><span style={{ color: "var(--aos-accent)", fontWeight: 600 }}>{TRIGGER_LABEL[triggerId!]}</span></div>
                    <div><strong style={{ color: "#374151", display: "inline-block", width: 100 }}>动作：</strong><span style={{ color: "#10B981", fontWeight: 600 }}>{ACTION_LABEL[actionId!]}</span></div>
                    {paramFields.length > 0 && (
                      <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid #E5E7EB" }}>
                        <strong style={{ color: "#374151" }}>参数：</strong>
                        <div style={{ marginTop: 4, paddingLeft: 100, fontFamily: "monospace", fontSize: 11, color: "#6B7280" }}>
                          {paramFields.map((f) => (
                            <div key={f.key}>{f.label}: <span style={{ color: "#374151" }}>{params[f.key] || "(空)"}</span></div>
                          ))}
                        </div>
                      </div>
                    )}
                    {(actionId === "callApi" || actionId === "updateData") && (
                      <div>
                        <strong style={{ color: "#374151", display: "inline-block", width: 100 }}>幂等键：</strong>
                        {enableIdempotency ? (
                          <span style={{ color: "#92400E", fontFamily: "monospace", fontSize: 11 }}>
                            {idempotencyKey || buildIdempotencyKey(actionId, params.widgetId, params)}
                          </span>
                        ) : (
                          <span style={{ color: "#EF4444" }}>未启用（写操作不推荐）</span>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* 向导底部按钮 */}
            <div style={{ padding: "12px 20px", borderTop: "1px solid #E5E7EB", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                {step > 1 && (
                  <button onClick={prevStep} style={btnSecondary}>
                    ← 上一步
                  </button>
                )}
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button onClick={closeWizard} style={btnSecondary}>取消</button>
                {step < 5 ? (
                  <button
                    onClick={nextStep}
                    disabled={!canNext()}
                    style={canNext() ? btnPrimary : { ...btnPrimary, background: "#E5E7EB", color: "#9CA3AF", cursor: "not-allowed" }}
                  >
                    下一步 →
                  </button>
                ) : (
                  <button disabled={busyId === "create"} onClick={() => void confirmCreate()} style={btnPrimary}>
                    {busyId === "create" ? "创建中…" : "✓ 完成创建"}
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </PageChrome>
  );
}

/* ============================================================================
 * 样式常量 & 辅助函数
 * ========================================================================== */

const inputStyle = (invalid: boolean): React.CSSProperties => ({
  width: "100%",
  padding: "8px 10px",
  border: `1px solid ${invalid ? "#EF4444" : "#D1D5DB"}`,
  borderRadius: 2,
  fontSize: 13,
  color: "#374151",
  fontFamily: "inherit",
  boxSizing: "border-box" as const,
  outline: "none",
});

const btnPrimary: React.CSSProperties = {
  padding: "8px 18px",
  fontSize: 12,
  fontWeight: 600,
  border: "none",
  borderRadius: 2,
  background: "var(--aos-accent)",
  color: "#fff",
  cursor: "pointer",
};

const btnSecondary: React.CSSProperties = {
  padding: "8px 18px",
  fontSize: 12,
  fontWeight: 500,
  border: "1px solid #D1D5DB",
  borderRadius: 2,
  background: "#fff",
  color: "#374151",
  cursor: "pointer",
};

function actionBg(color: string): string {
  const map: Record<string, string> = {
    blue: "#EFF6FF",
    green: "#ECFDF5",
    yellow: "#FFFBEB",
    purple: "#F3E8FF",
    red: "#FEE2E2",
  };
  return map[color] || "#F3F4F6";
}
