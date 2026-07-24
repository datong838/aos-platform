import { describe, expect, it } from "vitest";
import {
  TOKENS,
  aggregateHealth,
  appendAssistantFromAsk,
  appendUserMessage,
  buildAskBody,
  citationsForPanel,
} from "./buddy";

describe("aggregateHealth", () => {
  it("U-UI-04 all up → green", () => {
    expect(
      aggregateHealth({ dify: "up", openocta: "up", adapter: "up" })
    ).toBe("green");
  });
  it("U-UI-04 dify down → red", () => {
    expect(
      aggregateHealth({ dify: "down", openocta: "up", adapter: "up" })
    ).toBe("red");
  });
  it("openocta unknown + dify/adapter up → green (v0.1)", () => {
    expect(
      aggregateHealth({ dify: "up", openocta: "unknown", adapter: "up" })
    ).toBe("green");
  });
  it("unknown only → yellow", () => {
    expect(
      aggregateHealth({
        dify: "unknown",
        openocta: "unknown",
        adapter: "unknown",
      })
    ).toBe("yellow");
  });
});

describe("messages", () => {
  it("appends user", () => {
    const next = appendUserMessage([], "你好", "1");
    expect(next).toHaveLength(1);
    expect(next[0].role).toBe("user");
  });

  it("U-UI-01 ok response writes answer + citations", () => {
    let msgs = appendUserMessage([], "q", "u1");
    msgs = appendAssistantFromAsk(
      msgs,
      {
        trace_id: "T",
        answer: "答",
        citations: [{ doc_name: "a.pdf", snippet: "s" }],
        status: "ok",
      },
      "a1"
    );
    expect(msgs[1].content).toBe("答");
    expect(citationsForPanel(msgs)[0].doc_name).toBe("a.pdf");
  });

  it("U-UI-02 no_hit empty 右栏", () => {
    const msgs = appendAssistantFromAsk(
      [],
      { trace_id: "T", answer: "", citations: [], status: "no_hit" },
      "a"
    );
    expect(msgs[0].content).toContain("未命中");
    expect(citationsForPanel(msgs)).toEqual([]);
  });

  it("U-UI-03 error 温和失败", () => {
    const msgs = appendAssistantFromAsk(
      [],
      { trace_id: "T", answer: "", citations: [], status: "error" },
      "a"
    );
    expect(msgs[0].content).toContain("Docker");
  });
});

describe("buildAskBody", () => {
  it("U-UI-05 object_id in meta", () => {
    const b = buildAskBody("q", "OBJ-1001");
    expect(b.meta?.object_id).toBe("OBJ-1001");
  });
  it("no object omits meta", () => {
    const b = buildAskBody("q");
    expect(b.meta).toBeUndefined();
  });
});

describe("tokens", () => {
  it("matches foundry dark shell accent cyan", () => {
    expect(TOKENS.accent).toContain("34");
    expect(TOKENS.bgApp).toContain("2, 6, 23");
  });
});
