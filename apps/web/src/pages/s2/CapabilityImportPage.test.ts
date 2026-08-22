import { describe, expect, it } from "vitest";
import { buildImportPreviewRequest, EMPTY_IMPORT_FORM, type ImportForm } from "./GovernedImportPreview";

const valid: ImportForm = {
  ...EMPTY_IMPORT_FORM,
  sourceId: "approved/capability",
  sourceCommit: "1234abc",
  licenseId: "Apache-2.0",
  sbomId: "sbom/capability",
  targetId: "ecommerce.capability.external",
  displayName: "外部能力",
  sourcePath: "capability.py",
  sourceContent: "def invoke(value):\n    return value",
  inputSchema: '{"type":"object"}',
  outputSchema: '{"type":"object"}',
};

describe("CapabilityImportPage · governed preview", () => {
  it("requires user supplied input and output schema", () => {
    const request = buildImportPreviewRequest("capability", valid);
    expect(request.mapping.inputSchema).toEqual({ type: "object" });
    expect(request.mapping.outputSchema).toEqual({ type: "object" });
  });

  it("does not prefill fake endpoints, documents, credentials or test results", () => {
    expect(EMPTY_IMPORT_FORM.networkPolicyRef).toBe("");
    expect(EMPTY_IMPORT_FORM.secretRef).toBe("");
    expect(EMPTY_IMPORT_FORM.inputSchema).toBe("");
    expect(EMPTY_IMPORT_FORM.outputSchema).toBe("");
  });

  it("rejects malformed schema before any request", () => {
    expect(() => buildImportPreviewRequest("capability", { ...valid, inputSchema: "[]" })).toThrow("JSON 对象");
  });
});
