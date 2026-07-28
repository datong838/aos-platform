import { describe, expect, it } from "vitest";
import {
  canTransition,
  filterDrafts,
  countByTab,
  statusToTab,
  isTerminal,
  TRANSITIONS,
  TAB_STATUSES,
  STATUS_COLORS,
  STATUS_LABELS,
  ACTION_LABELS,
  ACTION_COLORS,
  statusBadgeVariant,
  extractSubmitters,
  type DraftItem,
  type DraftStatus,
  type DraftFilter,
} from "./DraftInboxPage";

/* --- 测试数据 --- */
const MOCK_DRAFTS: DraftItem[] = [
  {
    id: "d1",
    title: "测试 Draft 1",
    status: "in_review",
    type: "InsightBackfill",
    submittedBy: "张三",
    createdAt: "2026-07-21T10:00:00Z",
    updatedAt: "2026-07-21T11:00:00Z",
    confidence: 0.93,
    summary: "测试摘要",
    changes: [{ kind: "create", objectLabel: "X", detail: "d" }],
    timeline: [{ id: "t1", action: "create", actor: "张三", timestamp: "2026-07-21T10:00:00Z" }],
  },
  {
    id: "d2",
    title: "测试 Draft 2",
    status: "approved",
    type: "Action",
    submittedBy: "李四",
    createdAt: "2026-07-20T10:00:00Z",
    updatedAt: "2026-07-20T12:00:00Z",
    summary: "已批准",
    changes: [],
    timeline: [],
  },
  {
    id: "d3",
    title: "测试 Draft 3",
    status: "rejected",
    type: "Tool",
    submittedBy: "张三",
    createdAt: "2026-07-19T10:00:00Z",
    updatedAt: "2026-07-19T12:00:00Z",
    summary: "已拒绝",
    changes: [],
    timeline: [],
  },
  {
    id: "d4",
    title: "测试 Draft 4",
    status: "withdrawn",
    type: "OntologyChange",
    submittedBy: "王五",
    createdAt: "2026-07-18T10:00:00Z",
    updatedAt: "2026-07-18T12:00:00Z",
    summary: "已撤回",
    changes: [],
    timeline: [],
  },
];

/* =========================================================================
 * 测试 1: 状态转换合法性
 * ========================================================================= */
describe("审批流状态机", () => {
  it("draft → submitted 合法", () => {
    expect(canTransition("draft", "submitted")).toBe(true);
  });

  it("draft → approved 非法（不能跳过中间状态）", () => {
    expect(canTransition("draft", "approved")).toBe(false);
  });

  it("submitted → in_review 合法", () => {
    expect(canTransition("submitted", "in_review")).toBe(true);
  });

  it("in_review → approved 合法", () => {
    expect(canTransition("in_review", "approved")).toBe(true);
  });

  it("in_review → rejected 合法", () => {
    expect(canTransition("in_review", "rejected")).toBe(true);
  });

  it("in_review → changes_requested 合法", () => {
    expect(canTransition("in_review", "changes_requested")).toBe(true);
  });

  it("changes_requested → draft 合法（循环）", () => {
    expect(canTransition("changes_requested", "draft")).toBe(true);
  });

  it("draft → withdrawn 合法（可撤回）", () => {
    expect(canTransition("draft", "withdrawn")).toBe(true);
  });

  it("submitted → withdrawn 合法（可撤回）", () => {
    expect(canTransition("submitted", "withdrawn")).toBe(true);
  });

  it("approved → rejected 非法（终态不可转换）", () => {
    expect(canTransition("approved", "rejected")).toBe(false);
  });

  it("rejected → approved 非法（终态不可转换）", () => {
    expect(canTransition("rejected", "approved")).toBe(false);
  });

  it("TRANSITIONS 有 7 个状态", () => {
    expect(Object.keys(TRANSITIONS)).toHaveLength(7);
  });
});

/* =========================================================================
 * 测试 2: 终态判断
 * ========================================================================= */
describe("isTerminal", () => {
  it("approved 是终态", () => {
    expect(isTerminal("approved")).toBe(true);
  });

  it("rejected 是终态", () => {
    expect(isTerminal("rejected")).toBe(true);
  });

  it("withdrawn 是终态", () => {
    expect(isTerminal("withdrawn")).toBe(true);
  });

  it("in_review 不是终态", () => {
    expect(isTerminal("in_review")).toBe(false);
  });

  it("draft 不是终态", () => {
    expect(isTerminal("draft")).toBe(false);
  });
});

/* =========================================================================
 * 测试 3: 状态 → Tab 归类
 * ========================================================================= */
describe("statusToTab", () => {
  it("in_review 归类到 pending", () => {
    expect(statusToTab("in_review")).toBe("pending");
  });

  it("draft 归类到 pending", () => {
    expect(statusToTab("draft")).toBe("pending");
  });

  it("submitted 归类到 pending", () => {
    expect(statusToTab("submitted")).toBe("pending");
  });

  it("changes_requested 归类到 pending", () => {
    expect(statusToTab("changes_requested")).toBe("pending");
  });

  it("approved 归类到 approved", () => {
    expect(statusToTab("approved")).toBe("approved");
  });

  it("rejected 归类到 rejected", () => {
    expect(statusToTab("rejected")).toBe("rejected");
  });

  it("withdrawn 归类到 withdrawn", () => {
    expect(statusToTab("withdrawn")).toBe("withdrawn");
  });
});

/* =========================================================================
 * 测试 4: Tab 状态映射完整性
 * ========================================================================= */
describe("TAB_STATUSES", () => {
  it("pending Tab 包含 4 个非终态状态", () => {
    expect(TAB_STATUSES.pending).toHaveLength(4);
    expect(TAB_STATUSES.pending).toContain("draft");
    expect(TAB_STATUSES.pending).toContain("submitted");
    expect(TAB_STATUSES.pending).toContain("in_review");
    expect(TAB_STATUSES.pending).toContain("changes_requested");
  });

  it("approved Tab 只含 approved", () => {
    expect(TAB_STATUSES.approved).toEqual(["approved"]);
  });

  it("rejected Tab 只含 rejected", () => {
    expect(TAB_STATUSES.rejected).toEqual(["rejected"]);
  });

  it("withdrawn Tab 只含 withdrawn", () => {
    expect(TAB_STATUSES.withdrawn).toEqual(["withdrawn"]);
  });
});

/* =========================================================================
 * 测试 5: 筛选逻辑
 * ========================================================================= */
describe("filterDrafts", () => {
  const emptyFilter: DraftFilter = { type: "all", submittedBy: "all", dateFrom: "", dateTo: "" };

  it("pending Tab 下返回 1 个 in_review", () => {
    const result = filterDrafts(MOCK_DRAFTS, "pending", emptyFilter, "");
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe("d1");
  });

  it("approved Tab 下返回 1 个 approved", () => {
    const result = filterDrafts(MOCK_DRAFTS, "approved", emptyFilter, "");
    expect(result).toHaveLength(1);
    expect(result[0].status).toBe("approved");
  });

  it("按类型筛选 Action", () => {
    const result = filterDrafts(MOCK_DRAFTS, "approved", { ...emptyFilter, type: "Action" }, "");
    expect(result).toHaveLength(1);
    expect(result[0].type).toBe("Action");
  });

  it("按提交人筛选 张三", () => {
    const result = filterDrafts(MOCK_DRAFTS, "rejected", { ...emptyFilter, submittedBy: "张三" }, "");
    expect(result).toHaveLength(1);
    expect(result[0].submittedBy).toBe("张三");
  });

  it("搜索关键词匹配标题", () => {
    const result = filterDrafts(MOCK_DRAFTS, "pending", emptyFilter, "Draft 1");
    expect(result).toHaveLength(1);
    expect(result[0].title).toContain("Draft 1");
  });

  it("日期范围筛选排除早期数据", () => {
    const result = filterDrafts(MOCK_DRAFTS, "approved", { ...emptyFilter, dateFrom: "2026-07-21T00:00:00Z" }, "");
    expect(result).toHaveLength(0);
  });

  it("日期范围筛选包含数据", () => {
    const result = filterDrafts(MOCK_DRAFTS, "approved", { ...emptyFilter, dateFrom: "2026-07-19T00:00:00Z", dateTo: "2026-07-21T00:00:00Z" }, "");
    expect(result).toHaveLength(1);
  });

  it("空列表返回空", () => {
    const result = filterDrafts([], "pending", emptyFilter, "");
    expect(result).toHaveLength(0);
  });
});

/* =========================================================================
 * 测试 6: Tab 计数
 * ========================================================================= */
describe("countByTab", () => {
  it("正确统计各 Tab 数量", () => {
    const counts = countByTab(MOCK_DRAFTS);
    expect(counts.pending).toBe(1);
    expect(counts.approved).toBe(1);
    expect(counts.rejected).toBe(1);
    expect(counts.withdrawn).toBe(1);
  });

  it("空列表全为 0", () => {
    const counts = countByTab([]);
    expect(counts.pending).toBe(0);
    expect(counts.approved).toBe(0);
    expect(counts.rejected).toBe(0);
    expect(counts.withdrawn).toBe(0);
  });
});

/* =========================================================================
 * 测试 7: 提取提交人
 * ========================================================================= */
describe("extractSubmitters", () => {
  it("提取去重并排序的提交人列表", () => {
    const result = extractSubmitters(MOCK_DRAFTS);
    expect(result).toHaveLength(3);
    expect(result).toContain("张三");
    expect(result).toContain("李四");
    expect(result).toContain("王五");
  });

  it("空列表返回空数组", () => {
    expect(extractSubmitters([])).toHaveLength(0);
  });
});

/* =========================================================================
 * 测试 8: 颜色/标签映射
 * ========================================================================= */
describe("状态映射", () => {
  it("每个状态都有颜色", () => {
    const statuses: DraftStatus[] = ["draft", "submitted", "in_review", "approved", "rejected", "withdrawn", "changes_requested"];
    statuses.forEach((s) => {
      expect(STATUS_COLORS[s]).toBeTruthy();
    });
  });

  it("每个状态都有中文标签", () => {
    const statuses: DraftStatus[] = ["draft", "submitted", "in_review", "approved", "rejected", "withdrawn", "changes_requested"];
    statuses.forEach((s) => {
      expect(STATUS_LABELS[s]).toBeTruthy();
      expect(typeof STATUS_LABELS[s]).toBe("string");
    });
  });

  it("in_review 颜色为蓝色 token", () => {
    expect(STATUS_COLORS.in_review).toBe("var(--aos-blue-600)");
  });

  it("approved 颜色为绿色 token", () => {
    expect(STATUS_COLORS.approved).toBe("var(--aos-green-600)");
  });

  it("rejected 颜色为红色 token", () => {
    expect(STATUS_COLORS.rejected).toBe("var(--aos-red)");
  });

  it("submitted 颜色为橙色 token", () => {
    expect(STATUS_COLORS.submitted).toBe("var(--aos-amber-600)");
  });

  it("changes_requested 颜色为紫色 token", () => {
    expect(STATUS_COLORS.changes_requested).toBe("var(--aos-purple-600)");
  });
});

/* =========================================================================
 * 测试 9: Badge variant 映射
 * ========================================================================= */
describe("statusBadgeVariant", () => {
  it("approved → success", () => {
    expect(statusBadgeVariant("approved")).toBe("success");
  });

  it("rejected → danger", () => {
    expect(statusBadgeVariant("rejected")).toBe("danger");
  });

  it("in_review → info", () => {
    expect(statusBadgeVariant("in_review")).toBe("info");
  });

  it("submitted → warning", () => {
    expect(statusBadgeVariant("submitted")).toBe("warning");
  });

  it("changes_requested → purple", () => {
    expect(statusBadgeVariant("changes_requested")).toBe("purple");
  });
});

/* =========================================================================
 * 测试 10: Timeline 操作映射
 * ========================================================================= */
describe("Timeline 操作映射", () => {
  it("每个操作都有中文标签", () => {
    const actions = ["create", "submit", "in_review", "approve", "reject", "withdraw", "changes_requested", "comment"] as const;
    actions.forEach((a) => {
      expect(ACTION_LABELS[a]).toBeTruthy();
    });
  });

  it("每个操作都有颜色", () => {
    const actions = ["create", "submit", "in_review", "approve", "reject", "withdraw", "changes_requested", "comment"] as const;
    actions.forEach((a) => {
      expect(ACTION_COLORS[a]).toBeTruthy();
    });
  });

  it("approve 操作标签为「批准」", () => {
    expect(ACTION_LABELS.approve).toBe("批准");
  });

  it("reject 操作标签为「拒绝」", () => {
    expect(ACTION_LABELS.reject).toBe("拒绝");
  });
});
