import { describe, expect, it } from "vitest";

import { buildCountLabel, buildStageLabel } from "./data";

describe("build history business projection", () => {
  it("does not convert missing counts into business zero", () => {
    expect(buildCountLabel()).toBe("未读取");
    expect(buildCountLabel(0)).toBe("0");
    expect(buildCountLabel(936)).toBe("936");
  });

  it("renders pipeline stages as Chinese business steps", () => {
    expect(buildStageLabel("ingest")).toBe("读取数据");
    expect(buildStageLabel("transform")).toBe("处理数据");
    expect(buildStageLabel("sink")).toBe("写入数据");
    expect(buildStageLabel("")).toBe("未命名阶段");
  });
});
