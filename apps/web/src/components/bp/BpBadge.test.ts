import { describe, expect, it } from "vitest";
import { getBadgeClassName, type BpBadgeVariant, type BpBadgeSize } from "./BpBadge";

describe("getBadgeClassName", () => {
  it("基础类名包含 bp-badge", () => {
    const cls = getBadgeClassName("default", "md");
    expect(cls).toContain("bp-badge");
    expect(cls).toContain("bp-badge-default");
  });

  it("所有 7 种 variant 都生成对应类名", () => {
    const variants: BpBadgeVariant[] = [
      "default",
      "success",
      "warning",
      "danger",
      "info",
      "purple",
      "teal",
    ];
    for (const v of variants) {
      const cls = getBadgeClassName(v, "md");
      expect(cls).toContain(`bp-badge-${v}`);
    }
  });

  it("所有 3 种 size 都生成对应类名", () => {
    const sizes: BpBadgeSize[] = ["sm", "md", "lg"];
    for (const s of sizes) {
      const cls = getBadgeClassName("info", s);
      expect(cls).toContain(`bp-badge-${s}`);
    }
  });

  it("dot=true 时追加 bp-badge-dot 类", () => {
    const cls = getBadgeClassName("success", "md", true);
    expect(cls).toContain("bp-badge-dot");
  });

  it("dot=false（默认）时不追加 bp-badge-dot 类", () => {
    const cls = getBadgeClassName("success", "md", false);
    expect(cls).not.toContain("bp-badge-dot");
  });

  it("组合 variant + size + dot 生成完整类名", () => {
    const cls = getBadgeClassName("danger", "lg", true);
    expect(cls).toBe("bp-badge bp-badge-danger bp-badge-lg bp-badge-dot");
  });
});
