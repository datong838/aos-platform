import { describe, expect, it } from "vitest";
import {
  configFromTheme,
  themeTokensFromConfig,
} from "./StylesPage";
import {
  apiItemToWidgetItem,
  canvasUsePath,
} from "./WidgetRegistryPage";
import {
  sourceCreatePayload,
  verifyCreatedSource,
} from "../DataPage";
import { isBreakerTripConfirmed } from "./extras";
import { resolveRequestedPaletteItem } from "../CanvasPage";

describe("Wave3B W4 · Styles 服务器快照契约", () => {
  it("以服务端 tokens 还原编辑器配置，而不是按 mode 猜默认值", () => {
    const config = configFromTheme({
      id: "theme-x",
      name: "X",
      mode: "dark",
      tokens: {
        colorPrimary: "#123456",
        colorBgBase: "#202124",
        colorTextBase: "#fefefe",
        colorBorder: "#303134",
        fontSize: 16,
        lineHeight: 1.8,
      },
    });
    expect(config.primary).toBe("#123456");
    expect(config.bg).toBe("#202124");
    expect(config.text).toBe("#fefefe");
    expect(config.fontSize).toBe(16);
    expect(config.lineHeight).toBe(1.8);
  });

  it("把编辑器配置稳定序列化为后端 token 契约", () => {
    const tokens = themeTokensFromConfig(configFromTheme({ id: "x", name: "X", mode: "light", tokens: {} }));
    expect(tokens).toMatchObject({
      colorPrimary: expect.stringMatching(/^#/),
      colorBgBase: expect.stringMatching(/^#/),
      colorTextBase: expect.stringMatching(/^#/),
      fontSize: expect.any(Number),
      spacingBase: expect.any(Number),
    });
  });
});

describe("Wave3B W4 · Widget 目录到画布契约", () => {
  it("保留 installed 与 canvasKind，只有可用插件才允许进画布", () => {
    const item = apiItemToWidgetItem({
      id: "metric-card",
      nameZh: "指标卡",
      canvasKind: "metric",
      installed: true,
    });
    expect(item.installed).toBe(true);
    expect(item.canvasKind).toBe("metric");
    expect(canvasUsePath(item)).toBe("/workshop/canvas?pluginId=metric-card&canvasKind=metric");
  });

  it("未知画布类型必须 fail closed", () => {
    const item = apiItemToWidgetItem({ id: "no-canvas", installed: true });
    expect(canvasUsePath(item)).toBeNull();
  });

  it("画布只接受目录中 pluginId 与 canvasKind 同时匹配的已安装项", () => {
    const palette = [{ kind: "metric" as const, label: "+ 指标卡", pluginId: "metric-card" }];
    expect(resolveRequestedPaletteItem(palette, "?pluginId=metric-card&canvasKind=metric")).toEqual(palette[0]);
    expect(resolveRequestedPaletteItem(palette, "?pluginId=unknown&canvasKind=metric")).toBeNull();
    expect(resolveRequestedPaletteItem(palette, "?pluginId=metric-card&canvasKind=table")).toBeNull();
  });
});

describe("Wave3B W4 · Source 运行时持久化与写后重读", () => {
  it("创建请求包含服务端持久化的 runtimeMode", () => {
    expect(sourceCreatePayload("src-1", "file-local", "worker")).toEqual({
      id: "src-1",
      type: "file-local",
      runtimeMode: "worker",
    });
  });

  it("仅接受 GET 重读后 id 与 runtimeMode 一致的源", () => {
    expect(verifyCreatedSource([{ id: "src-1", runtimeMode: "agent" }], "src-1", "agent")).toBe(true);
    expect(verifyCreatedSource([{ id: "src-1" }], "src-1", "agent")).toBe(false);
    expect(verifyCreatedSource([{ id: "src-2", runtimeMode: "agent" }], "src-1", "agent")).toBe(false);
  });
});

describe("Wave3B W4 · 成熟度熔断真实性", () => {
  it("仅以服务端明确 open + L3 响应确认熔断", () => {
    expect(isBreakerTripConfirmed({ open: true, mode: "L3" })).toBe(true);
    expect(isBreakerTripConfirmed({ open: false, mode: "L3" })).toBe(false);
    expect(isBreakerTripConfirmed({ open: true, mode: "L4" })).toBe(false);
  });
});
