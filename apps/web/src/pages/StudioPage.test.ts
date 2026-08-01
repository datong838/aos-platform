import { describe, expect, it } from "vitest";
import {
  formatStudioSaveMsg,
  mapApiAgentToStudio,
  sameToolIds,
  toggleToolId,
  validateAgentToolsResponse,
  validatePromptResponse,
} from "./StudioPage";

describe("StudioPage · Agent API 映射", () => {
  it("列表响应映射为 Studio 项且不注入硬编码 Agent", () => {
    const mapped = mapApiAgentToStudio({
      id: "ag-1",
      name: "订单助手",
      description: "处理订单",
      source: "custom",
      tags: ["电商", "L2"],
      status: "draft",
      calls: 3,
    });
    expect(mapped.id).toBe("ag-1");
    expect(mapped.name).toBe("订单助手");
    expect(mapped.category).toBe("电商");
    expect(mapped.status).toBe("draft");
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

describe("StudioPage · 写后重读严格核验", () => {
  it("Prompt 回包必须匹配 agent 与冻结 prompt", () => {
    expect(validatePromptResponse({ ok: true, agent_id: "a1", prompt: "hello" }, "a1", "hello")).toBe(true);
    expect(validatePromptResponse({ ok: true, agent_id: "other", prompt: "hello" }, "a1", "hello")).toBe(false);
    expect(validatePromptResponse({ ok: true, agent_id: "a1", prompt: "stale" }, "a1", "hello")).toBe(false);
  });

  it("Tools 回包必须匹配 agent 与完整 ID 集合", () => {
    const response = { agent_id: "a1", items: [{ id: "t2" }, { id: "t1" }] };
    expect(validateAgentToolsResponse(response, "a1", ["t1", "t2"])).toBe(true);
    expect(validateAgentToolsResponse(response, "other", ["t1", "t2"])).toBe(false);
    expect(validateAgentToolsResponse(response, "a1", ["t1"])).toBe(false);
    expect(sameToolIds(["t2", "t1"], ["t1", "t2"])).toBe(true);
  });
});

describe("StudioPage · 保存文案", () => {
  it("仅 API 核验成功可报告已保存", () => {
    expect(formatStudioSaveMsg(true, "agents/prompt")).toContain("已保存并完成重读核验");
    expect(formatStudioSaveMsg(false, "重读不一致")).toContain("核验失败");
    expect(formatStudioSaveMsg(true)).not.toContain("localStorage");
  });
});
