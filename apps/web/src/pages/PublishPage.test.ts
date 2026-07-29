import { describe, expect, it } from "vitest";
import {
  PUBLISH_ENVS,
  envStepIndex,
  stepState,
  pickLatestByEnv,
  formatPublishResult,
  type DeploymentItem,
} from "./PublishPage";

describe("PublishPage · PUBLISH_ENVS", () => {
  it("四环境顺序：开发→测试→预发布→生产", () => {
    expect(PUBLISH_ENVS.map((e) => e.id)).toEqual(["dev", "test", "staging", "prod"]);
    expect(PUBLISH_ENVS.map((e) => e.label)).toEqual(["开发", "测试", "预发布", "生产"]);
  });
});

describe("PublishPage · stepState", () => {
  it("current 之前为 done", () => {
    expect(stepState(0, "staging")).toBe("done");
    expect(stepState(1, "staging")).toBe("done");
  });

  it("当前环境为 current", () => {
    expect(stepState(2, "staging")).toBe("current");
    expect(envStepIndex("staging")).toBe(2);
  });

  it("之后为 pending", () => {
    expect(stepState(3, "staging")).toBe("pending");
  });
});

describe("PublishPage · pickLatestByEnv", () => {
  it("按 environment 取首条（列表已按时间倒序）", () => {
    const items: DeploymentItem[] = [
      { id: "d1", environment: "dev", status: "success", version: "1.0.1" },
      { id: "d0", environment: "dev", status: "success", version: "1.0.0" },
      { id: "s1", environment: "staging", status: "success", version: "1.0.0" },
    ];
    const map = pickLatestByEnv(items);
    expect(map.dev?.id).toBe("d1");
    expect(map.staging?.version).toBe("1.0.0");
    expect(map.prod).toBeUndefined();
  });
});

describe("PublishPage · formatPublishResult", () => {
  it("成功文案含 id/环境/状态", () => {
    const msg = formatPublishResult({
      ok: true,
      moduleId: "m1",
      env: "staging",
      status: "ACCEPTED",
      idempotent: true,
    });
    expect(msg).toContain("m1");
    expect(msg).toContain("staging");
    expect(msg).toContain("ACCEPTED");
    expect(msg).toContain("幂等");
  });

  it("失败文案", () => {
    expect(formatPublishResult({ ok: false, error: "boom" })).toContain("发布失败");
  });
});
