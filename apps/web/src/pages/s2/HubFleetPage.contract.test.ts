import { describe, expect, it } from "vitest";
import { spokeHealthLabel, type Spoke } from "./HubFleetPage";

describe("HubFleetPage · current authority semantics", () => {
  it("does not infer online when heartbeat is not authoritative", () => {
    const spoke = { id: "node-1", name: "运行节点", status: "online", heartbeatOk: false } satisfies Spoke;
    expect(spokeHealthLabel(spoke)).toBe("未通过探活");
  });

  it("labels exact online heartbeat", () => {
    const spoke = { id: "node-1", name: "运行节点", status: "online", heartbeatOk: true } satisfies Spoke;
    expect(spokeHealthLabel(spoke)).toBe("在线");
  });
});
