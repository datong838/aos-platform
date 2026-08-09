import { describe, expect, it } from "vitest";

import { buildGraphNodes, resolveObjectSelectionId } from "./workshop";

describe("O1-UX0 · Object Explorer graph identity", () => {
  it("preserves neighbor type and collision-safe key", () => {
    const graph = buildGraphNodes(
      { id: "1", title: "订单 1" },
      [
        { id: "12", type: "Payment", rel: "Order.hasPayment" },
        { id: "12", type: "OrderLine", rel: "Order.lines" },
      ],
      "Order",
    );

    expect(graph.center).toMatchObject({ key: "Order:1", type: "Order", id: "1" });
    expect(graph.outer).toEqual([
      expect.objectContaining({ key: "Payment:12:Order.hasPayment", type: "Payment", id: "12" }),
      expect.objectContaining({ key: "OrderLine:12:Order.lines", type: "OrderLine", id: "12" }),
    ]);
  });

  it("resolves an authoritative neighbor reference to the target list identity", () => {
    expect(
      resolveObjectSelectionId(
        [{ id: "1" }, { id: "2", _sourceIdentity: { externalId: "niushop:1:2" } }],
        "niushop:1:2",
      ),
    ).toBe("2");
    expect(resolveObjectSelectionId([{ id: "1" }, { id: "2" }], "niushop:1:2")).toBe("2");
  });
});
