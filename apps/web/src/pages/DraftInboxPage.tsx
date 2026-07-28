import { useEffect, useMemo, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { getOntologyClient } from "../api/ontologyClient";
import { PageChrome } from "../components/PageChrome";
import { BpBadge } from "../components/bp";

/* =========================================================================
 * 1. 类型定义
 * ========================================================================= */

/** 审批流状态（6 状态） */
export type DraftStatus =
  | "draft"
  | "submitted"
  | "in_review"
  | "approved"
  | "rejected"
  | "withdrawn"
  | "changes_requested";

/** Draft 类型（4 种 Tab） */
export type DraftTab = "pending" | "approved" | "rejected" | "withdrawn";

/** Timeline 操作类型 */
export type TimelineAction =
  | "submit"
  | "in_review"
  | "approve"
  | "reject"
  | "withdraw"
  | "changes_requested"
  | "comment"
  | "create";

export type DraftType = "InsightBackfill" | "Action" | "Tool" | "OntologyChange";

export type DraftItem = {
  id: string;
  title: string;
  status: DraftStatus;
  type: DraftType;
  submittedBy: string;
  createdAt: string;
  updatedAt: string;
  confidence?: number;
  summary: string;
  changes: DraftChange[];
  timeline: TimelineEntry[];
};

export type DraftChange = {
  kind: "create" | "link" | "update";
  objectLabel: string;
  field?: string;
  detail: string;
};

export type TimelineEntry = {
  id: string;
  action: TimelineAction;
  actor: string;
  timestamp: string;
  comment?: string;
};

export type DraftFilter = {
  type: DraftType | "all";
  submittedBy: string | "all";
  dateFrom: string;
  dateTo: string;
};

/* =========================================================================
 * 2. 纯函数：状态机 / 筛选 / Tab / Timeline
 * ========================================================================= */

/** 状态转换表（状态 → 允许的下一状态集合） */
export const TRANSITIONS: Record<DraftStatus, DraftStatus[]> = {
  draft: ["submitted", "withdrawn"],
  submitted: ["in_review", "withdrawn"],
  in_review: ["approved", "rejected", "changes_requested"],
  approved: [],
  rejected: [],
  withdrawn: [],
  changes_requested: ["draft"],
};

/** 终态集合 */
export const TERMINAL_STATES: DraftStatus[] = ["approved", "rejected", "withdrawn"];

/** 判断从 from → to 是否合法 */
export function canTransition(from: DraftStatus, to: DraftStatus): boolean {
  return (TRANSITIONS[from] ?? []).includes(to);
}

/** Tab → 该 Tab 下应展示的状态集合 */
export const TAB_STATUSES: Record<DraftTab, DraftStatus[]> = {
  pending: ["draft", "submitted", "in_review", "changes_requested"],
  approved: ["approved"],
  rejected: ["rejected"],
  withdrawn: ["withdrawn"],
};

/** 将一个 DraftStatus 归类到某个 Tab */
export function statusToTab(status: DraftStatus): DraftTab {
  if (status === "approved") return "approved";
  if (status === "rejected") return "rejected";
  if (status === "withdrawn") return "withdrawn";
  return "pending";
}

/** 判断状态是否终态 */
export function isTerminal(status: DraftStatus): boolean {
  return TERMINAL_STATES.includes(status);
}

/** 按 Tab + 筛选条件过滤 Draft 列表（纯函数） */
export function filterDrafts(
  drafts: DraftItem[],
  tab: DraftTab,
  filter: DraftFilter,
  search: string,
): DraftItem[] {
  const allowed = TAB_STATUSES[tab];
  const q = search.trim().toLowerCase();
  return drafts.filter((d) => {
    if (!allowed.includes(d.status)) return false;
    if (filter.type !== "all" && d.type !== filter.type) return false;
    if (filter.submittedBy !== "all" && d.submittedBy !== filter.submittedBy) return false;
    if (filter.dateFrom && d.createdAt < filter.dateFrom) return false;
    if (filter.dateTo && d.createdAt > filter.dateTo) return false;
    if (q && !d.title.toLowerCase().includes(q) && !d.summary.toLowerCase().includes(q)) return false;
    return true;
  });
}

/** 统计各 Tab 下 Draft 数量 */
export function countByTab(drafts: DraftItem[]): Record<DraftTab, number> {
  const result: Record<DraftTab, number> = {
    pending: 0,
    approved: 0,
    rejected: 0,
    withdrawn: 0,
  };
  for (const d of drafts) {
    result[statusToTab(d.status)]++;
  }
  return result;
}

/** 状态 → 颜色映射 */
export const STATUS_COLORS: Record<DraftStatus, string> = {
  draft: "var(--aos-text-secondary)",
  submitted: "var(--aos-amber-600)",
  in_review: "var(--aos-blue-600)",
  approved: "var(--aos-green-600)",
  rejected: "var(--aos-red)",
  withdrawn: "var(--aos-text-secondary)",
  changes_requested: "var(--aos-purple-600)",
};

/** 状态 → Badge variant 映射 */
export function statusBadgeVariant(status: DraftStatus) {
  const map: Record<DraftStatus, "default" | "warning" | "info" | "success" | "danger" | "purple"> = {
    draft: "default",
    submitted: "warning",
    in_review: "info",
    approved: "success",
    rejected: "danger",
    withdrawn: "default",
    changes_requested: "purple",
  };
  return map[status];
}

/** 状态 → 中文标签 */
export const STATUS_LABELS: Record<DraftStatus, string> = {
  draft: "草稿",
  submitted: "已提交",
  in_review: "审批中",
  approved: "已批准",
  rejected: "已拒绝",
  withdrawn: "已撤回",
  changes_requested: "退回修改",
};

/** Timeline 操作 → 中文标签 */
export const ACTION_LABELS: Record<TimelineAction, string> = {
  create: "创建草稿",
  submit: "提交审批",
  in_review: "进入审批",
  approve: "批准",
  reject: "拒绝",
  withdraw: "撤回",
  changes_requested: "退回修改",
  comment: "评论",
};

/** Timeline 操作 → 颜色 */
export const ACTION_COLORS: Record<TimelineAction, string> = {
  create: "var(--aos-purple-600)",
  submit: "var(--aos-amber-600)",
  in_review: "var(--aos-blue-600)",
  approve: "var(--aos-green-600)",
  reject: "var(--aos-red)",
  withdraw: "var(--aos-text-secondary)",
  changes_requested: "var(--aos-purple-600)",
  comment: "var(--aos-text-tertiary)",
};

/* =========================================================================
 * 3. Mock 数据
 * ========================================================================= */

const MOCK_DRAFTS: DraftItem[] = [
  {
    id: "d1",
    title: "纯度异常 ↔ 设备振动 · 知识回填",
    status: "in_review",
    type: "InsightBackfill",
    submittedBy: "质控 Agent",
    createdAt: "2026-07-21T10:00:00Z",
    updatedAt: "2026-07-21T11:00:00Z",
    confidence: 0.93,
    summary: "由 AIP Logic 触发，置信度 0.93 超过回填阈值。",
    changes: [
      { kind: "create", objectLabel: "Insight", detail: "新建 Insight: 纯度异常 ↔ 设备振动相关性" },
      { kind: "link", objectLabel: "Batch#A ↔ Equipment#B", detail: "建立双向关联" },
      { kind: "update", objectLabel: "Batch#A", field: "anomaly_note", detail: 'null → "振动频率 32Hz 触发纯度偏差"' },
    ],
    timeline: [
      { id: "t1", action: "create", actor: "质控 Agent", timestamp: "2026-07-21T10:00:00Z", comment: "由 AIP Logic 触发" },
      { id: "t2", action: "submit", actor: "质控 Agent", timestamp: "2026-07-21T10:05:00Z" },
      { id: "t3", action: "in_review", actor: "系统", timestamp: "2026-07-21T10:10:00Z", comment: "分派给：李工、王产品" },
      { id: "t4", action: "comment", actor: "李工", timestamp: "2026-07-21T10:30:00Z", comment: "振动 32Hz 的阈值需要再核对一次设备手册。" },
      { id: "t5", action: "comment", actor: "王产品", timestamp: "2026-07-21T10:48:00Z", comment: "同意，Evals 已通过，可以批准。" },
    ],
  },
  {
    id: "d2",
    title: "维修派单 · 更新派单规则",
    status: "submitted",
    type: "Action",
    submittedBy: "李工",
    createdAt: "2026-07-21T09:00:00Z",
    updatedAt: "2026-07-21T09:00:00Z",
    summary: "更新维修派单规则，适配新设备类型。",
    changes: [
      { kind: "update", objectLabel: "DispatchRule", field: "priority_weight", detail: "0.5 → 0.7" },
    ],
    timeline: [
      { id: "t1", action: "create", actor: "李工", timestamp: "2026-07-21T09:00:00Z" },
      { id: "t2", action: "submit", actor: "李工", timestamp: "2026-07-21T09:05:00Z" },
    ],
  },
  {
    id: "d3",
    title: "库存预警 Agent · 新增工具调用",
    status: "draft",
    type: "Tool",
    submittedBy: "王产品",
    createdAt: "2026-07-20T14:00:00Z",
    updatedAt: "2026-07-20T14:00:00Z",
    summary: "库存预警 Agent 新增 check_inventory 工具。",
    changes: [
      { kind: "create", objectLabel: "ToolBinding", detail: "新增 check_inventory 工具绑定" },
    ],
    timeline: [
      { id: "t1", action: "create", actor: "王产品", timestamp: "2026-07-20T14:00:00Z" },
    ],
  },
  {
    id: "d4",
    title: "客户画像 Action · 批量标签更新",
    status: "approved",
    type: "Action",
    submittedBy: "张数据",
    createdAt: "2026-07-18T10:00:00Z",
    updatedAt: "2026-07-18T16:00:00Z",
    summary: "批量更新客户画像标签，已写入生产。",
    changes: [
      { kind: "update", objectLabel: "CustomerProfile", field: "tags", detail: "新增「高价值」标签" },
    ],
    timeline: [
      { id: "t1", action: "create", actor: "张数据", timestamp: "2026-07-18T10:00:00Z" },
      { id: "t2", action: "submit", actor: "张数据", timestamp: "2026-07-18T10:30:00Z" },
      { id: "t3", action: "in_review", actor: "系统", timestamp: "2026-07-18T11:00:00Z" },
      { id: "t4", action: "approve", actor: "审批人A", timestamp: "2026-07-18T16:00:00Z", comment: "通过，已写入生产。" },
    ],
  },
  {
    id: "d5",
    title: "价格策略 · 折扣阈值调整",
    status: "rejected",
    type: "Action",
    submittedBy: "陈运营",
    createdAt: "2026-07-16T08:00:00Z",
    updatedAt: "2026-07-16T12:00:00Z",
    summary: "调整折扣阈值，被拒绝。",
    changes: [
      { kind: "update", objectLabel: "PriceRule", field: "discount_threshold", detail: "0.3 → 0.5" },
    ],
    timeline: [
      { id: "t1", action: "create", actor: "陈运营", timestamp: "2026-07-16T08:00:00Z" },
      { id: "t2", action: "submit", actor: "陈运营", timestamp: "2026-07-16T08:30:00Z" },
      { id: "t3", action: "in_review", actor: "系统", timestamp: "2026-07-16T09:00:00Z" },
      { id: "t4", action: "reject", actor: "审批人B", timestamp: "2026-07-16T12:00:00Z", comment: "阈值过高，风险大。" },
    ],
  },
  {
    id: "d6",
    title: "本体提案 · 新增设备类",
    status: "withdrawn",
    type: "OntologyChange",
    submittedBy: "刘架构",
    createdAt: "2026-07-14T10:00:00Z",
    updatedAt: "2026-07-14T15:00:00Z",
    summary: "新增 EquipmentV2 本体类，已撤回。",
    changes: [
      { kind: "create", objectLabel: "ObjectType", detail: "新建 EquipmentV2" },
    ],
    timeline: [
      { id: "t1", action: "create", actor: "刘架构", timestamp: "2026-07-14T10:00:00Z" },
      { id: "t2", action: "submit", actor: "刘架构", timestamp: "2026-07-14T10:30:00Z" },
      { id: "t3", action: "withdraw", actor: "刘架构", timestamp: "2026-07-14T15:00:00Z", comment: "需要重新设计。" },
    ],
  },
];

/** 从 Mock 列表提取所有提交人 */
export function extractSubmitters(drafts: DraftItem[]): string[] {
  const set = new Set<string>();
  drafts.forEach((d) => set.add(d.submittedBy));
  return Array.from(set).sort();
}

/* =========================================================================
 * 4. 主组件
 * ========================================================================= */

const TAB_LABELS: { id: DraftTab; label: string }[] = [
  { id: "pending", label: "待审批" },
  { id: "approved", label: "已批准" },
  { id: "rejected", label: "已拒绝" },
  { id: "withdrawn", label: "已撤回" },
];

export function DraftInboxPage() {
  const [drafts, setDrafts] = useState<DraftItem[]>(MOCK_DRAFTS);
  const [activeTab, setActiveTab] = useState<DraftTab>("pending");
  const [selectedId, setSelectedId] = useState<string | null>(MOCK_DRAFTS[0]?.id ?? null);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<DraftFilter>({
    type: "all",
    submittedBy: "all",
    dateFrom: "",
    dateTo: "",
  });
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [apiItems, setApiItems] = useState<DraftItem[]>([]);
  const [apiError, setApiError] = useState<string | null>(null);

  const allDrafts = useMemo(() => {
    if (apiItems.length > 0) return apiItems;
    return drafts;
  }, [drafts, apiItems]);

  const tabCounts = useMemo(() => countByTab(allDrafts), [allDrafts]);
  const submitters = useMemo(() => extractSubmitters(allDrafts), [allDrafts]);

  const filteredDrafts = useMemo(
    () => filterDrafts(allDrafts, activeTab, filter, search),
    [allDrafts, activeTab, filter, search],
  );

  const selected = useMemo(
    () => allDrafts.find((d) => d.id === selectedId) ?? null,
    [allDrafts, selectedId],
  );

  /* --- API 同步（可选，失败不影响 Mock 演示） --- */
  const reloadFromApi = useCallback(async () => {
    try {
      const res = await getOntologyClient().listDrafts();
      const items = (res.items || []).map((row): DraftItem => ({
        id: row.id ?? "unknown",
        title: row.title ?? row.id ?? "Untitled",
        status: (row.status as DraftStatus) ?? "draft",
        type: "Action",
        submittedBy: (row.createdBy as string) ?? "未知",
        createdAt: (row.createdAt as string) ?? "",
        updatedAt: (row.updatedAt as string) ?? "",
        summary: "",
        changes: [],
        timeline: [],
      }));
      setApiItems(items);
      setApiError(null);
    } catch (e) {
      setApiError(String((e as Error).message || e));
    }
  }, []);

  useEffect(() => {
    reloadFromApi().catch(() => {});
  }, [reloadFromApi]);

  /* --- 状态转换（本地 Mock） --- */
  const transition = useCallback(
    (id: string, to: DraftStatus, comment?: string) => {
      setDrafts((prev) =>
        prev.map((d) => {
          if (d.id !== id) return d;
          if (!canTransition(d.status, to)) {
            setErr(`非法状态转换：${d.status} → ${to}`);
            return d;
          }
          setMsg(`${STATUS_LABELS[to]} · ${d.title}`);
          const newEntry: TimelineEntry = {
            id: `tl-${Date.now()}`,
            action: to === "approved" ? "approve" : to === "rejected" ? "reject" : to === "withdrawn" ? "withdraw" : to === "changes_requested" ? "changes_requested" : to === "submitted" ? "submit" : to === "in_review" ? "in_review" : "create",
            actor: "当前用户",
            timestamp: new Date().toISOString(),
            comment,
          };
          return {
            ...d,
            status: to,
            updatedAt: new Date().toISOString(),
            timeline: [...d.timeline, newEntry],
          };
        }),
      );
    },
    [],
  );

  /* --- 审批操作 --- */
  const handleApprove = () => { if (selected) transition(selected.id, "approved"); };
  const handleReject = () => { if (selected) transition(selected.id, "rejected"); };
  const handleChangeRequest = () => { if (selected) transition(selected.id, "changes_requested"); };
  const handleWithdraw = () => { if (selected) transition(selected.id, "withdrawn"); };
  const handleSubmit = () => { if (selected) transition(selected.id, "submitted"); };
  const handleStartReview = () => { if (selected) transition(selected.id, "in_review"); };

  const handleAddComment = () => {
    if (!selected) return;
    const comment = window.prompt("输入评论：");
    if (!comment) return;
    setDrafts((prev) =>
      prev.map((d) =>
        d.id === selected.id
          ? { ...d, timeline: [...d.timeline, { id: `c-${Date.now()}`, action: "comment", actor: "当前用户", timestamp: new Date().toISOString(), comment }] }
          : d,
      ),
    );
  };

  return (
    <PageChrome
      title="Draft 审批台"
      lede="Agent / Action 写入须经 HITL 批准后方可落生产 Ontology；含 Insight Backfill（知识回填）。"
    >
      {/* 消息条 */}
      {msg && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4 text-sm text-blue-800">
          {msg}
        </div>
      )}
      {err && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 text-sm text-red-800">
          {err}
        </div>
      )}
      {apiError && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-3 mb-4 text-xs text-gray-500">
          API 离线（{apiError}）· 使用 Mock 数据演示
        </div>
      )}

      {/* Draft Dataset 隔离说明 */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-4 text-xs text-blue-800">
        <strong>Draft Dataset 隔离：</strong>
        所有待审写入暂存于独立 Draft Dataset，与生产数据物理隔离；驳回即丢弃，不污染主库。
      </div>

      {/* ====== 三栏布局 ====== */}
      <div className="flex gap-4" style={{ minHeight: 600 }}>
        {/* ============ 左栏：筛选面板 (240px) ============ */}
        <aside
          className="flex flex-col gap-3"
          style={{ width: 240, flexShrink: 0 }}
        >
          <div className="bg-white border border-gray-200 rounded-lg p-3">
            <div className="text-sm font-semibold text-gray-900 mb-3 pb-2 border-b border-gray-100">
              筛选
            </div>

            {/* 类型筛选 */}
            <div className="mb-3">
              <label className="block text-xs font-medium text-gray-700 mb-1">类型</label>
              <select
                className="w-full text-xs border border-gray-200 rounded-md px-2 py-1.5 bg-white"
                value={filter.type}
                onChange={(e) => setFilter((f) => ({ ...f, type: e.target.value as DraftFilter["type"] }))}
              >
                <option value="all">全部类型</option>
                <option value="InsightBackfill">InsightBackfill</option>
                <option value="Action">Action</option>
                <option value="Tool">Tool</option>
                <option value="OntologyChange">OntologyChange</option>
              </select>
            </div>

            {/* 提交人筛选 */}
            <div className="mb-3">
              <label className="block text-xs font-medium text-gray-700 mb-1">提交人</label>
              <select
                className="w-full text-xs border border-gray-200 rounded-md px-2 py-1.5 bg-white"
                value={filter.submittedBy}
                onChange={(e) => setFilter((f) => ({ ...f, submittedBy: e.target.value }))}
              >
                <option value="all">全部提交人</option>
                {submitters.map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
            </div>

            {/* 日期范围 */}
            <div className="mb-3">
              <label className="block text-xs font-medium text-gray-700 mb-1">开始日期</label>
              <input
                type="date"
                className="w-full text-xs border border-gray-200 rounded-md px-2 py-1.5"
                value={filter.dateFrom}
                onChange={(e) => setFilter((f) => ({ ...f, dateFrom: e.target.value }))}
              />
            </div>
            <div className="mb-3">
              <label className="block text-xs font-medium text-gray-700 mb-1">结束日期</label>
              <input
                type="date"
                className="w-full text-xs border border-gray-200 rounded-md px-2 py-1.5"
                value={filter.dateTo}
                onChange={(e) => setFilter((f) => ({ ...f, dateTo: e.target.value }))}
              />
            </div>

            {/* 重置 */}
            <button
              type="button"
              className="w-full text-xs text-gray-500 hover:text-gray-700 border border-gray-200 rounded-md py-1.5"
              onClick={() => setFilter({ type: "all", submittedBy: "all", dateFrom: "", dateTo: "" })}
            >
              重置筛选
            </button>
          </div>
        </aside>

        {/* ============ 中栏：Draft 列表（自适应） ============ */}
        <section className="flex-1 flex flex-col" style={{ minWidth: 0 }}>
          {/* Tab 导航 */}
          <div className="flex gap-1 border-b border-gray-200 mb-3">
            {TAB_LABELS.map((t) => {
              const active = activeTab === t.id;
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => setActiveTab(t.id)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                    active
                      ? "border-blue-500 text-blue-600"
                      : "border-transparent text-gray-500 hover:text-gray-700"
                  }`}
                >
                  {t.label}
                  <span className="ml-1.5 text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-600">
                    {tabCounts[t.id]}
                  </span>
                </button>
              );
            })}
          </div>

          {/* 搜索栏 */}
          <div className="relative mb-3">
            <svg className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <circle cx="11" cy="11" r="7" />
              <path d="M20 20l-3-3" strokeLinecap="round" />
            </svg>
            <input
              type="search"
              placeholder="搜索 Draft…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-md outline-none focus:border-blue-400"
            />
          </div>

          {/* Draft 卡片列表 */}
          <div className="flex flex-col gap-2 overflow-y-auto" style={{ maxHeight: 540 }}>
            {filteredDrafts.length === 0 ? (
              <div className="text-center py-12 text-gray-400 text-sm">该 Tab 下暂无 Draft</div>
            ) : (
              filteredDrafts.map((d) => {
                const active = d.id === selectedId;
                return (
                  <button
                    key={d.id}
                    type="button"
                    onClick={() => setSelectedId(d.id)}
                    className={`text-left p-3 rounded-lg border transition-all ${
                      active
                        ? "border-blue-400 bg-blue-50 shadow-sm"
                        : "border-gray-200 bg-white hover:border-gray-300 hover:shadow-sm"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <BpBadge variant={statusBadgeVariant(d.status)} size="sm">
                          {STATUS_LABELS[d.status]}
                        </BpBadge>
                        <span className="text-xs text-gray-500">{d.type}</span>
                      </div>
                      <span className="text-xs text-gray-400">{formatTime(d.updatedAt)}</span>
                    </div>
                    <div className="text-sm font-medium text-gray-900 mb-1">{d.title}</div>
                    <div className="text-xs text-gray-500">
                      {d.submittedBy} · {d.changes.length} 项变更
                      {d.confidence !== undefined && ` · 置信 ${d.confidence}`}
                    </div>
                  </button>
                );
              })
            )}
          </div>
        </section>

        {/* ============ 右栏：详情预览 (400-600px) ============ */}
        <aside
          className="flex flex-col bg-white border border-gray-200 rounded-lg overflow-hidden"
          style={{ width: 480, flexShrink: 0 }}
        >
          {selected ? (
            <>
              {/* 详情 Header */}
              <div className="p-4 border-b border-gray-100">
                <div className="flex items-center gap-2 mb-2">
                  <BpBadge variant={statusBadgeVariant(selected.status)} size="sm">
                    {STATUS_LABELS[selected.status]}
                  </BpBadge>
                  <span className="text-xs text-gray-500">{selected.type}</span>
                  <span className="text-xs text-gray-400 ml-auto">{formatTime(selected.updatedAt)}</span>
                </div>
                <h2 className="text-base font-semibold text-gray-900 mb-1">{selected.title}</h2>
                <div className="text-xs text-gray-500">
                  提交人 {selected.submittedBy}
                  {selected.confidence !== undefined && ` · 置信度 ${selected.confidence}`}
                </div>
              </div>

              {/* 详情内容（可滚动） */}
              <div className="flex-1 overflow-y-auto p-4">
                {/* 概述 */}
                <div className="mb-4">
                  <h3 className="text-xs font-semibold text-gray-700 mb-2">概述</h3>
                  <p className="text-xs text-gray-600 leading-relaxed">{selected.summary}</p>
                </div>

                {/* 变更 Diff */}
                <div className="mb-4">
                  <h3 className="text-xs font-semibold text-gray-700 mb-2">
                    变更内容 · {selected.changes.length} 项
                  </h3>
                  <div className="border border-gray-200 rounded-md overflow-hidden">
                    {selected.changes.map((c, i) => (
                      <div
                        key={i}
                        className={`flex items-start gap-2 p-2 text-xs ${
                          i > 0 ? "border-t border-gray-100" : ""
                        }`}
                      >
                        <span
                          className="inline-block px-1.5 py-0.5 rounded text-xs font-medium flex-shrink-0"
                          style={{
                            background: c.kind === "create" ? "var(--aos-green-bg)" : c.kind === "link" ? "var(--aos-blue-bg)" : "var(--aos-amber-bg)",
                            color: c.kind === "create" ? "var(--aos-green-700)" : c.kind === "link" ? "var(--aos-blue-700)" : "var(--aos-amber-700)",
                          }}
                        >
                          {c.kind === "create" ? "新建" : c.kind === "link" ? "关联" : "更新"}
                        </span>
                        <div className="flex-1">
                          <span className="text-gray-900 font-medium">{c.objectLabel}</span>
                          {c.field && <span className="text-gray-500"> · {c.field}</span>}
                          <p className="text-gray-600 mt-0.5">{c.detail}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Timeline 审批历史 */}
                <div>
                  <h3 className="text-xs font-semibold text-gray-700 mb-3">审批历史</h3>
                  <div className="flex flex-col gap-0">
                    {selected.timeline.map((entry, idx) => (
                      <div key={entry.id} className="flex gap-3">
                        {/* 左侧竖线 + 节点圆点 */}
                        <div className="flex flex-col items-center flex-shrink-0">
                          <div
                            className="rounded-full"
                            style={{
                              width: 10,
                              height: 10,
                              background: ACTION_COLORS[entry.action],
                              marginTop: 4,
                            }}
                          />
                          {idx < selected.timeline.length - 1 && (
                            <div style={{ width: 2, flex: 1, background: "var(--aos-border)", minHeight: 24 }} />
                          )}
                        </div>
                        {/* 内容 */}
                        <div className="flex-1 pb-4">
                          <div className="text-xs font-medium text-gray-900">
                            {ACTION_LABELS[entry.action]}
                          </div>
                          <div className="text-xs text-gray-400 mt-0.5">
                            {entry.actor} · {formatTime(entry.timestamp)}
                          </div>
                          {entry.comment && (
                            <div className="text-xs text-gray-600 mt-1 leading-relaxed bg-gray-50 rounded p-2">
                              "{entry.comment}"
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* 审批操作按钮区 */}
              <div className="p-3 border-t border-gray-100 bg-gray-50">
                <ApprovalActions
                  status={selected.status}
                  onApprove={handleApprove}
                  onReject={handleReject}
                  onChangeRequest={handleChangeRequest}
                  onWithdraw={handleWithdraw}
                  onSubmit={handleSubmit}
                  onStartReview={handleStartReview}
                  onAddComment={handleAddComment}
                />
              </div>
            </>
          ) : (
            <div className="flex-1 flex items-center justify-center text-gray-400 text-sm">
              选择左侧 Draft 查看详情
            </div>
          )}
        </aside>
      </div>

      {/* 底部链接 */}
      <div className="flex gap-4 py-3 mt-4 border-t border-gray-100 text-xs">
        <Link to="/aip/lineage" className="text-blue-600 hover:underline">决策谱系 →</Link>
        <Link to="/workshop/inbox" className="text-blue-600 hover:underline">运营 Inbox →</Link>
      </div>
    </PageChrome>
  );
}

/* =========================================================================
 * 5. 审批操作按钮子组件
 * ========================================================================= */

function ApprovalActions({
  status,
  onApprove,
  onReject,
  onChangeRequest,
  onWithdraw,
  onSubmit,
  onStartReview,
  onAddComment,
}: {
  status: DraftStatus;
  onApprove: () => void;
  onReject: () => void;
  onChangeRequest: () => void;
  onWithdraw: () => void;
  onSubmit: () => void;
  onStartReview: () => void;
  onAddComment: () => void;
}) {
  const btnBase = "px-3 py-1.5 text-xs font-medium rounded-md border transition-colors cursor-pointer";

  // in_review：显示「批准」「拒绝」「退回修改」「添加评论」
  if (status === "in_review") {
    return (
      <div className="flex flex-wrap gap-2">
        <button type="button" className={`${btnBase} bg-green-600 text-white border-green-600 hover:bg-green-700`} onClick={onApprove}>
          批准
        </button>
        <button type="button" className={`${btnBase} bg-red-600 text-white border-red-600 hover:bg-red-700`} onClick={onReject}>
          拒绝
        </button>
        <button type="button" className={`${btnBase} bg-white text-purple-700 border-purple-300 hover:bg-purple-50`} onClick={onChangeRequest}>
          退回修改
        </button>
        <button type="button" className={`${btnBase} bg-white text-gray-700 border-gray-300 hover:bg-gray-50`} onClick={onAddComment}>
          添加评论
        </button>
      </div>
    );
  }

  // draft/submitted：显示「撤回」「编辑」/「进入审批」
  if (status === "draft" || status === "submitted") {
    return (
      <div className="flex flex-wrap gap-2">
        {status === "draft" && (
          <button type="button" className={`${btnBase} bg-blue-600 text-white border-blue-600 hover:bg-blue-700`} onClick={onSubmit}>
            提交审批
          </button>
        )}
        {status === "submitted" && (
          <button type="button" className={`${btnBase} bg-blue-600 text-white border-blue-600 hover:bg-blue-700`} onClick={onStartReview}>
            进入审批
          </button>
        )}
        <button type="button" className={`${btnBase} bg-white text-gray-700 border-gray-300 hover:bg-gray-50`}>
          编辑
        </button>
        <button type="button" className={`${btnBase} bg-white text-red-600 border-red-300 hover:bg-red-50`} onClick={onWithdraw}>
          撤回
        </button>
      </div>
    );
  }

  // changes_requested：显示「返回草稿」「编辑」
  if (status === "changes_requested") {
    return (
      <div className="flex flex-wrap gap-2">
        <button type="button" className={`${btnBase} bg-blue-600 text-white border-blue-600 hover:bg-blue-700`}>
          返回草稿
        </button>
        <button type="button" className={`${btnBase} bg-white text-gray-700 border-gray-300 hover:bg-gray-50`}>
          编辑
        </button>
      </div>
    );
  }

  // 终态（approved/rejected/withdrawn）：显示「查看历史」
  return (
    <div className="flex gap-2">
      <button type="button" className={`${btnBase} bg-white text-gray-700 border-gray-300 hover:bg-gray-50`}>
        查看历史
      </button>
    </div>
  );
}

/* =========================================================================
 * 6. 工具函数
 * ========================================================================= */

function formatTime(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  const now = new Date();
  const diff = now.getTime() - d.getTime();
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return d.toLocaleDateString("zh-CN");
}
