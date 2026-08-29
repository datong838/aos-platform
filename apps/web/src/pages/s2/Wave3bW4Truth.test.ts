import { describe, expect, it } from "vitest";
import {
  configFromTheme,
  themeTokensFromConfig,
} from "./StylesPage";
import {
  apiItemToWidgetItem,
  businessWidgetDescription,
  canvasUsePath,
} from "./WidgetRegistryPage";
import {
  sourceCreatePayload,
  datasetRidForSync,
  firstInstalledConnectorId,
  filterSources,
  scheduleBusinessDisplay,
  scheduleForSync,
  requestedInstalledConnectorId,
  verifyCreatedSource,
} from "../DataPage";
import { runtimeLabel, sourceBusinessName } from "./dataConnectionUi";
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

  it("面向业务页面的组件说明不暴露方案号和实现术语", () => {
    expect(businessWidgetDescription("ObjectSet Widget · scheme 223 · source=object-sets（非 G6 · 106）"))
      .toBe("对象集 组件");
    expect(businessWidgetDescription("AIP Assist overlay 触发 Action（106）"))
      .toBe("智能助手 浮层 触发 业务动作");
    expect(businessWidgetDescription("Tabs + Selection + Wiki · count/sum，trend 按 dateField 聚合 N 天"))
      .toBe("分类标签 + 选择联动 + 知识说明 · 计数与汇总，趋势 按 日期字段 聚合 指定天数");
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

  it("数据源类型与状态筛选会真实改变当前集合", () => {
    const rows = [
      { id: "niushop-qyh", type: "jdbc-mysql-ssh", status: "active" },
      { id: "upload", type: "file-local", status: "error" },
    ];
    expect(filterSources(rows, "jdbc", "online").map((item) => item.id)).toEqual(["niushop-qyh"]);
    expect(filterSources(rows, "file", "attention").map((item) => item.id)).toEqual(["upload"]);
  });

  it("栖月汇数据源与本机代理在业务主视图使用中文名称", () => {
    expect(sourceBusinessName({ id: "niushop-qyh", type: "jdbc-mysql-ssh" })).toBe("栖月汇微商城");
    expect(runtimeLabel({ id: "niushop-qyh", runtimeMode: "agent" })).toBe("本机边缘代理");
  });

  it("新建向导只从服务端目录选择首个已安装连接器", () => {
    expect(firstInstalledConnectorId([
      { id: "unavailable", installed: false },
      { id: "file-local", installed: true },
      { id: "jdbc-mysql", installed: true },
    ])).toBe("file-local");
    expect(firstInstalledConnectorId([{ id: "unavailable", installed: false }])).toBe("");
    expect(requestedInstalledConnectorId([
      { id: "file-local", installed: true },
      { id: "jdbc-mysql", installed: true },
    ], "jdbc-mysql")).toBe("jdbc-mysql");
    expect(requestedInstalledConnectorId([
      { id: "file-local", installed: true },
      { id: "jdbc-postgres", installed: false },
    ], "jdbc-postgres")).toBe("file-local");
  });

  it("每条同步精确关联自身管道的数据集与计划", () => {
    const sync = { id: "run-1", pipelineId: "pipe-2", scheduleId: "schedule-2", sourceId: "source-1" };
    expect(datasetRidForSync(sync, [
      { rid: "dataset-1", pipelineId: "pipe-1", sourceId: "source-1" },
      { rid: "dataset-2", pipelineId: "pipe-2", sourceId: "source-1" },
    ])).toBe("dataset-2");
    expect(scheduleForSync(sync, [
      { id: "schedule-1", pipelineId: "pipe-1", cron: "0 9 * * *" },
      { id: "schedule-2", pipelineId: "pipe-2", cron: "30 11 * * *" },
    ])?.id).toBe("schedule-2");
    expect(scheduleBusinessDisplay({ cron: "30 11 * * *" })).toEqual({ business: "每日 11:30", raw: "30 11 * * *" });
  });

  it("没有精确管道或计划关联时保持未读取，不借用同源记录", () => {
    const sync = { id: "run-1", pipelineId: "missing", sourceId: "source-1" };
    expect(datasetRidForSync(sync, [{ rid: "dataset-1", pipelineId: "pipe-1", sourceId: "source-1" }])).toBeUndefined();
    expect(scheduleForSync(sync, [{ id: "schedule-1", pipelineId: "pipe-1", cron: "0 9 * * *" }])).toBeUndefined();
    expect(scheduleBusinessDisplay()).toEqual({ business: "未读取" });
  });
});

describe("Wave3B W4 · 成熟度熔断真实性", () => {
  it("仅以服务端明确 open + L3 响应确认熔断", () => {
    expect(isBreakerTripConfirmed({ open: true, mode: "L3" })).toBe(true);
    expect(isBreakerTripConfirmed({ open: false, mode: "L3" })).toBe(false);
    expect(isBreakerTripConfirmed({ open: true, mode: "L4" })).toBe(false);
  });
});
