import { act, createElement } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { buildImportPreviewRequest, EMPTY_IMPORT_FORM, type ImportForm } from "./GovernedImportPreview";
import { AgentImportPage } from "./AgentImportPage";

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
  sourceId: "approved/agent",
  sourceCommit: "abcdef1",
  licenseId: "MIT",
  signatureId: "signature/agent",
  sbomId: "sbom/agent",
  targetId: "ecommerce.agent.external",
  displayName: "外部智能体",
  sourcePath: "agent.py",
  sourceContent: "def run(value):\n    return value",
};

describe("AgentImportPage · governed preview", () => {
  it("renders the complete governed import workspace instead of a blank frame", async () => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);

    await act(async () => root?.render(createElement(MemoryRouter, null, createElement(AgentImportPage))));

    expect(host.textContent).toContain("智能体受控导入");
    expect(host.textContent).toContain("来源冻结 → 扫描与映射");
    expect(host.querySelector('[aria-label="来源资源 ID"]')).not.toBeNull();
    expect(host.querySelector('[aria-label="源码快照"]')).not.toBeNull();
    expect(host.querySelector('a[href="/aip/agent-registry"]')?.textContent).toContain("返回智能体目录");
  });

  it("initial state does not fabricate repository or scan evidence", () => {
    expect(EMPTY_IMPORT_FORM.sourceId).toBe("");
    expect(EMPTY_IMPORT_FORM.sourceCommit).toBe("");
    expect(EMPTY_IMPORT_FORM.sourceContent).toBe("");
  });

  it("builds a caller-supplied immutable snapshot without ImportJob fields", () => {
    const request = buildImportPreviewRequest("agent", valid);
    expect(request.kind).toBe("agent");
    expect(request.source.sourceCommit).toBe("abcdef1");
    expect(request.source.signatureRef.resourceId).toBe("signature/agent");
    expect(request.source.files).toEqual([{ path: "agent.py", content: valid.sourceContent }]);
    expect(request.mapping.toolMappings).toEqual({});
    expect("importJob" in request).toBe(false);
  });

  it("rejects missing source facts and plaintext secrets", () => {
    expect(() => buildImportPreviewRequest("agent", EMPTY_IMPORT_FORM)).toThrow("均为必填");
    expect(() => buildImportPreviewRequest("agent", { ...valid, secretRef: "plaintext" })).toThrow("禁止明文");
  });
});
