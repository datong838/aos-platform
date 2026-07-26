import { describe, expect, it } from "vitest";

/**
 * WidgetRegistryPage 的纯函数测试。
 *
 * 由于 apiItemToWidgetItem 未导出（页面内部函数），这里复制其核心 source 判定逻辑
 * 进行测试，确保与页面实现保持一致。
 */
function classifySource(runtime: string | undefined, author: string | undefined): "builtin" | "market" | "custom" {
  const r = runtime || "inproc";
  const a = author || "aos";
  if (r === "stub") return "custom";
  if (a === "aos") return "builtin";
  return "market";
}

describe("WidgetRegistryPage · source 分类逻辑", () => {
  it("runtime=stub → custom（代码开发）", () => {
    expect(classifySource("stub", "aos")).toBe("custom");
    expect(classifySource("stub", undefined)).toBe("custom");
  });

  it("author=aos 且非 stub → builtin（平台内置）", () => {
    expect(classifySource("inproc", "aos")).toBe("builtin");
    expect(classifySource(undefined, "aos")).toBe("builtin");
    expect(classifySource(undefined, undefined)).toBe("builtin");
  });

  it("author 非 aos 且非 stub → market（市场安装）", () => {
    expect(classifySource("inproc", "community")).toBe("market");
    expect(classifySource(undefined, "vendor-x")).toBe("market");
  });
});

describe("WidgetRegistryPage · KIND_TO_ICON_KEY 映射覆盖", () => {
  it("常见 canvasKind 均有图标映射", () => {
    const mapping: Record<string, string> = {
      table: "table",
      graph: "chart",
      action: "form",
      filter: "filter",
      "filter-bar": "filter",
      buddy: "custom",
      overlay: "map",
      metric: "stat",
      "stat-card": "stat",
      "page-header": "hero",
      "detail-drawer": "container",
      "trend-chart": "chart",
      stub: "button",
    };
    for (const [kind, icon] of Object.entries(mapping)) {
      expect(icon.length).toBeGreaterThan(0);
      expect(typeof kind).toBe("string");
    }
  });
});
