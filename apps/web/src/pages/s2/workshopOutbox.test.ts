import { describe, expect, it } from "vitest";
import { formatOutboxRow } from "./workshop";

describe("218m workshop outbox UI helpers", () => {
  it("formats ok outbox row", () => {
    const f = formatOutboxRow({
      id: "ob-1",
      channel: "channel-webhook",
      ok: true,
      status: "retried",
    });
    expect(f.id).toBe("ob-1");
    expect(f.channel).toBe("channel-webhook");
    expect(f.result).toBe("ok");
    expect(f.status).toBe("retried");
  });

  it("formats fail / missing fields", () => {
    const f = formatOutboxRow({ ok: false, pluginId: "channel-email" });
    expect(f.channel).toBe("channel-email");
    expect(f.result).toBe("fail");
    expect(f.id).toBe("—");
  });
});
