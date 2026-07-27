import { describe, expect, it } from "vitest";
import {
  detectPermissions,
  extractCodeSuggestions,
  tokenizeForStream,
  generateOfflineResponse,
} from "./AipAssistPage";

describe("Phase 1 · AIP Assist 纯函数", () => {
  describe("detectPermissions", () => {
    it("API permissions 优先", () => {
      expect(detectPermissions("任意文本", ["read"])).toEqual(["read"]);
      expect(detectPermissions("任意文本", ["edit", "delete"])).toEqual(["edit", "delete"]);
    });

    it("识别查看/只读 → read", () => {
      const r = detectPermissions("查看笔记本列表，搜索文档");
      expect(r).toContain("read");
    });

    it("识别编辑/修改 → edit", () => {
      const r = detectPermissions("请编辑并更新这条记录");
      expect(r).toContain("edit");
    });

    it("识别删除 → delete", () => {
      const r = detectPermissions("删除该对象，移除关联");
      expect(r).toContain("delete");
    });

    it("无任何关键词 → authorized", () => {
      const r = detectPermissions("您好，欢迎使用平台");
      expect(r).toContain("authorized");
    });
  });

  describe("extractCodeSuggestions", () => {
    it("抽取单个代码块", () => {
      const text = "前文\n```python\nprint('hi')\n```\n后文";
      const list = extractCodeSuggestions(text);
      expect(list).toHaveLength(1);
      expect(list[0].language).toBe("python");
      expect(list[0].diff).toContain("print('hi')");
      expect(list[0].status).toBe("pending");
    });

    it("抽取多个代码块", () => {
      const text = "```js\nfoo()\n```\n中间\n```ts\nbar()\n```";
      const list = extractCodeSuggestions(text);
      expect(list).toHaveLength(2);
    });

    it("无代码块返回空数组", () => {
      expect(extractCodeSuggestions("纯文本无代码")).toEqual([]);
    });

    it("无语言标识也兼容", () => {
      const text = "```\ncode only\n```";
      const list = extractCodeSuggestions(text);
      expect(list).toHaveLength(1);
      expect(list[0].language).toBe("text");
    });
  });

  describe("tokenizeForStream", () => {
    it("普通文本切片", () => {
      const tokens = tokenizeForStream("abc");
      expect(tokens.join("")).toBe("abc");
    });

    it("标点单独成片", () => {
      const tokens = tokenizeForStream("你好，世界。");
      expect(tokens.join("")).toBe("你好，世界。");
      // 逗号应单独一片
      expect(tokens).toContain("，");
      expect(tokens).toContain("。");
    });

    it("换行包含在片段中", () => {
      const tokens = tokenizeForStream("a\nb");
      expect(tokens.join("")).toBe("a\nb");
      // 换行符会出现在某个片段中（不单独成片，但整体可拼接）
      expect(tokens.some((t) => t.includes("\n"))).toBe(true);
    });
  });

  describe("generateOfflineResponse", () => {
    it("分享笔记本 → 含分享关键词", () => {
      const r = generateOfflineResponse("如何分享笔记本？");
      expect(r).toContain("分享");
      expect(r).toContain("权限");
    });

    it("嵌入应用 → 含 Embed", () => {
      const r = generateOfflineResponse("如何嵌入应用内容？");
      expect(r).toContain("Embed");
    });

    it("Object Set 绑定", () => {
      const r = generateOfflineResponse("如何绑定 Object Set？");
      expect(r).toContain("Object Set");
    });

    it("Agent 工具面板", () => {
      const r = generateOfflineResponse("配置 Agent 工具面板");
      expect(r).toContain("工具");
    });

    it("兜底回复含原问题", () => {
      const r = generateOfflineResponse("随机问题 xyz");
      expect(r).toContain("随机问题 xyz");
    });
  });
});
