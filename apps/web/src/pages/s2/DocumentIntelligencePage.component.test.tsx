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
    vi.mocked(apiGet).mockImplementation(async (path: string) => {
      if (path.includes("/documents/stats")) return { total: 0, processing: 0, average_confidence: null, template_count: 3 };
      if (path.includes("/ontology/object-types")) return { items: [{ id: "Invoice", display_name: "发票" }] };
      return { items: [], total: 0 };
    });
    vi.mocked(apiPost).mockReset();
    vi.mocked(apiPut).mockReset();
    vi.mocked(apiDelete).mockReset();
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
    expect(init?.body).toBe(file);
    expect(host.textContent).toContain("invoice.pdf");
    expect(host.textContent).toContain("服务端已接收 1 个文件的真实字节");
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
    const select = host.querySelector<HTMLSelectElement>("[data-testid='ontology-type-select']")!;
    select.value = "Invoice";
    await act(async () => select.dispatchEvent(new Event("change", { bubbles: true })));
    const writeButton = host.querySelector<HTMLButtonElement>("[data-testid='ontology-write-btn']")!;
    await act(async () => writeButton.click());
    await flush();
    expect(apiPost).toHaveBeenCalledWith("/api/datasource/documents/doc-1/ontology-write", { object_type_id: "Invoice" });
    expect(host.textContent).toContain("Object obj-1");

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
});
