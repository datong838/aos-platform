import { describe, expect, it, beforeEach } from "vitest";
import {
  parseAosDeepLink,
  queuePendingDeepLink,
  takePendingDeepLink,
  PENDING_KEY,
} from "./deepLink";

describe("TWC.5 deep link", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("accepts whitelisted open paths", () => {
    const r = parseAosDeepLink("aos://open/workshop/inbox");
    expect(r.kind).toBe("open");
    expect(r.path).toBe("/workshop/inbox");
  });

  it("accepts open with query", () => {
    const r = parseAosDeepLink("aos://open/ontology?id=WorkOrder");
    expect(r.kind).toBe("open");
    expect(r.path).toBe("/ontology");
    expect(r.search).toContain("id=WorkOrder");
  });

  it("parses auth callback", () => {
    const r = parseAosDeepLink("aos://auth/callback?code=x");
    expect(r.kind).toBe("auth_callback");
  });

  it("rejects unknown path", () => {
    const r = parseAosDeepLink("aos://open/not-a-real-route-xyz");
    expect(r.kind).toBe("rejected");
    expect(r.reason).toBe("path_not_whitelisted");
  });

  it("rejects non-aos scheme", () => {
    expect(parseAosDeepLink("https://evil.example/x").kind).toBe("rejected");
  });

  it("queues pending until take", () => {
    queuePendingDeepLink("aos://open/");
    expect(sessionStorage.getItem(PENDING_KEY)).toBeTruthy();
    expect(takePendingDeepLink()).toBe("aos://open/");
    expect(takePendingDeepLink()).toBeNull();
  });
});
