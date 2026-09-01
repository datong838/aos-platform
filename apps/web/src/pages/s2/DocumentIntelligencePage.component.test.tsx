import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiDelete, apiGet, apiPost, apiPut } from "../../api/client";
import { DocumentIntelligencePage } from "./DocumentIntelligencePage";

vi.mock("../../api/client", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiDelete: vi.fn(),
}));

const rawDocument = (overrides: Record<string, unknown> = {}) => ({
  id: "doc-1",
  name: "invoice.pdf",
  file_type: "pdf",
  status: "review",
  size_bytes: 12,
  content_sha256: "abc",
  ocr_text: "发票号码: INV-1",
  created_at: 1_700_000_000,
  extracted_fields: {
    "xf-1": { id: "xf-1", name: "发票号码", value: "INV-1", type: "文本", confidence: 0.9, source: "P1 L1" },
  },
  history: [],
  source_label: "栖月汇合同归档",
  document_kind: "supplier_contract",
  sensitivity: "restricted",
  retention_policy: "180_days",
  template_revision: "v3",
  processing_progress: 100,
  current_page: 2,
  total_pages: 2,
  extraction_confidence: 0.9,
  usage_units: 128,
  run_evidence_ref: "document-run:doc-1:v3",
  lineage_ref: "document-lineage:doc-1:extract:v3",
  receipt_ref: "document-extract:doc-1:v3",
  receipt_refs: ["document-upload:doc-1:abc", "document-extract:doc-1:v3"],
  org_id: "org-org",
  project_id: "dev-project",
  review_status: "pending",
  ...overrides,
});

async function flush() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("DocumentIntelligencePage · real interaction", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    (globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    window.history.replaceState({}, "", "/aip/doc-intelligence");
    vi.mocked(apiGet).mockImplementation(async (path: string) => {
      if (path.includes("/documents/stats")) return { total: 0, processing: 0, average_confidence: null, template_count: 3 };
      if (path.includes("/ontology/object-types")) return { items: [{ id: "Invoice", display_name: "发票" }] };
      return { items: [], total: 0 };
    });
    vi.mocked(apiPost).mockReset();
    vi.mocked(apiPut).mockReset();
    vi.mocked(apiDelete).mockReset();
  });

  it("从下游返回时按精确 documentId 定位原文档", async () => {
    window.history.replaceState({}, "", "/aip/doc-intelligence?documentId=doc-2");
    vi.mocked(apiGet).mockImplementation(async (path: string) => {
      if (path.includes("/documents/stats")) return { total: 2, processing: 0, average_confidence: 0.9, template_count: 3 };
      if (path.includes("/ontology/object-types")) return { items: [] };
      if (path.includes("/extraction-templates")) return { items: [] };
      return { items: [rawDocument(), rawDocument({ id: "doc-2", name: "contract.pdf", source_label: "栖月汇供应商合同" })], total: 2 };
    });
    await act(async () => root.render(<DocumentIntelligencePage />));
    await flush();
    expect(host.querySelector("[data-testid='document-governance-panel']")?.textContent).toContain("栖月汇供应商合同");
    expect(host.querySelector("[data-testid='document-governance-panel']")?.textContent).not.toContain("栖月汇合同归档");
  });

  afterEach(() => {
    act(() => root.unmount());
    host.remove();
    vi.restoreAllMocks();
  });

  it("sends the selected File as request bytes and only adds the API response", async () => {
    const fetchMock = vi.fn(async (_url: string, init?: RequestInit) => ({
      ok: true,
      status: 200,
      json: async () => rawDocument({ status: "uploaded", extracted_fields: {} }),
      requestBody: init?.body,
    })) as unknown as typeof fetch;
    vi.stubGlobal("fetch", fetchMock);

    await act(async () => root.render(<DocumentIntelligencePage />));
    await flush();
    const file = new File(["%PDF-1.4 真实文件字节"], "invoice.pdf", { type: "application/pdf" });
    const input = host.querySelector<HTMLInputElement>("#doc-file-input")!;
    Object.defineProperty(input, "files", { configurable: true, value: [file] });

    await act(async () => input.dispatchEvent(new Event("change", { bubbles: true })));
    await flush();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = vi.mocked(fetchMock).mock.calls[0];
    const [requestUrl] = vi.mocked(fetchMock).mock.calls[0];
    expect(init?.body).toBe(file);
    expect(String(requestUrl)).toContain("source_label=%E4%BA%BA%E5%B7%A5%E4%B8%9A%E5%8A%A1%E6%96%87%E6%A1%A3%E5%AF%BC%E5%85%A5");
    expect(String(requestUrl)).toContain("sensitivity=internal");
    expect(host.textContent).toContain("invoice.pdf");
    expect(host.textContent).toContain("服务端已接收 1 个文件的真实字节");
    expect(host.textContent).toContain("来源、治理与运行证据");
  });

  it("keeps the list unchanged when upload fails", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: false,
      status: 409,
      json: async () => ({ detail: "storage unavailable" }),
    })));
    await act(async () => root.render(<DocumentIntelligencePage />));
    await flush();
    const input = host.querySelector<HTMLInputElement>("#doc-file-input")!;
    Object.defineProperty(input, "files", { configurable: true, value: [new File(["%PDF-x"], "invoice.pdf")] });

    await act(async () => input.dispatchEvent(new Event("change", { bubbles: true })));
    await flush();

    expect(host.querySelector("[data-testid^='doc-item-']")).toBeNull();
    expect(host.textContent).toContain("失败 1 个");
    expect(host.textContent).toContain("失败文件未加入列表");
  });

  it("shows actionable feedback and does not call the pipeline when no document exists", async () => {
    await act(async () => root.render(<DocumentIntelligencePage />));
    await flush();

    const trial = host.querySelector<HTMLButtonElement>("[data-testid='pipeline-trial-btn']")!;
    await act(async () => trial.click());
    await flush();

    expect(host.textContent).toContain("请先上传并选择文档后再试运行");
    expect(apiPost).not.toHaveBeenCalled();
  });

  it("creates, versions and rolls back a tenant-governed extraction template", async () => {
    const template = {
      id: "tpl-1",
      name: "供应商合同字段模板",
      description: "提取合同主体、合同金额、有效期和续签日",
      fields: [{ name: "party_a", label: "甲方" }, { name: "contract_amount", label: "合同金额" }],
      doc_type: "supplier_contract",
      revision: 1,
      validation_rules: [{ field: "合同金额", rule: "required" }],
      model_route: "deterministic_document_parser",
      estimated_cost_units: 2,
      approval_gate: "manual_review",
      active: true,
      change_note: "首次创建",
    };
    vi.mocked(apiPost).mockImplementation(async (path: string) => {
      if (path === "/api/datasource/extraction-templates") return template;
      if (path.endsWith("/rollback")) return { ...template, revision: 3, change_note: "回滚到 v1" };
      throw new Error(`unexpected ${path}`);
    });
    vi.mocked(apiPut).mockResolvedValue({ ...template, revision: 2, change_note: "人工保存新版本" });
    vi.mocked(apiGet).mockImplementation(async (path: string) => {
      if (path.includes("/documents/stats")) return { total: 0, processing: 0, average_confidence: null, template_count: 1 };
      if (path.includes("/ontology/object-types")) return { items: [] };
      if (path.endsWith("/versions")) return { items: [template, { ...template, revision: 2, fields: [...template.fields, { name: "renewal_date", label: "续签日" }] }] };
      return { items: [], total: 0 };
    });

    await act(async () => root.render(<DocumentIntelligencePage />));
    await flush();
    const create = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "新建合同模板") as HTMLButtonElement;
    await act(async () => create.click());
    await flush();
    expect(apiPost).toHaveBeenCalledWith("/api/datasource/extraction-templates", expect.objectContaining({ approval_gate: "manual_review" }));
    expect(host.querySelector("[data-testid='template-governance-panel']")?.textContent).toContain("中文字段：甲方、合同金额");

    const revise = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "保存新版本") as HTMLButtonElement;
    await act(async () => revise.click());
    await flush();
    expect(apiPut).toHaveBeenCalledWith("/api/datasource/extraction-templates/tpl-1", expect.objectContaining({ expected_revision: 1 }));
    expect(host.textContent).toContain("v2");

    const compare = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "比较版本") as HTMLButtonElement;
    await act(async () => compare.click());
    await flush();
    expect(apiGet).toHaveBeenCalledWith("/api/datasource/extraction-templates/tpl-1/versions");
    expect(host.textContent).toContain("新增字段 续签日");

    const rollback = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "回滚到 v1") as HTMLButtonElement;
    await act(async () => rollback.click());
    await flush();
    expect(apiPost).toHaveBeenCalledWith("/api/datasource/extraction-templates/tpl-1/rollback", { expected_revision: 2, target_revision: 1 });
    expect(host.textContent).toContain("回滚到 v1");
  });

  it("uses API responses for ontology write, reprocess and delete", async () => {
    vi.mocked(apiGet).mockImplementation(async (path: string) => {
      if (path.includes("/documents/stats")) return { total: 1, processing: 0, average_confidence: 0.9, template_count: 3 };
      if (path.includes("/ontology/object-types")) return { items: [{ id: "Invoice", display_name: "发票" }] };
      return { items: [rawDocument()], total: 1 };
    });
    vi.mocked(apiPost).mockImplementation(async (path: string) => {
      if (path.endsWith("/ontology-write")) return { document: rawDocument({ ontology_object_id: "obj-1" }), object: { id: "obj-1" } };
      if (path.endsWith("/reprocess")) return rawDocument({ ocr_text: "重新解析" });
      throw new Error(`unexpected ${path}`);
    });
    vi.mocked(apiDelete).mockResolvedValue({ deleted: true });

    await act(async () => root.render(<DocumentIntelligencePage />));
    await flush();
    expect(host.querySelector("[data-testid='document-governance-panel']")?.textContent).toContain("栖月汇合同归档");
    expect(host.querySelector("[data-testid='document-governance-panel']")?.textContent).toContain("已取得");
    expect(host.querySelector("[data-testid='document-task-handoff']")?.getAttribute("href")).toContain("documentId=doc-1");
    const select = host.querySelector<HTMLSelectElement>("[data-testid='ontology-type-select']")!;
    select.value = "Invoice";
    await act(async () => select.dispatchEvent(new Event("change", { bubbles: true })));
    const writeButton = host.querySelector<HTMLButtonElement>("[data-testid='ontology-write-btn']")!;
    await act(async () => writeButton.click());
    await flush();
    expect(apiPost).toHaveBeenCalledWith("/api/datasource/documents/doc-1/ontology-write", { object_type_id: "Invoice" });
    expect(host.textContent).toContain("已生成业务对象");

    const checkbox = host.querySelector<HTMLInputElement>("[data-testid='doc-item-doc-1'] input[type='checkbox']")!;
    await act(async () => checkbox.click());
    const reprocess = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "重新处理") as HTMLButtonElement;
    await act(async () => reprocess.click());
    await flush();
    expect(apiPost).toHaveBeenCalledWith("/api/datasource/documents/doc-1/reprocess", { template_id: "finance_report" });

    const deleteButton = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "删除") as HTMLButtonElement;
    await act(async () => deleteButton.click());
    await flush();
    expect(apiDelete).toHaveBeenCalledWith("/api/datasource/documents/doc-1");
    expect(host.querySelector("[data-testid='doc-item-doc-1']")).toBeNull();
  });

  it("keeps a document selected when delete response is not confirmed", async () => {
    vi.mocked(apiGet).mockImplementation(async (path: string) => {
      if (path.includes("/documents/stats")) return { total: 1, processing: 0, average_confidence: 0.9, template_count: 3 };
      if (path.includes("/ontology/object-types")) return { items: [] };
      return { items: [rawDocument()], total: 1 };
    });
    vi.mocked(apiDelete).mockResolvedValue({ deleted: false });
    await act(async () => root.render(<DocumentIntelligencePage />));
    await flush();
    const checkbox = host.querySelector<HTMLInputElement>("[data-testid='doc-item-doc-1'] input[type='checkbox']")!;
    await act(async () => checkbox.click());
    const deleteButton = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "删除") as HTMLButtonElement;

    await act(async () => deleteButton.click());
    await flush();

    expect(host.querySelector("[data-testid='doc-item-doc-1']")).not.toBeNull();
    expect(checkbox.checked).toBe(true);
    expect(host.textContent).toContain("删除成功 0 个，失败 1 个");
  });

  it("confirms deletion by rereading the list when the DELETE response is lost", async () => {
    let documentReads = 0;
    vi.mocked(apiGet).mockImplementation(async (path: string) => {
      if (path.includes("/documents/stats")) return { total: 0, processing: 0, average_confidence: null, template_count: 3 };
      if (path.includes("/ontology/object-types")) return { items: [] };
      documentReads += 1;
      return documentReads === 1 ? { items: [rawDocument()], total: 1 } : { items: [], total: 0 };
    });
    vi.mocked(apiDelete).mockRejectedValue(new Error("Load failed after server commit"));
    await act(async () => root.render(<DocumentIntelligencePage />));
    await flush();
    const checkbox = host.querySelector<HTMLInputElement>("[data-testid='doc-item-doc-1'] input[type='checkbox']")!;
    await act(async () => checkbox.click());
    const deleteButton = Array.from(host.querySelectorAll("button")).find((button) => button.textContent === "删除") as HTMLButtonElement;

    await act(async () => deleteButton.click());
    await flush();

    expect(host.querySelector("[data-testid='doc-item-doc-1']")).toBeNull();
    expect(host.textContent).toContain("删除成功 1 个，失败 0 个");
  });

  it("reports successful extraction separately when stats refresh fails", async () => {
    let statsCalls = 0;
    vi.mocked(apiGet).mockImplementation(async (path: string) => {
      if (path.includes("/documents/stats")) {
        statsCalls += 1;
        if (statsCalls > 1) throw new Error("stats unavailable");
        return { total: 1, processing: 0, average_confidence: 0.9, template_count: 3 };
      }
      if (path.includes("/ontology/object-types")) return { items: [] };
      return { items: [rawDocument()], total: 1 };
    });
    vi.mocked(apiPost).mockResolvedValue(rawDocument());
    await act(async () => root.render(<DocumentIntelligencePage />));
    await flush();
    const runButton = host.querySelector<HTMLButtonElement>("[data-testid='run-extract-btn']")!;

    await act(async () => runButton.click());
    await flush();

    expect(host.textContent).toContain("抽取完成 · 权威回包");
    expect(host.textContent).toContain("写入成功但统计刷新失败");
    expect(host.textContent).not.toContain("抽取失败，未生成演示结果");
  });

  it("fails closed when the service adds an unknown document field", async () => {
    vi.mocked(apiGet).mockImplementation(async (path: string) => {
      if (path.includes("/documents/stats")) return { total: 1, processing: 0, average_confidence: null, template_count: 3 };
      if (path.includes("/ontology/object-types")) return { items: [] };
      return { items: [rawDocument({ unexpected_contract_field: true })], total: 1 };
    });
    await act(async () => root.render(<DocumentIntelligencePage />));
    await flush();
    expect(host.querySelector("[data-testid^='doc-item-']")).toBeNull();
    expect(host.textContent).toContain("文档回包含未知字段");
  });
});
