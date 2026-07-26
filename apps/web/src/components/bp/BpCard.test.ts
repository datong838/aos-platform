import { describe, expect, it } from "vitest";
import {
  getCardClassName,
  type BpCardVariant,
  type BpCardPadding,
} from "./BpCard";

describe("getCardClassName", () => {
  it("基础类名包含 bp-card", () => {
    const cls = getCardClassName("default", "md");
    expect(cls).toContain("bp-card");
    expect(cls).toContain("bp-card-default");
    expect(cls).toContain("bp-card-pad-md");
  });

  it("所有 4 种 variant 都生成对应类名", () => {
    const variants: BpCardVariant[] = ["default", "outlined", "elevated", "filled"];
    for (const v of variants) {
      const cls = getCardClassName(v, "md");
      expect(cls).toContain(`bp-card-${v}`);
    }
  });

  it("所有 4 种 padding 都生成对应类名", () => {
    const paddings: BpCardPadding[] = ["none", "sm", "md", "lg"];
    for (const p of paddings) {
      const cls = getCardClassName("default", p);
      expect(cls).toContain(`bp-card-pad-${p}`);
    }
  });

  it("hover=true 时追加 bp-card-hover 类", () => {
    const cls = getCardClassName("elevated", "md", true);
    expect(cls).toContain("bp-card-hover");
  });

  it("hover=false（默认）时不追加 bp-card-hover 类", () => {
    const cls = getCardClassName("elevated", "md", false);
    expect(cls).not.toContain("bp-card-hover");
  });

  it("clickable=true 时追加 bp-card-clickable 类", () => {
    const cls = getCardClassName("default", "md", false, true);
    expect(cls).toContain("bp-card-clickable");
  });

  it("clickable=false（默认）时不追加 bp-card-clickable 类", () => {
    const cls = getCardClassName("default", "md", false, false);
    expect(cls).not.toContain("bp-card-clickable");
  });

  it("全组合：elevated + lg + hover + clickable", () => {
    const cls = getCardClassName("elevated", "lg", true, true);
    expect(cls).toContain("bp-card-elevated");
    expect(cls).toContain("bp-card-pad-lg");
    expect(cls).toContain("bp-card-hover");
    expect(cls).toContain("bp-card-clickable");
  });
});
