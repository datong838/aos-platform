import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { buildImportPreviewRequest, EMPTY_IMPORT_FORM, type ImportForm } from "./GovernedImportPreview";
import { CapabilityImportPage } from "./CapabilityImportPage";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement | null = null;
let root: ReturnType<typeof createRoot> | null = null;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  host?.remove();
  root = null;
  host = null;
});

const valid: ImportForm = {
  ...EMPTY_IMPORT_FORM,
  sourceId: "approved/capability",
  sourceCommit: "1234abc",
  licenseId: "Apache-2.0",
  signatureId: "signature/capability",
  sbomId: "sbom/capability",
  targetId: "ecommerce.capability.external",
  displayName: "外部能力",
  sourcePath: "capability.py",
  sourceContent: "def invoke(value):\n    return value",
  inputSchema: '{"type":"object"}',
  outputSchema: '{"type":"object"}',
};

describe("CapabilityImportPage · governed preview", () => {
  it("renders the complete governed import workspace instead of a blank frame", async () => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);

    await act(async () => root?.render(createElement(MemoryRouter, null, createElement(CapabilityImportPage))));

    expect(host.textContent).toContain("能力受控导入");
    expect(host.textContent).toContain("来源冻结 → 扫描与映射");
    expect(host.querySelector('[aria-label="输入 Schema JSON"]')).not.toBeNull();
    expect(host.querySelector('[aria-label="输出 Schema JSON"]')).not.toBeNull();
    expect(host.querySelector('a[href="/aip/capabilities"]')?.textContent).toContain("返回能力目录");
  });

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
