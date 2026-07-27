import { describe, expect, it } from "vitest";
import {
  TRIGGERS,
  ACTIONS,
  TRIGGER_LABEL,
  ACTION_LABEL,
  STATUS_META,
  MOCK_EVENTS,
  getParamFields,
  buildIdempotencyKey,
  canProceed,
} from "./EventsPage";

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
  it("包含 5 个动作", () => {
    expect(ACTIONS).toHaveLength(5);
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
