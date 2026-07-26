import { useState } from "react";
import { PageChrome } from "../../components/PageChrome";

type EventItem = {
  id: string;
  trigger: string;
  action: string;
  targetVar: string;
  idempotent: boolean;
  idempotencyKey?: string;
  isNew?: boolean;
};

const INITIAL_EVENTS: EventItem[] = [
  { id: "e1", trigger: "表格行选中 onSelect", action: "写入变量", targetVar: "selectedWorkOrderId", idempotent: true },
  { id: "e2", trigger: "按钮「派单」onClick", action: "调用 Action", targetVar: "assignWorkOrder", idempotent: true, idempotencyKey: "idempotencyKey" },
  { id: "e3", trigger: "筛选器 onChange", action: "刷新数据集", targetVar: "inboxFilter", idempotent: false },
];

const TRIGGER_OPTIONS = [
  { id: "onPageLoad", name: "onPageLoad", icon: "🕐", desc: "页面首次渲染时触发" },
  { id: "onRowClick", name: "onRowClick", icon: "🖱", desc: "表格行点击时触发" },
  { id: "onWidgetClick", name: "onWidgetClick", icon: "📊", desc: "Widget 点击时触发" },
  { id: "onFilterChange", name: "onFilterChange", icon: "🔍", desc: "筛选器值变化时触发" },
  { id: "onTimer", name: "onTimer", icon: "⏰", desc: "定时触发（间隔可配）" },
  { id: "onCustom", name: "自定义事件", icon: "⚙", desc: "监听其他 Module 发出的事件" },
];

const ACTION_OPTIONS = [
  { id: "write_variable", name: "写入变量", icon: "📝", desc: "将触发器数据写入指定变量", color: "blue" },
  { id: "call_action", name: "调用 Action", icon: "⚡", desc: "触发 Ontology Action（如 assignWorkOrder）", color: "green" },
  { id: "refresh_dataset", name: "刷新数据集", icon: "🔄", desc: "重新加载绑定的 ObjectSet 或数据查询", color: "yellow" },
  { id: "navigate", name: "导航", icon: "🔀", desc: "跳转到其他 Module 或外部链接", color: "purple" },
  { id: "open_modal", name: "打开模态框", icon: "🔲", desc: "弹出指定模态框组件", color: "red" },
  { id: "emit_event", name: "发送事件", icon: "📡", desc: "向其他 Module 发出跨组件事件", color: "indigo" },
];

const WIDGET_OPTIONS = [
  { value: "w_table_orders", label: "w_table_orders（订单表格）" },
  { value: "w_chart_revenue", label: "w_chart_revenue（收入图表）" },
  { value: "w_filter_country", label: "w_filter_country（国家筛选器）" },
  { value: "w_button_assign", label: "w_button_assign（派单按钮）" },
  { value: "global", label: "全局（不绑定特定 Widget）" },
];

const ACTION_LABELS: Record<string, string> = {
  write_variable: "写入变量",
  call_action: "调用 Action",
  refresh_dataset: "刷新数据集",
  navigate: "导航",
  open_modal: "打开模态框",
  emit_event: "发送事件",
};

export function EventsPage() {
  const [events, setEvents] = useState<EventItem[]>(INITIAL_EVENTS);
  const [showModal, setShowModal] = useState(false);
  const [currentStep, setCurrentStep] = useState(1);
  const [selectedTrigger, setSelectedTrigger] = useState<string | null>(null);
  const [selectedAction, setSelectedAction] = useState<string | null>(null);
  const [selectedWidget, setSelectedWidget] = useState("");
  const [actionParam, setActionParam] = useState("");
  const [targetVar, setTargetVar] = useState("");
  const [enableIdempotency, setEnableIdempotency] = useState(true);
  const [idempotencyKey, setIdempotencyKey] = useState("");

  function openModal() {
    setShowModal(true);
    setCurrentStep(1);
    setSelectedTrigger(null);
    setSelectedAction(null);
    setSelectedWidget("");
    setActionParam("");
    setTargetVar("");
    setEnableIdempotency(true);
    setIdempotencyKey("");
  }

  function closeModal() {
    setShowModal(false);
  }

  function canGoNext() {
    if (currentStep === 1) return selectedTrigger !== null;
    if (currentStep === 2) return selectedAction !== null;
    return true;
  }

  function nextStep() {
    if (!canGoNext()) return;
    setCurrentStep((s) => Math.min(s + 1, 3));
  }

  function prevStep() {
    setCurrentStep((s) => Math.max(s - 1, 1));
  }

  function confirmAdd() {
    if (!selectedTrigger || !selectedAction) return;
    const newEvent: EventItem = {
      id: `e_${Date.now()}`,
      trigger: selectedTrigger,
      action: ACTION_LABELS[selectedAction] || selectedAction,
      targetVar: targetVar || "—",
      idempotent: enableIdempotency,
      idempotencyKey: enableIdempotency ? (idempotencyKey || "idempotencyKey") : undefined,
      isNew: true,
    };
    setEvents((prev) => [...prev, newEvent]);
    closeModal();
  }

  const actionParamPlaceholders: Record<string, string> = {
    write_variable: "变量名，如 selectedWorkOrderId",
    call_action: "Action ID，如 assignWorkOrder",
    refresh_dataset: "数据集标识，如 covid_cases_dataset",
    navigate: "目标路由，如 /orders/{row.id}",
    open_modal: "模态框 ID，如 orderDetailModal",
    emit_event: "事件名，如 page:loaded",
  };

  return (
    <PageChrome title="Events 配置面板" lede="Widget 事件绑定、变量写入与幂等键配置。">
      <div className="max-w-4xl mx-auto space-y-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Events 配置面板</h1>
          <p className="mt-1 text-sm text-gray-500">Widget 事件绑定、变量写入与幂等键配置。</p>
        </div>

        <div className="rounded-xl border border-blue-600/25 bg-white overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200 flex justify-between items-center">
            <span className="text-sm font-medium text-gray-900">已注册事件</span>
            <button
              type="button"
              className="text-xs text-blue-600 hover:text-blue-700 cursor-pointer bg-transparent border-none"
              onClick={openModal}
            >
              + 添加事件
            </button>
          </div>
          <table className="w-full text-sm">
            <thead className="text-xs text-gray-500 uppercase bg-[rgba(11,14,23,0.5)]">
              <tr>
                <th className="text-left px-4 py-2 font-medium">触发器</th>
                <th className="text-left px-4 py-2 font-medium">动作</th>
                <th className="text-left px-4 py-2 font-medium">目标变量</th>
                <th className="text-left px-4 py-2 font-medium">幂等</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {events.map((e) => (
                <tr key={e.id} style={e.isNew ? { background: "#EFF6FF" } : undefined}>
                  <td className="px-4 py-3 text-gray-900">
                    {e.trigger}
                    {e.isNew && (
                      <span style={{ fontSize: 9, background: "#DBEAFE", color: "#1E40AF", padding: "1px 4px", borderRadius: 3, marginLeft: 6 }}>
                        新增
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-blue-600">{e.action}</td>
                  <td className="px-4 py-3 font-mono text-xs">{e.targetVar}</td>
                  <td className="px-4 py-3 text-xs">
                    {e.idempotent ? (
                      <span style={{ color: "#10B981" }}>
                        ● {e.idempotencyKey || "已启用"}
                      </span>
                    ) : (
                      <span style={{ color: "#9CA3AF" }}>—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="rounded-xl border border-yellow-200 bg-yellow-50 p-4 text-xs">
          <span className="text-yellow-700 font-medium">幂等护栏：</span>
          <span className="text-gray-500">写操作事件须配置 idempotencyKey，防止双击重复提交（对齐 ACT-07）。</span>
        </div>
      </div>

      {showModal && (
        <div
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 100,
            background: "rgba(0,0,0,0.3)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) closeModal();
          }}
        >
          <div
            style={{
              background: "#fff",
              borderRadius: 12,
              width: 640,
              maxWidth: "90vw",
              maxHeight: "85vh",
              display: "flex",
              flexDirection: "column",
              boxShadow: "0 20px 60px rgba(0,0,0,0.15)",
            }}
          >
            <div style={{ padding: "16px 24px", borderBottom: "1px solid #E5E7EB", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: "#111827" }}>添加事件绑定</div>
                <div style={{ fontSize: 11, color: "#6B7280", marginTop: 2 }}>选择触发器 → 配置动作 → 绑定变量 → 设置幂等键</div>
              </div>
              <button
                onClick={closeModal}
                style={{
                  width: 28,
                  height: 28,
                  border: "none",
                  background: "none",
                  cursor: "pointer",
                  color: "#6B7280",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: 4,
                }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                  <path d="M18 6L6 18M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>

            <div style={{ padding: "12px 24px", borderBottom: "1px solid #F3F4F6", display: "flex", alignItems: "center", gap: 6 }}>
              {[1, 2, 3].map((step, idx) => {
                const labels = ["触发器", "动作", "变量与幂等"];
                const isActive = currentStep >= step;
                return (
                  <div key={step} style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <span
                      style={{
                        width: 20,
                        height: 20,
                        borderRadius: "50%",
                        background: isActive ? "#3B82F6" : "#E5E7EB",
                        color: isActive ? "#fff" : "#6B7280",
                        fontSize: 10,
                        fontWeight: 600,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      {step}
                    </span>
                    <span style={{ fontSize: 11, color: isActive ? "#3B82F6" : "#9CA3AF", fontWeight: isActive ? 500 : 400 }}>
                      {labels[idx]}
                    </span>
                    {step < 3 && <span style={{ color: "#D1D5DB", fontSize: 10 }}>─</span>}
                  </div>
                );
              })}
            </div>

            <div style={{ flex: 1, overflowY: "auto", padding: "20px 24px" }}>
              {currentStep === 1 && (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "#374151", marginBottom: 12 }}>选择触发器类型</div>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                    {TRIGGER_OPTIONS.map((t) => (
                      <div
                        key={t.id}
                        onClick={() => setSelectedTrigger(t.id)}
                        style={{
                          padding: 12,
                          borderRadius: 8,
                          border: `1.5px solid ${selectedTrigger === t.id ? "#3B82F6" : "#E5E7EB"}`,
                          cursor: "pointer",
                          transition: "all 0.15s",
                          background: selectedTrigger === t.id ? "#EFF6FF" : "#fff",
                        }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                          <span style={{ fontSize: 16 }}>{t.icon}</span>
                          <span style={{ fontSize: 12, fontWeight: 600, color: "#374151" }}>{t.name}</span>
                        </div>
                        <div style={{ fontSize: 10, color: "#6B7280" }}>{t.desc}</div>
                      </div>
                    ))}
                  </div>

                  {selectedTrigger && (
                    <div style={{ marginTop: 16 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: "#374151", marginBottom: 6 }}>绑定 Widget</div>
                      <select
                        value={selectedWidget}
                        onChange={(e) => setSelectedWidget(e.target.value)}
                        style={{
                          width: "100%",
                          padding: "8px 10px",
                          border: "1px solid #D1D5DB",
                          borderRadius: 6,
                          fontSize: 12,
                          color: "#374151",
                          background: "#fff",
                        }}
                      >
                        <option value="">选择 Widget...</option>
                        {WIDGET_OPTIONS.map((w) => (
                          <option key={w.value} value={w.value}>{w.label}</option>
                        ))}
                      </select>
                    </div>
                  )}
                </div>
              )}

              {currentStep === 2 && (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "#374151", marginBottom: 12 }}>选择动作类型</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                    {ACTION_OPTIONS.map((a) => (
                      <div
                        key={a.id}
                        onClick={() => setSelectedAction(a.id)}
                        style={{
                          padding: "10px 12px",
                          borderRadius: 8,
                          border: `1.5px solid ${selectedAction === a.id ? "#10B981" : "#E5E7EB"}`,
                          cursor: "pointer",
                          display: "flex",
                          alignItems: "center",
                          gap: 10,
                          background: selectedAction === a.id ? "#ECFDF5" : "#fff",
                        }}
                      >
                        <span
                          style={{
                            width: 28,
                            height: 28,
                            borderRadius: 6,
                            background: a.color === "blue" ? "#EFF6FF" :
                              a.color === "green" ? "#ECFDF5" :
                              a.color === "yellow" ? "#FFFBEB" :
                              a.color === "purple" ? "#F3E8FF" :
                              a.color === "red" ? "#FEE2E2" : "#E0E7FF",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            fontSize: 14,
                          }}
                        >
                          {a.icon}
                        </span>
                        <div>
                          <div style={{ fontSize: 12, fontWeight: 500, color: "#374151" }}>{a.name}</div>
                          <div style={{ fontSize: 10, color: "#6B7280" }}>{a.desc}</div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {selectedAction && (
                    <div style={{ marginTop: 16 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: "#374151", marginBottom: 6 }}>动作参数</div>
                      <input
                        type="text"
                        value={actionParam}
                        onChange={(e) => setActionParam(e.target.value)}
                        placeholder={actionParamPlaceholders[selectedAction] || ""}
                        style={{
                          width: "100%",
                          padding: "8px 10px",
                          border: "1px solid #D1D5DB",
                          borderRadius: 6,
                          fontSize: 12,
                          fontFamily: "monospace",
                        }}
                      />
                    </div>
                  )}
                </div>
              )}

              {currentStep === 3 && (
                <div>
                  <div style={{ fontSize: 12, fontWeight: 600, color: "#374151", marginBottom: 12 }}>目标变量</div>
                  <input
                    type="text"
                    value={targetVar}
                    onChange={(e) => setTargetVar(e.target.value)}
                    placeholder="如 selectedWorkOrderId / inboxFilter"
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      border: "1px solid #D1D5DB",
                      borderRadius: 6,
                      fontSize: 12,
                      fontFamily: "monospace",
                      marginBottom: 16,
                    }}
                  />

                  <div style={{ fontSize: 12, fontWeight: 600, color: "#374151", marginBottom: 6 }}>幂等键配置 (ACT-07)</div>
                  <div style={{ padding: 10, borderRadius: 8, background: "#FFFBEB", border: "1px solid #FDE68A", marginBottom: 8 }}>
                    <div style={{ fontSize: 10, color: "#92400E", lineHeight: 1.5 }}>
                      <strong>幂等护栏：</strong>写操作事件必须配置幂等键，防止双击或重试导致重复提交。
                      幂等键格式：<code style={{ background: "#FEF3C7", padding: "1px 4px", borderRadius: 2 }}>{`{action}:{widgetId}:{paramHash}`}</code>
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                    <input
                      type="checkbox"
                      checked={enableIdempotency}
                      onChange={(e) => setEnableIdempotency(e.target.checked)}
                      style={{ accentColor: "#F59E0B", width: 14, height: 14 }}
                    />
                    <label style={{ fontSize: 11, color: "#374151", cursor: "pointer" }}>启用幂等键（推荐：写操作必开）</label>
                  </div>
                  <input
                    type="text"
                    value={idempotencyKey}
                    onChange={(e) => setIdempotencyKey(e.target.value)}
                    placeholder="如 assignWorkOrder:{rowId}:{timestamp}"
                    disabled={!enableIdempotency}
                    style={{
                      width: "100%",
                      padding: "8px 10px",
                      border: "1px solid #D1D5DB",
                      borderRadius: 6,
                      fontSize: 11,
                      fontFamily: "monospace",
                      background: enableIdempotency ? "#FAFBFC" : "#F3F4F6",
                      opacity: enableIdempotency ? 1 : 0.5,
                    }}
                  />

                  <div style={{ marginTop: 16 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: "#374151", marginBottom: 6 }}>事件预览</div>
                    <div
                      style={{
                        padding: 12,
                        borderRadius: 8,
                        background: "#F9FAFB",
                        border: "1px solid #E5E7EB",
                        fontSize: 11,
                        fontFamily: "monospace",
                        color: "#374151",
                        lineHeight: 1.6,
                      }}
                    >
                      <div>触发器: <span style={{ color: "#3B82F6", fontWeight: 600 }}>{selectedTrigger || "(未选择)"}</span></div>
                      <div>Widget: <span style={{ color: "#374151" }}>{selectedWidget || "(未绑定)"}</span></div>
                      <div>动作: <span style={{ color: "#10B981", fontWeight: 600 }}>{ACTION_LABELS[selectedAction || ""] || "(未选择)"}</span></div>
                      <div>参数: <span style={{ color: "#374151" }}>{actionParam || "(未配置)"}</span></div>
                      <div>目标变量: <span style={{ color: "#374151" }}>{targetVar || "(未配置)"}</span></div>
                      <div>
                        幂等:{" "}
                        {enableIdempotency ? (
                          <span style={{ color: "#F59E0B" }}>● 已启用 ({idempotencyKey || "自动生成"})</span>
                        ) : (
                          <span style={{ color: "#EF4444" }}>✕ 未启用（写操作不推荐）</span>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div style={{ padding: "12px 24px", borderTop: "1px solid #E5E7EB", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", gap: 6 }}>
                {currentStep > 1 && (
                  <button
                    onClick={prevStep}
                    style={{
                      padding: "6px 16px",
                      fontSize: 12,
                      border: "1px solid #D1D5DB",
                      borderRadius: 6,
                      background: "#fff",
                      color: "#374151",
                      cursor: "pointer",
                    }}
                  >
                    上一步
                  </button>
                )}
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <button
                  onClick={closeModal}
                  style={{
                    padding: "6px 16px",
                    fontSize: 12,
                    border: "1px solid #D1D5DB",
                    borderRadius: 6,
                    background: "#fff",
                    color: "#6B7280",
                    cursor: "pointer",
                  }}
                >
                  取消
                </button>
                {currentStep < 3 ? (
                  <button
                    onClick={nextStep}
                    disabled={!canGoNext()}
                    style={{
                      padding: "6px 16px",
                      fontSize: 12,
                      border: "none",
                      borderRadius: 6,
                      background: canGoNext() ? "#3B82F6" : "#E5E7EB",
                      color: canGoNext() ? "#fff" : "#9CA3AF",
                      cursor: canGoNext() ? "pointer" : "not-allowed",
                    }}
                  >
                    下一步
                  </button>
                ) : (
                  <button
                    onClick={confirmAdd}
                    style={{
                      padding: "6px 16px",
                      fontSize: 12,
                      border: "none",
                      borderRadius: 6,
                      background: "#3B82F6",
                      color: "#fff",
                      cursor: "pointer",
                    }}
                  >
                    确认添加
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </PageChrome>
  );
}
