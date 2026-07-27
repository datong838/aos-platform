import { describe, expect, it } from "vitest";
import { MOCK_FERRY_BUNDLES } from "./FerryPage";

describe("FerryPage · MOCK_FERRY_BUNDLES 数据", () => {
  it("有至少 2 个 Bundle", () => {
    expect(MOCK_FERRY_BUNDLES.length).toBeGreaterThanOrEqual(2);
  });

  it("每个 Bundle 有 id/name/size", () => {
    for (const b of MOCK_FERRY_BUNDLES) {
      expect(b.id.length).toBeGreaterThan(0);
      expect(b.name.length).toBeGreaterThan(0);
      expect(b.size.length).toBeGreaterThan(0);
    }
  });

  it("至少有一个已签名 Bundle", () => {
    const signed = MOCK_FERRY_BUNDLES.filter((b) => b.signed);
    expect(signed.length).toBeGreaterThan(0);
  });

  it("每个 Bundle 有 contents 组件清单", () => {
    for (const b of MOCK_FERRY_BUNDLES) {
      expect(b.contents.length).toBeGreaterThan(0);
      for (const c of b.contents) {
        expect(c.component.length).toBeGreaterThan(0);
        expect(c.version.length).toBeGreaterThan(0);
      }
    }
  });

  it("每个 Bundle 有 targetSpokes", () => {
    for (const b of MOCK_FERRY_BUNDLES) {
      expect(b.targetSpokes.length).toBeGreaterThan(0);
    }
  });

  it("签名信息包含算法和签名者", () => {
    const signed = MOCK_FERRY_BUNDLES.find((b) => b.signed);
    expect(signed).toBeTruthy();
    expect(signed!.signature.algorithm.length).toBeGreaterThan(0);
    expect(signed!.signature.signedBy.length).toBeGreaterThan(0);
  });
});
