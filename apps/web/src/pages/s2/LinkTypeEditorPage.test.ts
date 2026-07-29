import { describe, expect, it } from "vitest";
import {
  emptyForm,
  validateLinkType,
  isMdoRequired,
  cardinalityLabel,
  cardinalityIcon,
  joinMethodLabel,
  joinMethodDescription,
  checkScaleWarning,
  estimateStorage,
  swapDirection,
  normalizeLinkType,
  truncateLabel,
  buildLinkRelationLayout,
  CARDINALITIES,
  JOIN_METHODS,
  LINK_NAV_SECTIONS,
} from "./LinkTypeEditorPage";

describe("LinkTypeEditorPage · emptyForm", () => {
  it("creates a form with default values", () => {
    const f = emptyForm();
    expect(f.id).toBe("");
    expect(f.name).toBe("");
    expect(f.cardinality).toBe("MANY_TO_MANY");
    expect(f.joinMethod).toBe("foreign_key");
    expect(f.mdoApproved).toBe(false);
  });

  it("accepts id parameter", () => {
    const f = emptyForm("lt-test");
    expect(f.id).toBe("lt-test");
  });
});

describe("LinkTypeEditorPage · validateLinkType", () => {
  it("passes for valid form", () => {
    const f = {
      ...emptyForm(),
      id: "lt-related",
      name: "Related",
      srcType: "WorkOrder",
      dstType: "Customer",
    };
    expect(validateLinkType(f)).toHaveLength(0);
  });

  it("catches empty id", () => {
    const f = { ...emptyForm(), name: "Test" };
    expect(validateLinkType(f)).toContain("id 不能为空");
  });

  it("catches empty name", () => {
    const f = { ...emptyForm(), id: "lt-test" };
    expect(validateLinkType(f)).toContain("name 不能为空");
  });

  it("catches empty srcType", () => {
    const f = { ...emptyForm(), id: "lt-test", name: "T", srcType: "" };
    expect(validateLinkType(f)).toContain("srcType 不能为空");
  });

  it("catches empty dstType", () => {
    const f = { ...emptyForm(), id: "lt-test", name: "T", dstType: "" };
    expect(validateLinkType(f)).toContain("dstType 不能为空");
  });

  it("catches same src/dst without symmetric", () => {
    const f = {
      ...emptyForm(),
      id: "lt-self",
      name: "Self",
      srcType: "WorkOrder",
      dstType: "WorkOrder",
      symmetric: false,
    };
    const errors = validateLinkType(f);
    expect(errors.some((e) => e.includes("symmetric"))).toBe(true);
  });

  it("allows same src/dst with symmetric", () => {
    const f = {
      ...emptyForm(),
      id: "lt-self",
      name: "Self",
      srcType: "WorkOrder",
      dstType: "WorkOrder",
      symmetric: true,
    };
    expect(validateLinkType(f)).not.toContain(
      "srcType 和 dstType 相同时需要勾选 symmetric",
    );
  });

  it("catches negative expectedEdges", () => {
    const f = {
      ...emptyForm(),
      id: "lt-test",
      name: "T",
      expectedEdges: -1,
    };
    expect(validateLinkType(f)).toContain("expectedEdges 不能为负数");
  });
});

describe("LinkTypeEditorPage · isMdoRequired", () => {
  it("returns true for > 100k edges", () => {
    expect(isMdoRequired(100_001)).toBe(true);
  });

  it("returns false for exactly 100k", () => {
    expect(isMdoRequired(100_000)).toBe(false);
  });

  it("returns false for < 100k", () => {
    expect(isMdoRequired(50_000)).toBe(false);
  });
});

describe("LinkTypeEditorPage · cardinality helpers", () => {
  it("cardinalityLabel returns short labels", () => {
    expect(cardinalityLabel("ONE_TO_ONE")).toBe("1:1");
    expect(cardinalityLabel("MANY_TO_MANY")).toBe("N:N");
  });

  it("cardinalityIcon returns arrow symbols", () => {
    expect(cardinalityIcon("ONE_TO_ONE")).toBeTruthy();
    expect(cardinalityIcon("MANY_TO_MANY")).toBeTruthy();
  });
});

describe("LinkTypeEditorPage · joinMethod helpers", () => {
  it("joinMethodLabel returns Chinese labels", () => {
    expect(joinMethodLabel("foreign_key")).toBe("外键关联");
    expect(joinMethodLabel("junction_table")).toBe("交叉表");
  });

  it("joinMethodDescription returns descriptions", () => {
    expect(joinMethodDescription("foreign_key")).toBeTruthy();
    expect(joinMethodDescription("computed")).toBeTruthy();
  });
});

describe("LinkTypeEditorPage · checkScaleWarning", () => {
  it("warns when > 100k and no MDO", () => {
    const f = { ...emptyForm(), expectedEdges: 200_000, mdoApproved: false };
    const w = checkScaleWarning(f);
    expect(w.warn).toBe(true);
    expect(w.message).toContain("LINK_SCALE_BLOCKED");
  });

  it("no warning when > 100k and MDO approved", () => {
    const f = { ...emptyForm(), expectedEdges: 200_000, mdoApproved: true };
    expect(checkScaleWarning(f).warn).toBe(false);
  });

  it("no warning for small edges", () => {
    const f = { ...emptyForm(), expectedEdges: 1000, mdoApproved: false };
    expect(checkScaleWarning(f).warn).toBe(false);
  });
});

describe("LinkTypeEditorPage · estimateStorage", () => {
  it("returns 0 MB for 0 edges", () => {
    expect(estimateStorage({ ...emptyForm(), expectedEdges: 0 })).toBe("0 MB");
  });

  it("returns bytes for small counts", () => {
    const result = estimateStorage({ ...emptyForm(), expectedEdges: 10 });
    expect(result).toContain("B");
  });

  it("returns KB for medium counts", () => {
    const result = estimateStorage({ ...emptyForm(), expectedEdges: 1000 });
    expect(result).toContain("KB");
  });

  it("returns MB for large counts", () => {
    const result = estimateStorage({ ...emptyForm(), expectedEdges: 100_000 });
    expect(result).toContain("MB");
  });
});

describe("LinkTypeEditorPage · swapDirection", () => {
  it("swaps srcType and dstType", () => {
    const f = { ...emptyForm(), srcType: "A", dstType: "B" };
    const swapped = swapDirection(f);
    expect(swapped.srcType).toBe("B");
    expect(swapped.dstType).toBe("A");
  });

  it("preserves other fields", () => {
    const f = { ...emptyForm(), id: "lt-x", name: "Test", srcType: "A", dstType: "B" };
    const swapped = swapDirection(f);
    expect(swapped.id).toBe("lt-x");
    expect(swapped.name).toBe("Test");
  });
});

describe("LinkTypeEditorPage · normalizeLinkType (C8a)", () => {
  it("fills joinMethod/symmetric defaults when API omits them", () => {
    const n = normalizeLinkType({
      id: "lt-aircraft-airline",
      name: "Aircraft-Airline",
      srcType: "Aircraft",
      dstType: "Airline",
      rel: "operated_by",
      cardinality: "MANY_TO_ONE",
      expectedEdges: 10,
      mdoApproved: false,
      published: true,
      description: "demo",
    });
    expect(n.joinMethod).toBe("foreign_key");
    expect(n.symmetric).toBe(false);
    expect(n.constraints).toEqual([]);
    expect(n.cardinality).toBe("MANY_TO_ONE");
  });

  it("keeps provided joinMethod", () => {
    const n = normalizeLinkType({
      ...emptyForm("lt-x"),
      name: "X",
      joinMethod: "junction_table",
      symmetric: true,
    });
    expect(n.joinMethod).toBe("junction_table");
    expect(n.symmetric).toBe(true);
  });
});

describe("LinkTypeEditorPage · buildLinkRelationLayout (C8a)", () => {
  it("builds src/dst nodes and cardinality edge label", () => {
    const layout = buildLinkRelationLayout({
      srcType: "Aircraft",
      dstType: "Airline",
      rel: "operated_by",
      cardinality: "MANY_TO_ONE",
      joinMethod: "foreign_key",
      symmetric: false,
    });
    expect(layout.src.label).toBe("Aircraft");
    expect(layout.dst.label).toBe("Airline");
    expect(layout.edge.cardLabel).toBe("N:1");
    expect(layout.edge.relLabel).toContain("operated");
    expect(layout.summary.card).toBe("N:1");
    expect(layout.summary.join).toBe("外键关联");
    expect(layout.edge.x2).toBeGreaterThan(layout.edge.x1);
  });

  it("truncates long labels", () => {
    expect(truncateLabel("ABCDEFGHIJKLMNOPQRSTUVWXYZ", 10).endsWith("…")).toBe(true);
    expect(truncateLabel("")).toBe("—");
  });

  it("handles empty types with placeholder", () => {
    const layout = buildLinkRelationLayout({
      srcType: "",
      dstType: "",
      rel: "",
      cardinality: "ONE_TO_ONE",
      joinMethod: "computed",
      symmetric: true,
    });
    expect(layout.src.label).toBe("—");
    expect(layout.dst.label).toBe("—");
    expect(layout.summary.symmetric).toBe(true);
  });
});

describe("LinkTypeEditorPage · constants", () => {
  it("CARDINALITIES has 4 values", () => {
    expect(CARDINALITIES).toHaveLength(4);
  });

  it("JOIN_METHODS has 4 values", () => {
    expect(JOIN_METHODS).toHaveLength(4);
  });

  it("LINK_NAV_SECTIONS has 4 sections", () => {
    expect(LINK_NAV_SECTIONS).toHaveLength(4);
  });

  it("all JOIN_METHODS have descriptions", () => {
    for (const j of JOIN_METHODS) {
      expect(j.description).toBeTruthy();
    }
  });
});
