import { describe, expect, it } from "vitest";

import {
  buildExactContextHref,
  readExactRef,
  readSafeReturnTo,
  writeExactRef,
} from "./aipExactContext";

describe("AIP exact 跨页上下文", () => {
  const taskRef = { resourceType: "Task", resourceId: "task-1", revision: "7", authority: "aip-task-store" };

  it("资源引用必须同时包含类型、标识、修订和 authority", () => {
    expect(readExactRef(new URLSearchParams("taskType=Task&taskId=task-1&taskRevision=7&taskAuthority=aip-task-store"), "task")).toEqual(taskRef);
    expect(readExactRef(new URLSearchParams("taskType=Task&taskId=task-1&taskAuthority=aip-task-store"), "task")).toBeNull();
    expect(readExactRef(new URLSearchParams("taskType=Task&taskId=task-1&taskRevision=0&taskAuthority=aip-task-store"), "task")).toBeNull();
  });

  it("编码和读取保持 exact ref、cutoff 与同源返回路径", () => {
    const params = new URLSearchParams();
    writeExactRef(params, "task", taskRef);
    const href = buildExactContextHref("/aip/assist", {
      params,
      cutoffAt: "2026-08-30T04:00:00.000Z",
      returnTo: "/aip/logic?view=run",
    });
    const url = new URL(href, "http://aos.local");
    expect(readExactRef(url.searchParams, "task")).toEqual(taskRef);
    expect(url.searchParams.get("cutoffAt")).toBe("2026-08-30T04:00:00.000Z");
    expect(readSafeReturnTo(url.searchParams)).toBe("/aip/logic?view=run");
  });

  it("拒绝外站、协议相对和包含控制字符的返回地址", () => {
    for (const value of ["https://evil.example", "//evil.example", "/aip/logic\\evil", "/aip/logic\nnext"]) {
      expect(readSafeReturnTo(new URLSearchParams({ returnTo: value }))).toBeNull();
    }
  });
});
