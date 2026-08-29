import { describe, expect, it } from "vitest";

import { isValidScheduleDraft, scheduleRunStatusLabel } from "./dataSchedules";

describe("schedule editor trust boundaries", () => {
  it("requires a business name, a real pipeline selection, and a five-field cycle", () => {
    expect(isValidScheduleDraft("", "P05-order-qyh", "0 6 * * *")).toBe(false);
    expect(isValidScheduleDraft("栖月汇订单每日同步", "", "0 6 * * *")).toBe(false);
    expect(isValidScheduleDraft("栖月汇订单每日同步", "P05-order-qyh", "0 6 *")).toBe(false);
    expect(isValidScheduleDraft("栖月汇订单每日同步", "P05-order-qyh", "0 6 * * *")).toBe(true);
  });

  it("normalizes run states into Chinese business labels", () => {
    expect(scheduleRunStatusLabel("SUCCEEDED")).toBe("成功");
    expect(scheduleRunStatusLabel("failed")).toBe("失败");
    expect(scheduleRunStatusLabel("IN_PROGRESS")).toBe("运行中");
    expect(scheduleRunStatusLabel("pending")).toBe("计划中");
    expect(scheduleRunStatusLabel()).toBe("未读取");
  });
});
