import { describe, expect, it } from "vitest";
import {
  getLayerStyle,
  DEFAULT_ARCH_LAYERS,
  type BpArchLayerId,
} from "./BpArchitectureBar";

describe("DEFAULT_ARCH_LAYERS", () => {
  it("包含 L1→L2→L3→AIP 四层且顺序正确", () => {
    const ids = DEFAULT_ARCH_LAYERS.map((l) => l.id);
    expect(ids).toEqual(["L1", "L2", "L3", "AIP"]);
  });

  it("每层有非空 label", () => {
    for (const layer of DEFAULT_ARCH_LAYERS) {
      expect(layer.label.length).toBeGreaterThan(0);
    }
  });
});

describe("getLayerStyle", () => {
  it("activeLayer 匹配时返回 is-active 类名", () => {
    const info = getLayerStyle("L1", "L1");
    expect(info.isActive).toBe(true);
    expect(info.className).toContain("is-active");
    expect(info.className).toContain("bp-arch-layer");
  });

  it("activeLayer 不匹配时返回非活跃类名", () => {
    const info = getLayerStyle("L1", "L2");
    expect(info.isActive).toBe(false);
    expect(info.className).toBe("bp-arch-layer");
    expect(info.className).not.toContain("is-active");
  });

  it("activeLayer 为 null 时所有层均非活跃", () => {
    const layers: BpArchLayerId[] = ["L1", "L2", "L3", "AIP"];
    for (const id of layers) {
      const info = getLayerStyle(id, null);
      expect(info.isActive).toBe(false);
    }
  });

  it("activeLayer 为 undefined 时所有层均非活跃", () => {
    const info = getLayerStyle("L3", undefined);
    expect(info.isActive).toBe(false);
  });

  it("AIP 层也能正确高亮", () => {
    const info = getLayerStyle("AIP", "AIP");
    expect(info.isActive).toBe(true);
  });

  it("返回的 id 与入参一致", () => {
    const info = getLayerStyle("L2", "L1");
    expect(info.id).toBe("L2");
  });
});
