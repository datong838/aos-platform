// @vitest-environment jsdom

import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  EventsPage,
  TRIGGERS,
  ACTIONS,
  TRIGGER_LABEL,
  ACTION_LABEL,
  STATUS_META,
  MOCK_EVENTS,
  getParamFields,
  buildIdempotencyKey,
  canProceed,
  apiEventToEventItem,
  eventCreatePayload,
} from "./EventsPage";

const apiMocks = vi.hoisted(() => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
}));

vi.mock("../../api/client", () => apiMocks);

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

describe("EventsPage · TRIGGERS 触发器定义", () => {
  it("包含 6 个触发器", () => {
    expect(TRIGGERS).toHaveLength(6);
  });

  it("每个触发器有 id/name/icon/desc", () => {
    for (const t of TRIGGERS) {
      expect(t.id.length).toBeGreaterThan(0);
      expect(t.name.length).toBeGreaterThan(0);
      expect(t.icon.length).toBeGreaterThan(0);
      expect(t.desc.length).toBeGreaterThan(0);
    }
  });

  it("ID 唯一", () => {
    const ids = TRIGGERS.map((t) => t.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe("EventsPage · ACTIONS 动作定义", () => {
  it("包含后端 catalog 可表达的 7 个动作", () => {
    expect(ACTIONS).toHaveLength(7);
  });

  it("每个动作有 id/name/icon/desc/color", () => {
    for (const a of ACTIONS) {
      expect(a.id.length).toBeGreaterThan(0);
      expect(a.name.length).toBeGreaterThan(0);
      expect(a.icon.length).toBeGreaterThan(0);
      expect(a.desc.length).toBeGreaterThan(0);
      expect(a.color.length).toBeGreaterThan(0);
    }
  });

  it("ID 唯一", () => {
    const ids = ACTIONS.map((a) => a.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});

describe("EventsPage · TRIGGER_LABEL / ACTION_LABEL 映射完整", () => {
  it("TRIGGER_LABEL 覆盖所有触发器", () => {
    for (const t of TRIGGERS) {
      expect(TRIGGER_LABEL[t.id as keyof typeof TRIGGER_LABEL]).toBeTruthy();
    }
  });

  it("ACTION_LABEL 覆盖所有动作", () => {
    for (const a of ACTIONS) {
      expect(ACTION_LABEL[a.id as keyof typeof ACTION_LABEL]).toBeTruthy();
    }
  });
});

describe("EventsPage · STATUS_META 状态元数据", () => {
  it("包含 active/draft/paused 三种状态", () => {
    expect(STATUS_META.active).toBeTruthy();
    expect(STATUS_META.draft).toBeTruthy();
    expect(STATUS_META.paused).toBeTruthy();
  });

  it("每个状态有 label/bg/color", () => {
    for (const key of Object.keys(STATUS_META)) {
      const s = STATUS_META[key as keyof typeof STATUS_META];
      expect(s.label.length).toBeGreaterThan(0);
      expect(s.bg.length).toBeGreaterThan(0);
      expect(s.color.length).toBeGreaterThan(0);
    }
  });
});

describe("EventsPage · getParamFields 动态参数表单", () => {
  it("timer 触发器生成 interval 字段", () => {
    const fields = getParamFields("timer", null);
    const interval = fields.find((f) => f.key === "interval");
    expect(interval).toBeTruthy();
    expect(interval!.required).toBe(true);
    expect(interval!.type).toBe("number");
  });

  it("userAction 触发器生成 eventType select + widgetId", () => {
    const fields = getParamFields("userAction", null);
    const eventType = fields.find((f) => f.key === "eventType");
    expect(eventType).toBeTruthy();
    expect(eventType!.type).toBe("select");
    expect(eventType!.options!.length).toBeGreaterThan(0);
    expect(fields.find((f) => f.key === "widgetId")).toBeTruthy();
  });

  it("apiCallback 触发器生成 apiEndpoint", () => {
    const fields = getParamFields("apiCallback", null);
    expect(fields.find((f) => f.key === "apiEndpoint")).toBeTruthy();
  });

  it("showMessage 动作生成 messageType + messageContent", () => {
    const fields = getParamFields(null, "showMessage");
    expect(fields.find((f) => f.key === "messageType")).toBeTruthy();
    expect(fields.find((f) => f.key === "messageContent")).toBeTruthy();
  });

  it("navigate 动作生成 targetRoute", () => {
    const fields = getParamFields(null, "navigate");
    const route = fields.find((f) => f.key === "targetRoute");
    expect(route).toBeTruthy();
    expect(route!.required).toBe(true);
  });

  it("callApi 动作生成 apiAction + payload", () => {
    const fields = getParamFields(null, "callApi");
    expect(fields.find((f) => f.key === "apiAction")).toBeTruthy();
    expect(fields.find((f) => f.key === "payload")).toBeTruthy();
  });

  it("updateData 动作生成 targetVar + valueExpr", () => {
    const fields = getParamFields(null, "updateData");
    expect(fields.find((f) => f.key === "targetVar")).toBeTruthy();
    expect(fields.find((f) => f.key === "valueExpr")).toBeTruthy();
  });

  it("sendNotification 动作生成 channel + recipient", () => {
    const fields = getParamFields(null, "sendNotification");
    expect(fields.find((f) => f.key === "channel")).toBeTruthy();
    expect(fields.find((f) => f.key === "recipient")).toBeTruthy();
  });

  it("组合触发器+动作：字段叠加", () => {
    const fields = getParamFields("userAction", "updateData");
    // 触发器侧
    expect(fields.find((f) => f.key === "eventType")).toBeTruthy();
    expect(fields.find((f) => f.key === "widgetId")).toBeTruthy();
    // 动作侧
    expect(fields.find((f) => f.key === "targetVar")).toBeTruthy();
    expect(fields.find((f) => f.key === "valueExpr")).toBeTruthy();
  });

  it("null + null 返回空数组", () => {
    expect(getParamFields(null, null)).toEqual([]);
  });

  it("pageLoad 无额外触发器参数", () => {
    const fields = getParamFields("pageLoad", null);
    expect(fields).toEqual([]);
  });
});

describe("EventsPage · buildIdempotencyKey 幂等键生成", () => {
  it("基础格式：action:widget:hash", () => {
    const key = buildIdempotencyKey("callApi", "w_button_assign", { apiAction: "assignWorkOrder" });
    expect(key).toContain("callApi");
    expect(key).toContain("w_button_assign");
    expect(key).toContain("assignWorkOrder");
  });

  it("无 widgetId 用 global", () => {
    const key = buildIdempotencyKey("updateData", undefined, {});
    expect(key).toContain("global");
  });

  it("null actionId 返回空串", () => {
    expect(buildIdempotencyKey(null)).toBe("");
  });

  it("无参数用 auto 兜底", () => {
    const key = buildIdempotencyKey("callApi");
    expect(key).toBe("callApi:global:auto");
  });

  it("参数 hash 不超过 16 字符", () => {
    const longVal = "a".repeat(50);
    const key = buildIdempotencyKey("updateData", "w1", { targetVar: longVal });
    const parts = key.split(":");
    expect(parts[2].length).toBeLessThanOrEqual(16);
  });
});

describe("EventsPage · canProceed 向导步骤校验", () => {
  it("step 1：名称为空 → false", () => {
    expect(canProceed(1, { name: "", triggerId: null, actionId: null, params: {} })).toBe(false);
  });

  it("step 1：名称非空 → true", () => {
    expect(canProceed(1, { name: "事件A", triggerId: null, actionId: null, params: {} })).toBe(true);
  });

  it("step 2：未选触发器 → false", () => {
    expect(canProceed(2, { name: "事件A", triggerId: null, actionId: null, params: {} })).toBe(false);
  });

  it("step 2：已选触发器 → true", () => {
    expect(canProceed(2, { name: "事件A", triggerId: "pageLoad", actionId: null, params: {} })).toBe(true);
  });

  it("step 3：未选动作 → false", () => {
    expect(canProceed(3, { name: "事件A", triggerId: "pageLoad", actionId: null, params: {} })).toBe(false);
  });

  it("step 3：已选动作 → true", () => {
    expect(canProceed(3, { name: "事件A", triggerId: "pageLoad", actionId: "showMessage", params: {} })).toBe(true);
  });

  it("step 4：必填参数缺失 → false", () => {
    // userAction + showMessage 有必填字段 eventType/messageContent
    const result = canProceed(4, {
      name: "事件A",
      triggerId: "userAction",
      actionId: "showMessage",
      params: { eventType: "click" }, // messageContent 缺失
    });
    expect(result).toBe(false);
  });

  it("step 4：必填参数齐全 → true", () => {
    const result = canProceed(4, {
      name: "事件A",
      triggerId: "userAction",
      actionId: "showMessage",
      params: { eventType: "click", widgetId: "w1", messageType: "toast", messageContent: "hello" },
    });
    expect(result).toBe(true);
  });

  it("step 4：无参数字段 → true", () => {
    // pageLoad + showMessage（showMessage 有必填）
    const result = canProceed(4, {
      name: "事件A",
      triggerId: "pageLoad",
      actionId: "navigate",
      params: { targetRoute: "/orders" },
    });
    expect(result).toBe(true);
  });

  it("step 5：总是 true", () => {
    expect(canProceed(5, { name: "事件A", triggerId: null, actionId: null, params: {} })).toBe(true);
  });
});

describe("EventsPage · MOCK_EVENTS 初始数据", () => {
  it("有 3 条预设事件", () => {
    expect(MOCK_EVENTS.length).toBeGreaterThanOrEqual(3);
  });

  it("每条事件有完整的 id/name/triggerId/actionId/status", () => {
    for (const e of MOCK_EVENTS) {
      expect(e.id.length).toBeGreaterThan(0);
      expect(e.name.length).toBeGreaterThan(0);
      expect(e.triggerId.length).toBeGreaterThan(0);
      expect(e.actionId.length).toBeGreaterThan(0);
      expect(["active", "draft", "paused"]).toContain(e.status);
    }
  });

  it("写操作事件（callApi/updateData）已配置幂等键", () => {
    for (const e of MOCK_EVENTS) {
      if (e.actionId === "callApi" || e.actionId === "updateData") {
        if (e.idempotent) {
          expect(e.idempotencyKey).toBeTruthy();
        }
      }
    }
  });
});

describe("EventsPage · API DTO", () => {
  it("把后端 trigger/action/enabled 映射为页面事件", () => {
    expect(apiEventToEventItem({
      id: "evt-1",
      name: "选择联动",
      trigger: { type: "on_select", widgetId: "orders" },
      action: { type: "set_variable", params: { targetVar: "selected" } },
      enabled: false,
    })).toMatchObject({
      id: "evt-1",
      triggerId: "userAction",
      actionId: "updateData",
      status: "paused",
      params: { widgetId: "orders", targetVar: "selected" },
    });
  });

  it("创建 payload 保留事件语义且默认禁用", () => {
    expect(eventCreatePayload({
      name: "新事件",
      description: "说明",
      triggerId: "manual",
      actionId: "showMessage",
      params: { messageContent: "完成" },
      idempotent: false,
    })).toMatchObject({
      name: "新事件",
      trigger: { type: "custom" },
      action: { type: "show_notification", uiType: "showMessage", description: "说明" },
      enabled: false,
    });
  });

  it("创建 payload 满足 trigger/action catalog 必填字段", () => {
    const timer = eventCreatePayload({
      name: "定时",
      description: "",
      triggerId: "timer",
      actionId: "callApi",
      params: { interval: "30", apiAction: "refreshOrders" },
      idempotent: true,
      idempotencyKey: "refresh",
    });
    expect(timer).toMatchObject({
      trigger: { type: "interval", value: 30, unit: "seconds" },
      action: { type: "call_function", target: "refreshOrders" },
    });

    const changed = eventCreatePayload({
      name: "变量变更",
      description: "",
      triggerId: "dataChange",
      actionId: "updateData",
      params: { variableId: "orders", targetVar: "filteredOrders" },
      idempotent: true,
    });
    expect(changed).toMatchObject({
      trigger: { type: "on_change", variableId: "orders" },
      action: { type: "set_variable", target: "filteredOrders" },
    });
  });

  it("覆盖后端扩展动作，未知类型显式失败", () => {
    expect(apiEventToEventItem({ id: "f", action: { type: "call_function" }, trigger: { type: "on_load" } }).actionId).toBe("callApi");
    expect(apiEventToEventItem({ id: "n", action: { type: "show_notification" }, trigger: { type: "on_load" } }).actionId).toBe("showMessage");
    expect(apiEventToEventItem({ id: "o", action: { type: "open_overlay" }, trigger: { type: "on_load" } }).actionId).toBe("openOverlay");
    expect(apiEventToEventItem({ id: "e", action: { type: "export_data" }, trigger: { type: "on_load" } }).actionId).toBe("exportData");
    expect(() => apiEventToEventItem({ id: "bad", action: { type: "unknown" }, trigger: { type: "on_load" } })).toThrow("不支持的事件动作类型");
    expect(() => apiEventToEventItem({ id: "bad", action: { type: "query" }, trigger: { type: "unknown" } })).toThrow("不支持的事件触发器类型");
  });
});

describe("EventsPage · 真实 CRUD 交互", () => {
  let host: HTMLDivElement;
  let root: Root;

  const serverEvent = {
    id: "evt-1",
    name: "真实事件",
    trigger: { type: "manual", params: {} },
    action: { type: "showMessage", params: { messageType: "toast", messageContent: "完成" } },
    enabled: true,
  };
  const serverModule = { id: "mod-real", name: "真实应用" };

  async function flush() {
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
  }

  function button(label: string): HTMLButtonElement {
    const found = Array.from(host.querySelectorAll("button")).find((node) => node.textContent?.includes(label));
    if (!found) throw new Error(`button not found: ${label}`);
    return found;
  }

  function setValue(element: HTMLInputElement | HTMLTextAreaElement, value: string) {
    const prototype = element instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(prototype, "value")?.set?.call(element, value);
    element.dispatchEvent(new Event("input", { bubbles: true }));
    element.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function clickText(label: string) {
    const found = Array.from(host.querySelectorAll("*")).find((node) => node.textContent === label);
    if (!found) throw new Error(`text not found: ${label}`);
    found.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  }

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    apiMocks.apiGet.mockReset();
    apiMocks.apiPost.mockReset();
    apiMocks.apiPut.mockReset();
    apiMocks.apiDelete.mockReset();
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
  });

  it("启停和删除成功后调用真实 API 并重读", async () => {
    let reads = 0;
    apiMocks.apiGet.mockImplementation(async (path: string) => {
      if (path === "/v1/modules") return { items: [serverModule] };
      if (path === "/v1/modules/mod-real/events") {
        reads += 1;
        if (reads === 1) return { items: [serverEvent] };
        if (reads === 2) return { items: [{ ...serverEvent, enabled: false }] };
        return { items: [] };
      }
      throw new Error(path);
    });
    apiMocks.apiPut.mockResolvedValue({ ok: true, item: { ...serverEvent, enabled: false } });
    apiMocks.apiDelete.mockResolvedValue({ ok: true });

    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(EventsPage)));
    });
    await flush();

    await act(async () => button("暂停").click());
    await flush();
    expect(apiMocks.apiPut).toHaveBeenCalledWith("/v1/modules/mod-real/events/evt-1", { enabled: false });
    expect(host.textContent).toContain("已暂停");

    await act(async () => button("删除").click());
    await flush();
    expect(apiMocks.apiDelete).toHaveBeenCalledWith("/v1/modules/mod-real/events/evt-1");
    expect(host.textContent).toContain("暂无事件");
  });

  it("写 API 回包不可信时保留服务端列表并显示错误", async () => {
    apiMocks.apiGet.mockImplementation(async (path: string) => path === "/v1/modules"
      ? { items: [serverModule] }
      : { items: [serverEvent] });
    apiMocks.apiPut.mockResolvedValue({ ok: true, item: { ...serverEvent, enabled: true } });

    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(EventsPage)));
    });
    await flush();
    await act(async () => button("暂停").click());
    await flush();

    expect(host.textContent).toContain("更新 API 回包与目标状态不一致");
    expect(host.textContent).toContain("运行中");
    expect(apiMocks.apiGet).toHaveBeenCalledTimes(2);
  });

  it("完成向导后 POST 创建并以服务端重读结果展示", async () => {
    const created = {
      ...serverEvent,
      id: "evt-created",
      name: "导航事件",
      trigger: { type: "manual", params: { targetRoute: "/orders" } },
      action: { type: "navigate", params: { targetRoute: "/orders" } },
      enabled: false,
    };
    let eventReads = 0;
    apiMocks.apiGet.mockImplementation(async (path: string) => {
      if (path === "/v1/modules") return { items: [serverModule] };
      if (path === "/v1/modules/mod-real/events") {
        eventReads += 1;
        return { items: eventReads === 1 ? [] : [created] };
      }
      throw new Error(path);
    });
    apiMocks.apiPost.mockResolvedValue({ ok: true, item: created });

    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(EventsPage)));
    });
    await flush();
    await act(async () => button("添加事件").click());
    const nameInput = host.querySelector('input[placeholder="如：选中订单写入变量"]') as HTMLInputElement;
    await act(async () => setValue(nameInput, "导航事件"));
    expect(button("下一步").disabled).toBe(false);
    await act(async () => button("下一步").click());
    await flush();
    await act(async () => clickText("手动触发"));
    await act(async () => button("下一步").click());
    await flush();
    await act(async () => clickText("跳转页面"));
    await act(async () => button("下一步").click());
    await flush();
    const routeInput = host.querySelector('input[placeholder="/orders/{row.id}"]') as HTMLInputElement;
    await act(async () => setValue(routeInput, "/orders"));
    await act(async () => button("下一步").click());
    await flush();
    await act(async () => button("完成创建").click());
    await flush();

    expect(apiMocks.apiPost).toHaveBeenCalledWith(
      "/v1/modules/mod-real/events",
      expect.objectContaining({
        name: "导航事件",
        trigger: expect.objectContaining({ type: "custom" }),
        action: expect.objectContaining({ type: "navigate" }),
        enabled: false,
      }),
    );
    expect(host.textContent).toContain("已创建并从服务端重读");
    expect(host.textContent).toContain("已暂停");
  });

  it("无真实应用时添加事件禁用且不发送写请求", async () => {
    apiMocks.apiGet.mockResolvedValue({ items: [] });
    await act(async () => {
      root.render(createElement(MemoryRouter, null, createElement(EventsPage)));
    });
    await flush();

    expect(button("添加事件").disabled).toBe(true);
    expect(host.textContent).toContain("请先新建或选择真实应用");
    expect(apiMocks.apiPost).not.toHaveBeenCalled();
    expect(apiMocks.apiPut).not.toHaveBeenCalled();
    expect(apiMocks.apiDelete).not.toHaveBeenCalled();
  });
});
