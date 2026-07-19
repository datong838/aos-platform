import { beforeEach, describe, expect, it } from "vitest";
import {
  gateInstall,
  signManifest,
  verifyUpdateSignature,
  type UpdateManifest,
} from "./verify";
import { checkDesktopUpdate, injectUpdateManifest } from "./check";

describe("TWC.9 signed update", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("rejects missing or bad signature (拒装)", async () => {
    const bad: UpdateManifest = {
      version: "0.2.1",
      url: "https://example/a.dmg",
      sha256: "abc",
      signature: "aos-v1:deadbeef",
    };
    const v = await verifyUpdateSignature(bad);
    expect(v.ok).toBe(false);
    const g = await gateInstall(bad);
    expect(g.allowed).toBe(false);
  });

  it("accepts valid aos-v1 signature", async () => {
    const base = {
      version: "0.2.1",
      url: "https://example/a.dmg",
      sha256: "abc123",
    };
    const m: UpdateManifest = {
      ...base,
      notes: "fix",
      signature: await signManifest(base),
    };
    expect((await verifyUpdateSignature(m)).ok).toBe(true);
    expect((await gateInstall(m)).allowed).toBe(true);
  });

  it("check returns available only when signed and newer", async () => {
    const base = {
      version: "0.9.0",
      url: "https://example/x.dmg",
      sha256: "ff",
    };
    injectUpdateManifest({
      ...base,
      signature: await signManifest(base),
    });
    const r = await checkDesktopUpdate("0.1.0");
    expect(r.status).toBe("available");
    if (r.status === "available") {
      expect(r.manifest.version).toBe("0.9.0");
    }
  });

  it("check invalid when tampered", async () => {
    injectUpdateManifest({
      version: "0.9.0",
      url: "https://example/x.dmg",
      sha256: "ff",
      signature: "aos-v1:0000",
    });
    const r = await checkDesktopUpdate("0.1.0");
    expect(r.status).toBe("invalid");
  });
});
