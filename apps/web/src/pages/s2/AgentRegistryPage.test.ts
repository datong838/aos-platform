import { describe, expect, it } from "vitest";
import {
  computeRegistryStats,
  extractAllTags,
  filterAgents,
  STATUS_TABS,
  type AgentCard,
} from "./AgentRegistryPage";

const MOCK_AGENTS_FOR_TEST: AgentCard[] = [
  {
    id: "test-1",
    name: "测试 Agent 1",
    category: "测试",
    source: "builtin",
    sourceLabel: "平台内创建",
    status: "running",
    statusLabel: "运行中",
    description: "用于测试的 Agent",
    tags: [
      { label: "工单分配", tone: "indigo" },
      { label: "L2 · HITL", tone: "yellow" },
    ],
    toolCount: 3,
    callCount: 100,
    iconBg: "#FEF3C7",
    iconColor: "#D97706",
    iconType: "wrench",
    detailLink: "/test",
    detailLabel: "配置",
  },
  {
    id: "test-2",
    name: "客服 Bot",
    category: "客服",
    source: "plugin",
    sourceLabel: "插件引入",
    status: "draft",
    statusLabel: "Draft",
    description: "客服机器人",
    tags: [{ label: "多轮对话", tone: "indigo" }],
    toolCount: 2,
    callCount: 50,
    iconBg: "#DBEAFE",
    iconColor: "#2563EB",
    iconType: "chat",
    detailLink: "/test",
    detailLabel: "配置",
  },
  {
    id: "test-3",
    name: "外部 Agent",
    category: "外部",
    source: "external",
    sourceLabel: "外部接入",
    status: "stopped",
    statusLabel: "已停用",
    description: "外部接入 Agent",
    tags: [{ label: "L1 · 建议", tone: "blue" }],
    toolCount: 0,
    callCount: 10,
    iconBg: "#F3F4F6",
    iconColor: "#6B7280",
    iconType: "multi-agent",
    detailLink: "/test",
    detailLabel: "管理",
  },
];

describe("AgentRegistryPage · computeRegistryStats", () => {
  it("返回 total/active/draft/stopped 字段", () => {
    const stats = computeRegistryStats(MOCK_AGENTS_FOR_TEST);
    expect(stats).toHaveProperty("total");
    expect(stats).toHaveProperty("active");
    expect(stats).toHaveProperty("draft");
    expect(stats).toHaveProperty("stopped");
  });

  it("total 等于 Agent 总数", () => {
    const stats = computeRegistryStats(MOCK_AGENTS_FOR_TEST);
    expect(stats.total).toBe(3);
  });

  it("active 数量正确（running/ready/session 计为活跃）", () => {
    const stats = computeRegistryStats(MOCK_AGENTS_FOR_TEST);
    expect(stats.active).toBe(1);
  });

  it("draft 数量正确", () => {
    const stats = computeRegistryStats(MOCK_AGENTS_FOR_TEST);
    expect(stats.draft).toBe(1);
  });

  it("stopped 数量正确", () => {
    const stats = computeRegistryStats(MOCK_AGENTS_FOR_TEST);
    expect(stats.stopped).toBe(1);
  });

  it("总调用量正确", () => {
    const stats = computeRegistryStats(MOCK_AGENTS_FOR_TEST);
    expect(stats.totalCalls).toBe(160);
  });

  it("空数组返回全 0", () => {
    const stats = computeRegistryStats([]);
    expect(stats.total).toBe(0);
    expect(stats.active).toBe(0);
    expect(stats.avgCalls).toBe(0);
    expect(stats.guardrailCoverage).toBe(0);
  });
});

describe("AgentRegistryPage · extractAllTags", () => {
  it("返回所有去重标签", () => {
    const tags = extractAllTags(MOCK_AGENTS_FOR_TEST);
    expect(tags).toContain("工单分配");
    expect(tags).toContain("L2 · HITL");
    expect(tags).toContain("多轮对话");
    expect(tags).toContain("L1 · 建议");
  });

  it("标签去重", () => {
    const tags = extractAllTags(MOCK_AGENTS_FOR_TEST);
    const unique = new Set(tags);
    expect(tags.length).toBe(unique.size);
  });

  it("空数组返回空数组", () => {
    expect(extractAllTags([])).toEqual([]);
  });
});

describe("AgentRegistryPage · filterAgents", () => {
  it("all 返回全部", () => {
    const result = filterAgents(MOCK_AGENTS_FOR_TEST, { source: "all", status: "all", tag: "all" }, "");
    expect(result.length).toBe(3);
  });

  it("按 source 筛选 builtin", () => {
    const result = filterAgents(MOCK_AGENTS_FOR_TEST, { source: "builtin", status: "all", tag: "all" }, "");
    expect(result.length).toBe(1);
    expect(result[0].source).toBe("builtin");
  });

  it("按 source 筛选 plugin", () => {
    const result = filterAgents(MOCK_AGENTS_FOR_TEST, { source: "plugin", status: "all", tag: "all" }, "");
    expect(result.every((a) => a.source === "plugin")).toBe(true);
  });

  it("按 status 筛选 running", () => {
    const result = filterAgents(MOCK_AGENTS_FOR_TEST, { source: "all", status: "running", tag: "all" }, "");
    expect(result.every((a) => a.status === "running")).toBe(true);
  });

  it("按 status 筛选 draft", () => {
    const result = filterAgents(MOCK_AGENTS_FOR_TEST, { source: "all", status: "draft", tag: "all" }, "");
    expect(result.every((a) => a.status === "draft")).toBe(true);
  });

  it("按 tag 筛选", () => {
    const result = filterAgents(MOCK_AGENTS_FOR_TEST, { source: "all", status: "all", tag: "多轮对话" }, "");
    expect(result.length).toBe(1);
    expect(result[0].tags.some((t) => t.label === "多轮对话")).toBe(true);
  });

  it("搜索关键词匹配名称", () => {
    const result = filterAgents(MOCK_AGENTS_FOR_TEST, { source: "all", status: "all", tag: "all" }, "客服");
    expect(result.length).toBe(1);
    expect(result[0].name).toContain("客服");
  });

  it("搜索关键词匹配描述", () => {
    const result = filterAgents(MOCK_AGENTS_FOR_TEST, { source: "all", status: "all", tag: "all" }, "外部接入");
    expect(result.length).toBe(1);
  });

  it("不修改原数组", () => {
    const original = [...MOCK_AGENTS_FOR_TEST];
    filterAgents(MOCK_AGENTS_FOR_TEST, { source: "builtin", status: "all", tag: "all" }, "");
    expect(MOCK_AGENTS_FOR_TEST).toEqual(original);
  });

  it("空搜索+all 条件返回全部", () => {
    const result = filterAgents(MOCK_AGENTS_FOR_TEST, { source: "all", status: "all", tag: "all" }, "");
    expect(result.length).toBe(MOCK_AGENTS_FOR_TEST.length);
  });

  it("组合条件筛选", () => {
    const result = filterAgents(
      MOCK_AGENTS_FOR_TEST,
      { source: "builtin", status: "running", tag: "all" },
      "测试",
    );
    expect(result.length).toBe(1);
    expect(result[0].id).toBe("test-1");
  });
});

describe("AgentRegistryPage · STATUS_TABS", () => {
  it("包含 all + 5 种状态", () => {
    expect(STATUS_TABS.length).toBe(6);
  });

  it("第一个是 all", () => {
    expect(STATUS_TABS[0].id).toBe("all");
    expect(STATUS_TABS[0].label).toBe("全部状态");
  });

  it("每个状态有 label 和 color", () => {
    for (const tab of STATUS_TABS) {
      expect(tab.label.length).toBeGreaterThan(0);
      expect(tab.color.length).toBeGreaterThan(0);
    }
  });
});
