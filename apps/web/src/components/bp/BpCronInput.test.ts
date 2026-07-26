import { describe, expect, it } from "vitest";
import { isValidCron, describeCron } from "./BpCronInput";

describe("isValidCron", () => {
  it("接受标准 5 段通配", () => {
    expect(isValidCron("* * * * *")).toBe(true);
  });
  it("接受步长与列表", () => {
    expect(isValidCron("*/5 * * * *")).toBe(true);
    expect(isValidCron("0,30 * * * *")).toBe(true);
    expect(isValidCron("0 0 1,15 * *")).toBe(true);
  });
  it("接受范围", () => {
    expect(isValidCron("0 9-17 * * 1-5")).toBe(true);
  });
  it("拒绝段数不足", () => {
    expect(isValidCron("* * * *")).toBe(false);
    expect(isValidCron("* * * * * *")).toBe(false);
  });
  it("拒绝越界值", () => {
    expect(isValidCron("60 * * * *")).toBe(false);
    expect(isValidCron("* 24 * * *")).toBe(false);
    expect(isValidCron("* * 32 * *")).toBe(false);
    expect(isValidCron("* * * 13 *")).toBe(false);
    expect(isValidCron("* * * * 7")).toBe(false);
  });
  it("拒绝非数字", () => {
    expect(isValidCron("abc * * * *")).toBe(false);
  });
  it("拒绝无效步长", () => {
    expect(isValidCron("*/0 * * * *")).toBe(false);
    expect(isValidCron("*/x * * * *")).toBe(false);
  });
});

describe("describeCron", () => {
  it("每 5 分钟", () => {
    expect(describeCron("*/5 * * * *")).toBe("每 5 分钟");
  });
  it("每小时整点", () => {
    expect(describeCron("0 * * * *")).toBe("每小时整点");
  });
  it("每天 00:00", () => {
    expect(describeCron("0 0 * * *")).toBe("每天 00:00");
  });
  it("每周日", () => {
    expect(describeCron("0 0 * * 0")).toBe("每周日 00:00");
  });
  it("每月 1 日", () => {
    expect(describeCron("0 0 1 * *")).toBe("每月 1 日 00:00");
  });
  it("自定义模式回退", () => {
    expect(describeCron("30 14 * * *")).toBe("自定义：30 14 * * *");
  });
  it("无效表达式", () => {
    expect(describeCron("invalid")).toBe("无效表达式");
  });
});
