import { describe, expect, it } from "vitest";
import { buildImportPreviewRequest, EMPTY_IMPORT_FORM, type ImportForm } from "./GovernedImportPreview";

const valid: ImportForm = {
  ...EMPTY_IMPORT_FORM,
  sourceId: "approved/agent",
  sourceCommit: "abcdef1",
  licenseId: "MIT",
  sbomId: "sbom/agent",
  targetId: "ecommerce.agent.external",
  displayName: "外部智能体",
  sourcePath: "agent.py",
  sourceContent: "def run(value):\n    return value",
};

describe("AgentImportPage · governed preview", () => {
  it("initial state does not fabricate repository or scan evidence", () => {
    expect(EMPTY_IMPORT_FORM.sourceId).toBe("");
    expect(EMPTY_IMPORT_FORM.sourceCommit).toBe("");
    expect(EMPTY_IMPORT_FORM.sourceContent).toBe("");
  });

  it("builds a caller-supplied immutable snapshot without ImportJob fields", () => {
    const request = buildImportPreviewRequest("agent", valid);
    expect(request.kind).toBe("agent");
    expect(request.source.sourceCommit).toBe("abcdef1");
    expect(request.source.files).toEqual([{ path: "agent.py", content: valid.sourceContent }]);
    expect(request.mapping.toolMappings).toEqual({});
    expect("importJob" in request).toBe(false);
  });

  it("rejects missing source facts and plaintext secrets", () => {
    expect(() => buildImportPreviewRequest("agent", EMPTY_IMPORT_FORM)).toThrow("均为必填");
    expect(() => buildImportPreviewRequest("agent", { ...valid, secretRef: "plaintext" })).toThrow("禁止明文");
  });
});
