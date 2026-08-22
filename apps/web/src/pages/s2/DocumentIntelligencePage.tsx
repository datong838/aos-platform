/**
 * 文档智能 · OCR + LLM 抽取
 *
 * Wave 3A：文件、抽取、修正、入库、删除、重处理全部以后端响应为准；失败不生成 MOCK。
 * W4-E1：pipeline-doc-intel 并入本页（不新建侧栏）；说明条 + 轻量管道试运行。
 */
import { useState, useMemo, useCallback, useEffect } from "react";
import { apiDelete, apiGet, apiPost, apiPut } from "../../api/client";
import { getApiBase } from "../../api/apiBase";
import { tenantAuthHeaders } from "../../api/tenant";
import { PageChrome } from "../../components/PageChrome";

/* =========================================================================
 *  类型定义
 * ========================================================================= */

/** 文档处理四态状态机（+ 失败/需修正两个分支态） */
export type DocState =
  | "uploaded"
  | "processing_ocr"
  | "extracting"
  | "review"
  | "failed"
  | "needs_correction";

/** 文件类型 */
export type FileType = "pdf" | "word" | "excel" | "image" | "ppt";

/** 提取模板类型 */
export type TemplateId = "invoice" | "contract" | "purchase_order" | "finance_report" | "custom";

/** 文档项 */
export type DocItem = {
  id: string;
  title: string;
  type: FileType;
  size: number; // 字节
  status: DocState;
  uploadedAt: string;
  ocrProgress?: number; // 0-100
  ocrText?: string;
  errorMessage?: string;
  history?: HistoryEntry[];
  extractedFields?: ExtractField[];
  ontologyObjectId?: string;
  contentSha256?: string;
};

/** 提取字段 */
export type ExtractField = {
  id: string;
  name: string;
  type: string;
  value: string;
  confidence: number; // 0-1
  source: string; // 来源位置（页码/坐标描述）
};

/** 历史记录条目 */
export type HistoryEntry = {
  state: DocState;
  timestamp: string;
  note: string;
};

/* =========================================================================
 *  常量
 * ========================================================================= */

/** 置信度阈值：低于此值自动进入 needs_correction */
export const CONFIDENCE_THRESHOLD = 0.7;

/** 允许的文件扩展名 */
export const ALLOWED_EXTENSIONS = ["pdf", "doc", "docx", "xls", "xlsx", "jpg", "jpeg", "png", "ppt", "pptx"];

/** 最大文件大小 50MB */
export const MAX_FILE_SIZE = 50 * 1024 * 1024;

/** 状态元数据 */
export const STATE_META: Record<DocState, { label: string; color: string; bg: string }> = {
  uploaded: { label: "已上传", color: "#3B82F6", bg: "#DBEAFE" },
  processing_ocr: { label: "OCR 识别中", color: "#F59E0B", bg: "#FEF3C7" },
  extracting: { label: "LLM 提取中", color: "#8B5CF6", bg: "#EDE9FE" },
  review: { label: "待审核", color: "#10B981", bg: "#D1FAE5" },
  failed: { label: "失败", color: "#EF4444", bg: "#FEE2E2" },
  needs_correction: { label: "需人工修正", color: "#F59E0B", bg: "#FEF3C7" },
};

/** 状态机流转顺序（主流程） */
export const STATE_FLOW: DocState[] = ["uploaded", "processing_ocr", "extracting", "review"];

/** 文件类型元数据 */
export const TYPE_META: Record<FileType, { color: string; label: string; bg: string }> = {
  pdf: { color: "#DC2626", label: "PDF", bg: "#FEE2E2" },
  word: { color: "#2563EB", label: "Word", bg: "#DBEAFE" },
  excel: { color: "#16A34A", label: "Excel", bg: "#DCFCE7" },
  image: { color: "#9333EA", label: "图片", bg: "#F3E8FF" },
  ppt: { color: "#EA580C", label: "PPT", bg: "#FFEDD5" },
};

/** 提取模板 */
export const TEMPLATES: { id: TemplateId; label: string; fields: string[] }[] = [
  { id: "invoice", label: "发票模板", fields: ["发票号码", "开票日期", "销方名称", "购方名称", "金额(含税)", "税率", "税额"] },
  { id: "contract", label: "合同模板", fields: ["合同编号", "签订日期", "甲方", "乙方", "合同金额", "有效期", "标的物"] },
  { id: "purchase_order", label: "采购单模板", fields: ["采购单号", "下单日期", "供应商", "物料编码", "数量", "单价", "总金额"] },
  { id: "finance_report", label: "财务报告模板", fields: ["报告期间", "公司名称", "总收入", "净利润", "总资产", "负债率", "审计意见"] },
  { id: "custom", label: "自定义模板", fields: ["字段1", "字段2", "字段3"] },
];

/* =========================================================================
 *  纯函数 —— 状态机逻辑（便于测试）
 * ========================================================================= */

/**
 * 计算下一个状态（主流程）。
 * uploaded → processing_ocr → extracting → review
 * failed / needs_correction 为终态（不会自动前进）。
 */
export function nextState(current: DocState): DocState {
  const idx = STATE_FLOW.indexOf(current);
  if (idx === -1 || idx === STATE_FLOW.length - 1) return current;
  return STATE_FLOW[idx + 1];
}

/**
 * 判断状态流转是否合法。
 */
export function canTransition(from: DocState, to: DocState): boolean {
  if (from === to) return true;
  // 主流程顺序流转
  const fromIdx = STATE_FLOW.indexOf(from);
  const toIdx = STATE_FLOW.indexOf(to);
  if (fromIdx !== -1 && toIdx !== -1) {
    return toIdx === fromIdx + 1;
  }
  // 任意非终态 → failed
  if (to === "failed" && from !== "failed" && from !== "review") return true;
  // extracting → needs_correction
  if (from === "extracting" && to === "needs_correction") return true;
  // needs_correction → extracting（修正后重试）
  if (from === "needs_correction" && to === "extracting") return true;
  // needs_correction → review（人工直接确认）
  if (from === "needs_correction" && to === "review") return true;
  // failed → uploaded（重试从头上传）
  if (from === "failed" && to === "uploaded") return true;
  return false;
}

/**
 * 判断给定状态是否为终态（不可再自动流转）。
 */
export function isTerminal(state: DocState): boolean {
  return state === "failed" || state === "review";
}

/**
 * 获取状态在流程中的步骤索引（0-3），非主流程态返回 -1 或映射。
 */
export function getStepIndex(state: DocState): number {
  const idx = STATE_FLOW.indexOf(state);
  if (idx !== -1) return idx;
  // needs_correction 视为 extracting 阶段
  if (state === "needs_correction") return 2;
  // failed 视为停留在之前的阶段（保守返回 0）
  return 0;
}

/**
 * 根据提取字段的最低置信度，决定是否需要人工修正。
 */
export function shouldEnterNeedsCorrection(fields: ExtractField[]): boolean {
  if (fields.length === 0) return false;
  const minConf = Math.min(...fields.map((f) => f.confidence));
  return minConf < CONFIDENCE_THRESHOLD;
}

/* =========================================================================
 *  纯函数 —— 文件验证
 * ========================================================================= */

/**
 * 根据文件名推断文件类型。
 */
export function inferFileType(filename: string): FileType {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  if (ext === "pdf") return "pdf";
  if (ext === "doc" || ext === "docx") return "word";
  if (ext === "xls" || ext === "xlsx") return "excel";
  if (ext === "jpg" || ext === "jpeg" || ext === "png" || ext === "gif" || ext === "bmp") return "image";
  if (ext === "ppt" || ext === "pptx") return "ppt";
  return "pdf"; // 默认
}

/**
 * 验证文件是否可上传（扩展名 + 大小）。
 * 返回 null 表示合法，否则返回错误消息。
 */
export function validateFile(filename: string, size: number): string | null {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  if (!ALLOWED_EXTENSIONS.includes(ext)) {
    return `不支持的文件类型: .${ext}`;
  }
  if (size > MAX_FILE_SIZE) {
    return `文件大小超过限制 (最大 ${Math.round(MAX_FILE_SIZE / 1024 / 1024)}MB)`;
  }
  return null;
}

/**
 * 格式化文件大小。
 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/* =========================================================================
 *  纯函数 —— 置信度
 * ========================================================================= */

export type ConfidenceLevel = "high" | "medium" | "low";

/**
 * 根据置信度返回等级。
 * 高(>0.9)=green、中(0.7-0.9)=orange、低(<0.7)=red
 */
export function getConfidenceLevel(conf: number): ConfidenceLevel {
  if (conf > 0.9) return "high";
  if (conf >= 0.7) return "medium";
  return "low";
}

export function getConfidenceColor(conf: number): string {
  const level = getConfidenceLevel(conf);
  if (level === "high") return "#10B981";
  if (level === "medium") return "#F59E0B";
  return "#EF4444";
}

/* =========================================================================
 *  纯函数 —— 审批操作
 * ========================================================================= */

export type ReviewAction = "approve" | "reject";

/**
 * 计算审批操作后的目标状态。
 * approve → review（终态，已入库）
 * reject → needs_correction
 */
export function getReviewTargetState(action: ReviewAction): DocState {
  return action === "approve" ? "review" : "needs_correction";
}

/* =========================================================================
 *  W4-A8 / E1 纯函数
 * ========================================================================= */

/** live=真 API；demo=MOCK 演示路径；loading=请求中 */
export type DocIntelDataMode = "live" | "demo" | "loading" | "idle";

/** 视觉稿 pipeline-doc-intel 模板（并入本页，不单独建菜单） */
export const DOCINTEL_PIPELINE_TEMPLATES = [
  { id: "classify", label: "分类" },
  { id: "summarize", label: "总结" },
  { id: "translate", label: "翻译" },
  { id: "sentiment", label: "情感" },
  { id: "entity", label: "实体提取" },
  { id: "blank", label: "空模板" },
] as const;

export function pathLabel(mode: DocIntelDataMode): string {
  if (mode === "live") return "真 API";
  if (mode === "loading") return "加载中";
  if (mode === "idle") return "未运行";
  return "演示路径";
}

export function normalizeExtractFields(raw: unknown): ExtractField[] {
  if (!Array.isArray(raw)) return [];
  const out: ExtractField[] = [];
  raw.forEach((item, i) => {
    if (!item || typeof item !== "object") return;
    const o = item as Record<string, unknown>;
    const name = String(o.name ?? o.field ?? `字段${i + 1}`);
    const value = String(o.value ?? o.text ?? "");
    const confidence = typeof o.confidence === "number" ? o.confidence : Number(o.confidence) || 0.8;
    out.push({
      id: String(o.id ?? `xf-${i + 1}`),
      name,
      type: String(o.type ?? "文本"),
      value,
      confidence: Math.min(1, Math.max(0, confidence)),
      source: String(o.source ?? `API L${i + 1}`),
    });
  });
  return out;
}

export type PipelineRunResponse = {
  batchOk?: boolean;
  parsed?: boolean;
  ocr?: { text?: string; preview?: string };
  parse?: { text?: string; preview?: string };
};

export type ApiDocument = {
  id: string;
  name: string;
  file_type?: string;
  status?: string;
  size_bytes?: number;
  content_sha256?: string;
  ocr_text?: string;
  error_message?: string;
  ontology_object_id?: string;
  extracted_fields?: Record<string, unknown>;
  history?: Array<{ state?: string; timestamp?: number | string; note?: string }>;
  created_at?: number;
};

export type DocumentStats = {
  total: number;
  processing: number;
  average_confidence: number | null;
  template_count: number;
};

function normalizeDocState(status?: string): DocState {
  if (status === "processing_ocr" || status === "extracting" || status === "failed" || status === "needs_correction") return status;
  if (status === "review" || status === "extracted" || status === "approved") return "review";
  return "uploaded";
}

function formatTimestamp(raw: number | string | undefined): string {
  if (typeof raw === "number") return new Date(raw * 1000).toISOString().replace("T", " ").slice(0, 16);
  if (typeof raw === "string" && raw) return raw.replace("T", " ").slice(0, 16);
  return "—";
}

export function apiDocumentFields(doc: ApiDocument): ExtractField[] {
  const raw = doc.extracted_fields ? Object.values(doc.extracted_fields) : [];
  return normalizeExtractFields(raw);
}

export function mapApiDocument(doc: ApiDocument): DocItem {
  const fields = apiDocumentFields(doc);
  return {
    id: doc.id,
    title: doc.name,
    type: inferFileType(doc.name),
    size: Number(doc.size_bytes || 0),
    status: normalizeDocState(doc.status),
    uploadedAt: formatTimestamp(doc.created_at),
    ocrText: doc.ocr_text || "",
    errorMessage: doc.error_message || undefined,
    ontologyObjectId: doc.ontology_object_id || undefined,
    contentSha256: doc.content_sha256 || undefined,
    extractedFields: fields,
    history: (doc.history || []).map((entry) => ({
      state: normalizeDocState(entry.state),
      timestamp: formatTimestamp(entry.timestamp),
      note: String(entry.note || ""),
    })),
  };
}

export function requireMatchingDocument(
  document: ApiDocument,
  expectedId: string,
  operation: string,
): ApiDocument {
  if (!document || document.id !== expectedId) {
    throw new Error(`${operation}响应文档错配：期望 ${expectedId}，实际 ${document?.id || "缺失"}`);
  }
  return document;
}

export async function uploadDocumentFile(
  file: File,
  fetchImpl: typeof fetch = fetch,
): Promise<ApiDocument> {
  const path = `/api/datasource/documents/upload?name=${encodeURIComponent(file.name)}`;
  const response = await fetchImpl(`${getApiBase()}${path}`, {
    method: "POST",
    headers: {
      ...tenantAuthHeaders(),
      "Content-Type": file.type || "application/octet-stream",
    },
    body: file,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { detail?: string; message?: string };
    throw new Error(body.detail || body.message || `上传失败 HTTP ${response.status}`);
  }
  return response.json() as Promise<ApiDocument>;
}

/* =========================================================================
 *  子组件
 * ========================================================================= */

function StatCard({ value, label, trend, trendUp }: { value: string; label: string; trend: string; trendUp?: boolean }) {
  return (
    <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 2, padding: 16 }}>
      <div style={{ fontSize: 24, fontWeight: 600, color: "var(--aos-text)", lineHeight: 1.2 }}>{value}</div>
      <div style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginTop: 4 }}>{label}</div>
      <div style={{ fontSize: 11, marginTop: 6, color: trendUp ? "var(--aos-green)" : "var(--aos-text-secondary)" }}>
        {trendUp ? "↑ " : ""}
        {trend}
      </div>
    </div>
  );
}

function DocIcon({ type }: { type: FileType }) {
  const meta = TYPE_META[type];
  return (
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke={meta.color} strokeWidth="1">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M14 2v6h6" strokeLinecap="round" strokeLinejoin="round" />
      <text x="12" y="17" fontSize="4" fill={meta.color} stroke="none" fontWeight="bold" textAnchor="middle">
        {meta.label}
      </text>
    </svg>
  );
}

/* ---- 状态步骤条 ---- */
function StateStepper({ state, errorMessage }: { state: DocState; errorMessage?: string }) {
  const stepIdx = getStepIndex(state);
  const labels = [
    { key: "uploaded", title: "上传" },
    { key: "processing_ocr", title: "OCR 识别" },
    { key: "extracting", title: "LLM 提取" },
    { key: "review", title: "审核" },
  ];

  return (
    <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 2, padding: "16px 24px", marginBottom: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 0 }}>
        {labels.map((label, i) => {
          const isDone = i < stepIdx;
          const isCurrent = i === stepIdx && state !== "failed";
          const isFailed = state === "failed" && i === stepIdx;
          const isCorrection = state === "needs_correction" && i === stepIdx;
          const color = isFailed
            ? "var(--aos-red)"
            : isCorrection
              ? "var(--aos-amber)"
              : isDone
                ? "var(--aos-green)"
                : isCurrent
                  ? STATE_META[state].color
                  : "var(--aos-border-strong)";
          return (
            <div key={label.key} style={{ display: "flex", alignItems: "center", flex: i === labels.length - 1 ? "0 0 auto" : "1 1 auto" }}>
              {/* 圆形节点 */}
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
                <div
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: "50%",
                    background: color,
                    color: "var(--text-on-brand)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 12,
                    fontWeight: 600,
                  }}
                >
                  {isDone ? "✓" : i + 1}
                </div>
                <span style={{ fontSize: 11, color: isCurrent || isDone ? "var(--aos-text)" : "var(--aos-text-tertiary)", fontWeight: isCurrent ? 600 : 400 }}>
                  {label.title}
                </span>
              </div>
              {/* 连线 */}
              {i < labels.length - 1 && (
                <div
                  style={{
                    flex: 1,
                    height: 2,
                    background: i < stepIdx ? "var(--aos-green)" : "var(--aos-border)",
                    margin: "0 8px",
                    marginBottom: 18,
                  }}
                />
              )}
            </div>
          );
        })}
      </div>
      {state === "failed" && errorMessage && (
        <div style={{ marginTop: 8, padding: "6px 10px", background: "var(--aos-red-bg)", borderRadius: 4, fontSize: 12, color: "var(--aos-red)" }}>
          ⚠ {errorMessage}
        </div>
      )}
      {state === "needs_correction" && (
        <div style={{ marginTop: 8, padding: "6px 10px", background: "var(--aos-amber-bg)", borderRadius: 4, fontSize: 12, color: "var(--aos-amber)" }}>
          ⚠ 部分字段置信度低于阈值 ({CONFIDENCE_THRESHOLD})，需要人工修正
        </div>
      )}
    </div>
  );
}

/* ---- 拖拽上传区 ---- */
function UploadDropZone({ onFiles }: { onFiles: (files: File[]) => void }) {
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFiles = useCallback(
    (fileList: FileList | null) => {
      if (!fileList || fileList.length === 0) return;
      const files = Array.from(fileList);
      for (const f of files) {
        const err = validateFile(f.name, f.size);
        if (err) {
          setError(err);
          return;
        }
      }
      setError(null);
      onFiles(files);
    },
    [onFiles],
  );

  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        handleFiles(e.dataTransfer.files);
      }}
      onClick={() => document.getElementById("doc-file-input")?.click()}
      style={{
        border: dragOver ? "2px dashed var(--aos-accent)" : "2px dashed var(--aos-border-strong)",
        borderRadius: 2,
        padding: "28px 20px",
        textAlign: "center",
        cursor: "pointer",
        background: dragOver ? "var(--aos-accent-light)" : "var(--aos-surface-hover)",
        transition: "all 0.15s",
        marginBottom: 16,
      }}
    >
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="var(--aos-text-tertiary)" strokeWidth="1.5" style={{ margin: "0 auto 8px" }}>
        <path d="M12 16V4M12 4l-4 4M12 4l4 4" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" strokeLinecap="round" />
      </svg>
      <div style={{ fontSize: 13, color: "var(--aos-text)", fontWeight: 500 }}>拖拽文件到此处，或点击选择文件</div>
      <div style={{ fontSize: 11, color: "var(--aos-text-tertiary)", marginTop: 4 }}>
        支持 PDF / Word / Excel / 图片 / PPT，单个文件最大 {Math.round(MAX_FILE_SIZE / 1024 / 1024)}MB
      </div>
      <input
        id="doc-file-input"
        aria-label="选择待导入文档"
        type="file"
        multiple
        style={{ display: "none" }}
        accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.ppt,.pptx"
        onChange={(e) => handleFiles(e.target.files)}
      />
      {error && (
        <div style={{ marginTop: 8, fontSize: 12, color: "var(--aos-red)" }}>⚠ {error}</div>
      )}
    </div>
  );
}

/* ---- OCR 面板 ---- */
function OcrPanel({ doc, onCorrectText }: { doc: DocItem; onCorrectText: (text: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(doc.ocrText ?? "");

  useEffect(() => {
    setText(doc.ocrText ?? "");
    setEditing(false);
  }, [doc.id, doc.ocrText]);

  return (
    <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 2, padding: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--aos-text)" }}>OCR 识别结果</h3>
        <button
          type="button"
          onClick={() => {
            if (editing) onCorrectText(text);
            setEditing(!editing);
          }}
          style={{
            padding: "4px 10px",
            fontSize: 12,
            borderRadius: 4,
            border: "1px solid var(--aos-border)",
            background: editing ? "var(--aos-accent)" : "var(--aos-surface)",
            color: editing ? "var(--text-on-brand)" : "var(--aos-text)",
            cursor: "pointer",
          }}
        >
          {editing ? "保存" : "手动校正"}
        </button>
      </div>

      <div style={{ display: "flex", gap: 16 }}>
        {/* 左侧：文档原图模拟 */}
        <div style={{ flex: "0 0 200px", height: 240, background: "var(--aos-surface-hover)", border: "1px solid var(--aos-border)", borderRadius: 4, position: "relative", overflow: "hidden" }}>
          <svg width="100%" height="100%" viewBox="0 0 200 240">
            {/* 模拟文档背景 */}
            <rect x="10" y="10" width="180" height="220" fill="var(--aos-surface)" stroke="var(--aos-border)" />
            {/* 模拟 OCR 识别框 */}
            <rect x="20" y="25" width="120" height="12" fill="none" stroke="var(--aos-green)" strokeWidth="1" strokeDasharray="3 2" />
            <rect x="20" y="50" width="80" height="12" fill="none" stroke="var(--aos-amber)" strokeWidth="1" strokeDasharray="3 2" />
            <rect x="20" y="75" width="140" height="12" fill="none" stroke="var(--aos-green)" strokeWidth="1" strokeDasharray="3 2" />
            <rect x="20" y="100" width="100" height="12" fill="none" stroke="var(--aos-red)" strokeWidth="1" strokeDasharray="3 2" />
            <rect x="20" y="125" width="110" height="12" fill="none" stroke="var(--aos-green)" strokeWidth="1" strokeDasharray="3 2" />
            {/* 标注 */}
            <text x="150" y="33" fontSize="7" fill="var(--aos-green)">98%</text>
            <text x="110" y="58" fontSize="7" fill="var(--aos-amber)">85%</text>
            <text x="170" y="83" fontSize="7" fill="var(--aos-green)">92%</text>
            <text x="130" y="108" fontSize="7" fill="var(--aos-red)">65%</text>
            <text x="140" y="133" fontSize="7" fill="var(--aos-green)">91%</text>
          </svg>
        </div>

        {/* 右侧：识别文本 */}
        <div style={{ flex: 1 }}>
          {doc.status === "processing_ocr" && doc.ocrProgress !== undefined && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--aos-text-secondary)", marginBottom: 4 }}>
                <span>识别进度</span>
                <span>{doc.ocrProgress}% · 预估剩余 {Math.ceil((100 - doc.ocrProgress) / 10)}s</span>
              </div>
              <div style={{ height: 6, background: "var(--aos-bg-secondary)", borderRadius: 3, overflow: "hidden" }}>
                <div style={{ width: `${doc.ocrProgress}%`, height: "100%", background: "var(--aos-amber)", transition: "width 0.3s" }} />
              </div>
            </div>
          )}
          {editing ? (
            <textarea
              aria-label="OCR 识别文本修正"
              value={text}
              onChange={(e) => setText(e.target.value)}
              style={{ width: "100%", height: 180, padding: 8, fontSize: 12, border: "1px solid var(--aos-border)", borderRadius: 4, fontFamily: "monospace", resize: "vertical" }}
            />
          ) : (
            <pre
              data-testid="ocr-text"
              style={{ whiteSpace: "pre-wrap", fontSize: 12, color: "var(--aos-text)", lineHeight: 1.6, fontFamily: "monospace", margin: 0 }}
            >
              {doc.ocrText || "（暂无识别文本）"}
            </pre>
          )}
          <div style={{ marginTop: 8, fontSize: 11, color: "var(--aos-text-tertiary)" }}>
            绿色框 = 高置信度 · 橙色框 = 中置信度 · 红色框 = 低置信度（需人工校正）
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---- LLM 提取面板 ---- */
function ExtractionPanel({
  fields,
  onEditField,
  selectedTemplate,
  onTemplateChange,
  dataMode,
  running,
  onRunExtract,
}: {
  fields: ExtractField[];
  onEditField: (id: string, value: string) => void;
  selectedTemplate: TemplateId;
  onTemplateChange: (id: TemplateId) => void;
  dataMode: DocIntelDataMode;
  running: boolean;
  onRunExtract: () => void;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  return (
    <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 2, padding: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, gap: 8, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--aos-text)", margin: 0 }}>LLM 结构化提取结果</h3>
          <span
            className={`w4-e1-path-badge${dataMode === "demo" ? " is-demo" : dataMode === "live" ? " is-live" : ""}`}
            data-testid="extract-path-badge"
          >
            {pathLabel(dataMode)}
          </span>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <select
            aria-label="提取模板"
            value={selectedTemplate}
            onChange={(e) => onTemplateChange(e.target.value as TemplateId)}
            style={{ padding: "4px 8px", fontSize: 12, borderRadius: 4, border: "1px solid var(--aos-border)", background: "var(--aos-surface)", color: "var(--aos-text)" }}
          >
            {TEMPLATES.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            data-testid="run-extract-btn"
            disabled={running}
            onClick={onRunExtract}
            style={{
              padding: "4px 10px",
              fontSize: 12,
              borderRadius: 4,
              border: "1px solid var(--aos-indigo-border)",
              background: "var(--aos-accent)",
              color: "var(--text-on-brand)",
              cursor: running ? "wait" : "pointer",
              opacity: running ? 0.7 : 1,
            }}
          >
            {running ? "抽取中…" : "运行抽取"}
          </button>
        </div>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
        <thead>
          <tr style={{ borderBottom: "2px solid var(--aos-border)" }}>
            <th style={{ textAlign: "left", padding: "6px 8px", color: "var(--aos-text-secondary)", fontWeight: 500, width: "20%" }}>字段名</th>
            <th style={{ textAlign: "left", padding: "6px 8px", color: "var(--aos-text-secondary)", fontWeight: 500, width: "30%" }}>提取值</th>
            <th style={{ textAlign: "center", padding: "6px 8px", color: "var(--aos-text-secondary)", fontWeight: 500, width: "15%" }}>置信度</th>
            <th style={{ textAlign: "left", padding: "6px 8px", color: "var(--aos-text-secondary)", fontWeight: 500, width: "20%" }}>来源位置</th>
            <th style={{ textAlign: "center", padding: "6px 8px", color: "var(--aos-text-secondary)", fontWeight: 500, width: "15%" }}>操作</th>
          </tr>
        </thead>
        <tbody>
          {fields.map((field) => {
            const confColor = getConfidenceColor(field.confidence);
            const isLow = getConfidenceLevel(field.confidence) === "low";
            const isEditing = editingId === field.id;
            return (
              <tr key={field.id} style={{ borderBottom: "1px solid var(--aos-bg-secondary)" }}>
                <td style={{ padding: "6px 8px", color: "var(--aos-text)", fontWeight: 500 }}>{field.name}</td>
                <td style={{ padding: "6px 8px", color: "var(--aos-text)" }}>
                  {isEditing ? (
                    <input
                      aria-label={`修正字段 ${field.name}`}
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          onEditField(field.id, editValue);
                          setEditingId(null);
                        }
                      }}
                      style={{ width: "100%", padding: "2px 4px", fontSize: 12, border: "1px solid var(--aos-accent)", borderRadius: 3 }}
                      autoFocus
                    />
                  ) : (
                    <span style={{ background: isLow ? "var(--aos-amber-bg)" : "transparent", padding: "1px 4px", borderRadius: 2 }}>
                      {field.value}
                    </span>
                  )}
                </td>
                <td style={{ padding: "6px 8px", textAlign: "center" }}>
                  <span style={{ color: confColor, fontWeight: 600, fontSize: 11 }}>
                    {(field.confidence * 100).toFixed(0)}%
                  </span>
                </td>
                <td style={{ padding: "6px 8px", color: "var(--aos-text-tertiary)", fontSize: 11 }}>{field.source}</td>
                <td style={{ padding: "6px 8px", textAlign: "center" }}>
                  <button
                    type="button"
                    onClick={() => {
                      if (isEditing) {
                        onEditField(field.id, editValue);
                        setEditingId(null);
                      } else {
                        setEditingId(field.id);
                        setEditValue(field.value);
                      }
                    }}
                    style={{ fontSize: 11, color: "var(--aos-accent)", background: "none", border: "none", cursor: "pointer", textDecoration: "underline" }}
                  >
                    {isEditing ? "保存" : "修正"}
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/* ---- 审核台 ---- */
function ReviewPanel({
  fields,
  doc,
  onApprove,
  onReject,
  objectTypes,
  objectTypeId,
  onObjectTypeChange,
  busy,
}: {
  fields: ExtractField[];
  doc: DocItem;
  onApprove: () => void;
  onReject: () => void;
  objectTypes: Array<{ id: string; name: string }>;
  objectTypeId: string;
  onObjectTypeChange: (id: string) => void;
  busy: boolean;
}) {
  const avgConf = fields.length > 0 ? fields.reduce((s, f) => s + f.confidence, 0) / fields.length : 0;

  return (
    <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 2, padding: 16 }}>
      <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--aos-text)", marginBottom: 12 }}>审核台</h3>

      {/* 总览 */}
      <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
        <div style={{ flex: 1, padding: 12, background: "var(--aos-surface-hover)", borderRadius: 2 }}>
          <div style={{ fontSize: 11, color: "var(--aos-text-secondary)" }}>提取字段数</div>
          <div style={{ fontSize: 20, fontWeight: 600, color: "var(--aos-text)", marginTop: 2 }}>{fields.length}</div>
        </div>
        <div style={{ flex: 1, padding: 12, background: "var(--aos-surface-hover)", borderRadius: 2 }}>
          <div style={{ fontSize: 11, color: "var(--aos-text-secondary)" }}>平均置信度</div>
          <div style={{ fontSize: 20, fontWeight: 600, color: getConfidenceColor(avgConf), marginTop: 2 }}>
            {(avgConf * 100).toFixed(1)}%
          </div>
        </div>
        <div style={{ flex: 1, padding: 12, background: "var(--aos-surface-hover)", borderRadius: 2 }}>
          <div style={{ fontSize: 11, color: "var(--aos-text-secondary)" }}>低置信度字段</div>
          <div style={{ fontSize: 20, fontWeight: 600, color: "var(--aos-red)", marginTop: 2 }}>
            {fields.filter((f) => getConfidenceLevel(f.confidence) === "low").length}
          </div>
        </div>
      </div>

      {/* 操作按钮 */}
      <label style={{ display: "block", marginBottom: 8, fontSize: 12, color: "var(--aos-text-secondary)" }}>
        写入目标 Object Type
        <select
          aria-label="写入目标 Object Type"
          data-testid="ontology-type-select"
          value={objectTypeId}
          onChange={(event) => onObjectTypeChange(event.target.value)}
          style={{ display: "block", width: "100%", marginTop: 4, padding: "6px 8px" }}
        >
          <option value="">请选择后端已有 Object Type</option>
          {objectTypes.map((item) => <option key={item.id} value={item.id}>{item.name}（{item.id}）</option>)}
        </select>
      </label>
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button
          type="button"
          onClick={onApprove}
          disabled={busy || !objectTypeId || fields.length === 0}
          data-testid="ontology-write-btn"
          style={{
            flex: 1,
            padding: "8px 12px",
            fontSize: 13,
            fontWeight: 500,
            borderRadius: 2,
            border: "1px solid var(--aos-green)",
            background: "var(--aos-green)",
            color: "var(--text-on-brand)",
            cursor: busy || !objectTypeId || fields.length === 0 ? "not-allowed" : "pointer",
            opacity: busy || !objectTypeId || fields.length === 0 ? 0.6 : 1,
          }}
        >
          ✓ 确认入库（写入本体 Objects）
        </button>
        <button
          type="button"
          onClick={onReject}
          disabled={busy}
          style={{
            flex: 1,
            padding: "8px 12px",
            fontSize: 13,
            fontWeight: 500,
            borderRadius: 2,
            border: "1px solid var(--aos-border)",
            background: "var(--aos-surface)",
            color: "var(--aos-red)",
            cursor: "pointer",
          }}
        >
          ✗ 退回修正
        </button>
      </div>

      {/* 历史时间线 */}
      {doc.history && doc.history.length > 0 && (
        <div>
          <h4 style={{ fontSize: 12, fontWeight: 600, color: "var(--aos-text-secondary)", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 8 }}>
            处理历史
          </h4>
          <div style={{ position: "relative", paddingLeft: 16 }}>
            <div style={{ position: "absolute", left: 5, top: 4, bottom: 4, width: 2, background: "var(--aos-border)" }} />
            {doc.history.map((entry, idx) => (
              <div key={idx} style={{ position: "relative", marginBottom: 12 }}>
                <div
                  style={{
                    position: "absolute",
                    left: -16,
                    top: 2,
                    width: 12,
                    height: 12,
                    borderRadius: "50%",
                    background: STATE_META[entry.state].color,
                    border: "2px solid var(--aos-surface)",
                    boxShadow: "0 0 0 1px var(--aos-border)",
                  }}
                />
                <div style={{ fontSize: 12, fontWeight: 500, color: "var(--aos-text)" }}>{STATE_META[entry.state].label}</div>
                <div style={{ fontSize: 11, color: "var(--aos-text-tertiary)" }}>
                  {entry.timestamp} · {entry.note}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* =========================================================================
 *  主组件
 * ========================================================================= */

export function DocumentIntelligencePage() {
  const [docs, setDocs] = useState<DocItem[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateId>("finance_report");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [extractFields, setExtractFields] = useState<ExtractField[]>([]);
  const [dataMode, setDataMode] = useState<DocIntelDataMode>("idle");
  const [extractRunning, setExtractRunning] = useState(false);
  const [pipelineRunning, setPipelineRunning] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string>("");
  const [pipelineTpl, setPipelineTpl] = useState<string>("entity");
  const [stats, setStats] = useState<DocumentStats>({ total: 0, processing: 0, average_confidence: null, template_count: 0 });
  const [objectTypes, setObjectTypes] = useState<Array<{ id: string; name: string }>>([]);
  const [objectTypeId, setObjectTypeId] = useState("");

  const selectedDoc = useMemo(() => docs.find((d) => d.id === selectedId) ?? docs[0], [docs, selectedId]);

  const loadStats = useCallback(async () => {
    const value = await apiGet<DocumentStats>("/api/datasource/documents/stats");
    setStats(value);
  }, []);

  const reportWriteSuccess = useCallback(async (message: string) => {
    try {
      await loadStats();
      setStatusMsg(message);
    } catch (error) {
      setStatusMsg(`${message}；写入成功但统计刷新失败：${String((error as Error).message || error)}`);
    }
  }, [loadStats]);

  const replaceDocument = useCallback((raw: ApiDocument) => {
    const mapped = mapApiDocument(raw);
    setDocs((prev) => prev.map((item) => item.id === mapped.id ? mapped : item));
    if (mapped.id === selectedId) setExtractFields(mapped.extractedFields || []);
    return mapped;
  }, [selectedId]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setStatusMsg("");
      try {
        const [documents, currentStats] = await Promise.all([
          apiGet<{ items: ApiDocument[]; total: number }>("/api/datasource/documents?page=1&page_size=100"),
          apiGet<DocumentStats>("/api/datasource/documents/stats"),
        ]);
        if (cancelled) return;
        const mapped = documents.items.map(mapApiDocument);
        setDocs(mapped);
        setStats(currentStats);
        if (mapped[0]) setSelectedId(mapped[0].id);
        try {
          const types = await apiGet<{ items: Array<{ id: string; name?: string; display_name?: string }> }>("/v1/ontology/object-types?page=1&page_size=100");
          if (!cancelled) setObjectTypes(types.items.map((item) => ({ id: item.id, name: item.display_name || item.name || item.id })));
        } catch (error) {
          if (!cancelled) setStatusMsg(`文档已加载；本体类型加载失败，入库功能已禁用：${String((error as Error).message || error)}`);
        }
      } catch (error) {
        if (!cancelled) setStatusMsg(`加载失败，未使用演示数据：${String((error as Error).message || error)}`);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    setExtractFields(selectedDoc?.extractedFields || []);
    setDataMode(selectedDoc?.extractedFields?.length ? "live" : "idle");
  }, [selectedDoc?.id]);

  const runExtract = useCallback(async () => {
    const doc = docs.find((d) => d.id === selectedId);
    if (!doc) return;
    setExtractRunning(true);
    setDataMode("loading");
    setStatusMsg("");
    try {
      const res = await apiPost<ApiDocument>(
        `/api/datasource/documents/${encodeURIComponent(doc.id)}/extract`,
        { template_id: selectedTemplate },
      );
      const mapped = replaceDocument(requireMatchingDocument(res, doc.id, "抽取"));
      setDataMode("live");
      await reportWriteSuccess(`抽取完成 · 真 API · ${mapped.extractedFields?.length || 0} 字段`);
    } catch (e) {
      setDataMode(doc.extractedFields?.length ? "live" : "idle");
      setStatusMsg(`抽取失败，未生成演示结果：${String((e as Error).message || e)}`);
    } finally {
      setExtractRunning(false);
    }
  }, [docs, selectedId, selectedTemplate, replaceDocument, reportWriteSuccess]);

  const runPipelineTrial = useCallback(async () => {
    const doc = docs.find((d) => d.id === selectedId) ?? docs[0];
    if (!doc) return;
    setPipelineRunning(true);
    setStatusMsg("");
    try {
      const res = await apiPost<PipelineRunResponse>("/v1/docintel/pipeline", {
        textHint: (doc.ocrText || "").trim() || doc.title,
        name: doc.title,
        template: pipelineTpl,
      });
      const ocrText =
        res.ocr?.text ||
        res.ocr?.preview ||
        res.parse?.text ||
        res.parse?.preview ||
        doc.ocrText;
      if (ocrText) {
        setDocs((prev) => prev.map((d) => (d.id === doc.id ? { ...d, ocrText } : d)));
      }
      if (!res.batchOk && !res.parsed && !ocrText) throw new Error("后端未返回成功证据");
      setStatusMsg(`管道试运行成功 · 真 API · 模板 ${pipelineTpl}`);
    } catch (e) {
      setStatusMsg(`管道试运行失败，未生成演示结果：${String((e as Error).message || e)}`);
    } finally {
      setPipelineRunning(false);
    }
  }, [docs, selectedId, pipelineTpl]);

  const handleFiles = useCallback(async (files: File[]) => {
    setActionBusy(true);
    setStatusMsg("");
    try {
      const results = await Promise.allSettled(files.map((file) => uploadDocumentFile(file)));
      const uploaded = results
        .filter((result): result is PromiseFulfilledResult<ApiDocument> => result.status === "fulfilled")
        .map((result) => mapApiDocument(result.value));
      const failed = results.filter((result) => result.status === "rejected");
      if (uploaded.length) {
        setDocs((prev) => [...uploaded, ...prev]);
        setSelectedId(uploaded[0].id);
      }
      const message = failed.length
        ? `上传完成 ${uploaded.length} 个，失败 ${failed.length} 个；失败文件未加入列表`
        : `上传成功 · 服务端已接收 ${uploaded.length} 个文件的真实字节`;
      if (uploaded.length) await reportWriteSuccess(message);
      else setStatusMsg(message);
    } finally {
      setActionBusy(false);
    }
  }, [reportWriteSuccess]);

  const handleEditField = useCallback(async (id: string, value: string) => {
    if (!selectedDoc) return;
    const next = extractFields.map((field) => field.id === id ? { ...field, value, confidence: Math.max(field.confidence, 0.95) } : field);
    setActionBusy(true);
    try {
      const res = await apiPut<ApiDocument>(`/api/datasource/documents/${encodeURIComponent(selectedDoc.id)}`, { extracted_fields: next });
      replaceDocument(requireMatchingDocument(res, selectedDoc.id, "字段保存"));
      await reportWriteSuccess("字段修正已保存 · 真 API");
    } catch (error) {
      setStatusMsg(`字段保存失败，原值未改变：${String((error as Error).message || error)}`);
    } finally {
      setActionBusy(false);
    }
  }, [selectedDoc, extractFields, replaceDocument, reportWriteSuccess]);

  const handleCorrectOcr = useCallback(async (text: string) => {
    if (!selectedDoc) return;
    setActionBusy(true);
    try {
      const res = await apiPut<ApiDocument>(`/api/datasource/documents/${encodeURIComponent(selectedDoc.id)}`, { ocr_text: text });
      replaceDocument(requireMatchingDocument(res, selectedDoc.id, "OCR 保存"));
      await reportWriteSuccess("OCR 校正已保存 · 真 API");
    } catch (error) {
      setStatusMsg(`OCR 保存失败，原文未改变：${String((error as Error).message || error)}`);
    } finally {
      setActionBusy(false);
    }
  }, [selectedDoc, replaceDocument, reportWriteSuccess]);

  const handleApprove = useCallback(async () => {
    if (!selectedDoc || !objectTypeId) return;
    setActionBusy(true);
    try {
      const res = await apiPost<{ document: ApiDocument; object: { id: string } }>(
        `/api/datasource/documents/${encodeURIComponent(selectedDoc.id)}/ontology-write`,
        { object_type_id: objectTypeId },
      );
      replaceDocument(requireMatchingDocument(res.document, selectedDoc.id, "本体写入"));
      await reportWriteSuccess(`本体写入成功 · Object ${res.object.id}`);
    } catch (error) {
      setStatusMsg(`本体写入失败，文档状态未伪造：${String((error as Error).message || error)}`);
    } finally {
      setActionBusy(false);
    }
  }, [selectedDoc, objectTypeId, replaceDocument, reportWriteSuccess]);

  const handleReject = useCallback(async () => {
    if (!selectedDoc) return;
    setActionBusy(true);
    try {
      const res = await apiPost<ApiDocument>(`/api/datasource/documents/${encodeURIComponent(selectedDoc.id)}/review`, { action: "reject" });
      replaceDocument(requireMatchingDocument(res, selectedDoc.id, "退回修正"));
      await reportWriteSuccess("已退回修正 · 真 API");
    } catch (error) {
      setStatusMsg(`退回失败，状态未改变：${String((error as Error).message || error)}`);
    } finally {
      setActionBusy(false);
    }
  }, [selectedDoc, replaceDocument, reportWriteSuccess]);

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const toggleSelectAll = useCallback(() => {
    setSelectedIds((prev) => {
      if (prev.size === docs.length) return new Set();
      return new Set(docs.map((d) => d.id));
    });
  }, [docs]);

  const handleBatchDelete = useCallback(async () => {
    const ids = [...selectedIds];
    setActionBusy(true);
    try {
      const results = await Promise.allSettled(ids.map((id) => apiDelete<{ deleted: boolean }>(`/api/datasource/documents/${encodeURIComponent(id)}`)));
      const deletedByResponse = new Set(ids.filter((_, index) => {
        const result = results[index];
        return result.status === "fulfilled" && result.value.deleted === true;
      }));
      let deleted = deletedByResponse;
      try {
        const current = await apiGet<{ items: ApiDocument[]; total: number }>("/api/datasource/documents?page=1&page_size=100");
        const currentIds = new Set(current.items.map((doc) => doc.id));
        deleted = new Set(ids.filter((id) => deletedByResponse.has(id) || !currentIds.has(id)));
        setDocs(current.items.filter((doc) => !deleted.has(doc.id)).map(mapApiDocument));
      } catch {
        setDocs((prev) => prev.filter((doc) => !deletedByResponse.has(doc.id)));
      }
      setSelectedIds(new Set(ids.filter((id) => !deleted.has(id))));
      const message = `删除成功 ${deleted.size} 个，失败 ${ids.length - deleted.size} 个`;
      if (deleted.size) await reportWriteSuccess(message);
      else setStatusMsg(message);
    } finally {
      setActionBusy(false);
    }
  }, [selectedIds, reportWriteSuccess]);

  const handleBatchReprocess = useCallback(async () => {
    const ids = [...selectedIds];
    setActionBusy(true);
    try {
      const results = await Promise.allSettled(ids.map(async (id) => {
        const response = await apiPost<ApiDocument>(
          `/api/datasource/documents/${encodeURIComponent(id)}/reprocess`,
          { template_id: selectedTemplate },
        );
        return requireMatchingDocument(response, id, "重新处理");
      }));
      const succeeded = results
        .filter((result): result is PromiseFulfilledResult<ApiDocument> => result.status === "fulfilled")
        .map((result) => result.value);
      succeeded.forEach(replaceDocument);
      const message = `重新处理成功 ${succeeded.length} 个，失败 ${ids.length - succeeded.length} 个；失败项保持原状态`;
      if (succeeded.length) await reportWriteSuccess(message);
      else setStatusMsg(message);
    } finally {
      setActionBusy(false);
    }
  }, [selectedIds, selectedTemplate, replaceDocument, reportWriteSuccess]);

  return (
    <PageChrome title="文档智能" lede="导入文档、配置提取模板，自动识别并结构化关键字段">
      {/* E1：DocIntel 管道并入说明 */}
      <div className="w4-e1-notice" data-testid="docintel-merge-notice">
        <strong>DocIntel 管道能力收敛于此页</strong>
        <span>（原 pipeline-doc-intel 视觉稿，不单独建侧栏菜单；抽取与流水线试运行在本页完成）</span>
      </div>

      {/* E1：轻量管道能力条 */}
      <div className="w4-e1-pipeline-strip" data-testid="docintel-pipeline-strip">
        <div className="w4-e1-pipeline-nodes" aria-label="DocIntel 迷你管道">
          <span className="w4-e1-node">输入</span>
          <span className="w4-e1-arrow">→</span>
          <span className="w4-e1-node is-llm">Use LLM</span>
          <span className="w4-e1-arrow">→</span>
          <span className="w4-e1-node">输出</span>
        </div>
        <div className="w4-e1-pipeline-templates">
          {DOCINTEL_PIPELINE_TEMPLATES.map((t) => (
            <button
              key={t.id}
              type="button"
              className={`w4-e1-tpl-chip${pipelineTpl === t.id ? " is-active" : ""}`}
              onClick={() => setPipelineTpl(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          data-testid="pipeline-trial-btn"
          disabled={pipelineRunning}
          onClick={() => void runPipelineTrial()}
          className="w4-e1-trial-btn"
        >
          {pipelineRunning ? "试运行中…" : "管道试运行"}
        </button>
      </div>

      {statusMsg ? (
        <div className="w4-e1-status-msg" data-testid="docintel-status-msg">
          {statusMsg}
        </div>
      ) : null}

      {/* 顶部统计卡片 */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
        <StatCard value={String(stats.total)} label="文档总数" trend="来自文档 API" />
        <StatCard value={stats.average_confidence == null ? "—" : `${(stats.average_confidence * 100).toFixed(1)}%`} label="平均提取置信度" trend="按后端提取字段计算" />
        <StatCard value={String(stats.processing)} label="处理中" trend="按后端状态计算" />
        <StatCard value={String(stats.template_count)} label="提取模板" trend="来自模板 API" />
      </div>

      {/* 拖拽上传区 */}
      <UploadDropZone onFiles={handleFiles} />

      {/* 批量操作栏 */}
      {selectedIds.size > 0 && (
        <div style={{ display: "flex", gap: 8, marginBottom: 12, padding: "8px 12px", background: "var(--aos-accent-light)", borderRadius: 2, alignItems: "center" }}>
          <span style={{ fontSize: 12, color: "var(--aos-accent)" }}>已选择 {selectedIds.size} 个文件</span>
          <button type="button" disabled={actionBusy} onClick={() => void handleBatchReprocess()} style={batchBtnStyle}>重新处理</button>
          <button type="button" disabled={actionBusy} onClick={() => void handleBatchDelete()} style={{ ...batchBtnStyle, color: "var(--aos-red)", borderColor: "var(--aos-red-border)" }}>删除</button>
        </div>
      )}

      {/* 状态步骤条 */}
      {selectedDoc ? <StateStepper state={selectedDoc.status} errorMessage={selectedDoc.errorMessage} /> : null}

      {/* 主体：左文件列表 + 右提取面板 */}
      <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
        {/* 文件列表 */}
        <div style={{ flex: "0 0 400px" }}>
          {/* 全选 */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, padding: "0 4px" }}>
            <input
              type="checkbox"
              aria-label="选择全部文档"
              checked={selectedIds.size === docs.length && docs.length > 0}
              onChange={toggleSelectAll}
              style={{ cursor: "pointer" }}
            />
            <span style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>全选 ({docs.length})</span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {docs.map((doc) => {
              const meta = STATE_META[doc.status];
              const isSelected = doc.id === selectedId;
              const isChecked = selectedIds.has(doc.id);
              return (
                <div
                  key={doc.id}
                  data-testid={`doc-item-${doc.id}`}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: 10,
                    border: isSelected ? "1px solid var(--aos-accent)" : "1px solid var(--aos-border)",
                    borderRadius: 2,
                    background: isSelected ? "var(--aos-accent-light)" : "var(--aos-surface)",
                    cursor: "pointer",
                    boxShadow: isSelected ? "0 0 0 3px var(--aos-indigo-50)" : "none",
                  }}
                  onClick={() => setSelectedId(doc.id)}
                >
                  <input
                    type="checkbox"
                    aria-label={`选择文档 ${doc.title}`}
                    checked={isChecked}
                    onChange={(e) => {
                      e.stopPropagation();
                      toggleSelect(doc.id);
                    }}
                    onClick={(e) => e.stopPropagation()}
                    style={{ cursor: "pointer" }}
                  />
                  <DocIcon type={doc.type} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: "var(--aos-text)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {doc.title}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--aos-text-tertiary)", marginTop: 2, display: "flex", gap: 8 }}>
                      <span>{formatFileSize(doc.size)}</span>
                      <span>{doc.uploadedAt}</span>
                    </div>
                  </div>
                  <span
                    style={{
                      padding: "2px 8px",
                      borderRadius: 4,
                      fontSize: 10,
                      fontWeight: 500,
                      background: meta.bg,
                      color: meta.color,
                      whiteSpace: "nowrap",
                    }}
                  >
                    {meta.label}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* 右侧：OCR + 提取 + 审核 */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 16 }}>
          {!selectedDoc ? <div data-testid="documents-empty">暂无文档。上传成功后才会加入列表。</div> : null}
          {selectedDoc ? <OcrPanel doc={selectedDoc} onCorrectText={(text) => void handleCorrectOcr(text)} /> : null}
          {selectedDoc ? (
          <ExtractionPanel
            fields={extractFields}
            onEditField={handleEditField}
            selectedTemplate={selectedTemplate}
            onTemplateChange={setSelectedTemplate}
            dataMode={dataMode}
            running={extractRunning}
            onRunExtract={() => void runExtract()}
          />
          ) : null}
          {selectedDoc ? (
            <ReviewPanel
              fields={extractFields}
              doc={selectedDoc}
              onApprove={() => void handleApprove()}
              onReject={() => void handleReject()}
              objectTypes={objectTypes}
              objectTypeId={objectTypeId}
              onObjectTypeChange={setObjectTypeId}
              busy={actionBusy}
            />
          ) : null}
        </div>
      </div>
    </PageChrome>
  );
}

const batchBtnStyle: React.CSSProperties = {
  padding: "4px 10px",
  fontSize: 12,
  borderRadius: 4,
  border: "1px solid var(--aos-indigo-border)",
  background: "var(--aos-surface)",
  color: "var(--aos-accent)",
  cursor: "pointer",
};
