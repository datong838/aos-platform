import { describe, expect, it, beforeEach } from "vitest";
import {
  studioPromptKey,
  studioToolsKey,
  loadLocalPrompt,
  saveLocalPrompt,
  loadLocalTools,
  saveLocalTools,
  toggleToolId,
  toolsToCategories,
  formatStudioSaveMsg,
  mapWizardAgentToStudio,
} from "./StudioPage";
import type { AgentItem as WizardAgent } from "./s2/agentsCore";

describe("StudioPage · W2-B2 keys", () => {
  it("prompt/tools key 含 agentId", () => {
    expect(studioPromptKey("repair-buddy")).toContain("repair-buddy");
    expect(studioToolsKey("video-agent")).toContain("video-agent");
  });
});

describe("StudioPage · localStorage 演示路径", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("save/load prompt", () => {
    saveLocalPrompt("a1", "hello prompt");
    expect(loadLocalPrompt("a1", "fallback")).toBe("hello prompt");
    expect(loadLocalPrompt("missing", "fallback")).toBe("fallback");
  });

  it("save/load tools", () => {
    saveLocalTools("a1", ["t1", "t2"]);
    expect(loadLocalTools("a1", ["x"])).toEqual(["t1", "t2"]);
    expect(loadLocalTools("missing", ["x"])).toEqual(["x"]);
  });
});

describe("StudioPage · toggleToolId", () => {
  it("开启未选中工具", () => {
    expect(toggleToolId(["a"], "b")).toEqual(["a", "b"]);
  });

  it("关闭已选中工具", () => {
    expect(toggleToolId(["a", "b"], "a")).toEqual(["b"]);
  });
});

describe("StudioPage · toolsToCategories", () => {
  const catalog = [
    { id: "action.dispatch", category: "action" },
    { id: "query.device", category: "query" },
    { id: "wiki.fields", category: "wiki" },
  ];

  it("仅映射已启用工具的 category", () => {
    expect(toolsToCategories(["query.device", "wiki.fields"], catalog).sort()).toEqual([
      "query",
      "wiki",
    ]);
  });

  it("空选择返回空", () => {
    expect(toolsToCategories([], catalog)).toEqual([]);
  });
});

describe("StudioPage · formatStudioSaveMsg", () => {
  it("API 成功", () => {
    expect(formatStudioSaveMsg("api", true, "agents/prompt")).toContain("API");
  });

  it("演示路径成功", () => {
    const msg = formatStudioSaveMsg("local", true);
    expect(msg).toContain("演示路径");
    expect(msg).toContain("localStorage");
  });

  it("失败", () => {
    expect(formatStudioSaveMsg("api", false, "404")).toContain("保存失败");
  });
});

describe("StudioPage · mapWizardAgentToStudio", () => {
  it("向导 Agent 映射为 Studio 列表项（Draft）", () => {
    const wizard: WizardAgent = {
      id: "ag-x",
      name: "测试助手",
      description: "desc",
      source: "platform",
      status: "draft",
      calls: 0,
      modelId: "m1",
      prompt: "你是助手",
      icon: "chat",
      domain: "电商客服",
      level: "L2",
      tools: [{ id: "t1", name: "Object Query", kind: "API", state: "on" }],
    };
    const mapped = mapWizardAgentToStudio(wizard);
    expect(mapped.id).toBe("ag-x");
    expect(mapped.name).toBe("测试助手");
    expect(mapped.status).toBe("draft");
    expect(mapped.toolCount).toBe(1);
    expect(mapped.category).toBe("电商客服");
    expect(mapped.level).toBe("L2");
    expect(mapped.levelLabel).toBe("L2 HITL");
  });
});
