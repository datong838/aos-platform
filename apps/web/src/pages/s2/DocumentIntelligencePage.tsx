/**
 * 文档智能 · OCR + LLM 抽取
 *
 * Wave 3A：文件、抽取、修正、入库、删除、重处理全部以后端响应为准；失败不生成 MOCK。
 * W4-E1：pipeline-doc-intel 并入本页（不新建侧栏）；说明条 + 轻量管道试运行。
 */
import { useState, useMemo, useCallback, useEffect, useRef } from "react";
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
  sourceLabel: string;
  documentKind: string;
  sensitivity: string;
  retentionPolicy: string;
  templateRevision?: string;
  processingProgress: number;
  currentPage: number;
  totalPages: number;
  extractionConfidence?: number;
  usageUnits: number;
  processingAttempts: number;
  runEvidenceRef?: string;
  lineageRef?: string;
  receiptRef?: string;
  receiptRefs: string[];
  reviewStatus: string;
  reviewedBy?: string;
  reviewedAt?: string;
  downstreamRef?: string;
};

export type DocumentGovernanceInput = {
  sourceLabel: string;
  documentKind: string;
  sensitivity: "public" | "internal" | "restricted";
  retentionPolicy: "project_default" | "30_days" | "180_days" | "permanent";
};

export const DEFAULT_DOCUMENT_GOVERNANCE: DocumentGovernanceInput = {
  sourceLabel: "人工业务文档导入",
  documentKind: "business_document",
  sensitivity: "internal",
  retentionPolicy: "project_default",
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
  extracting: { label: "智能提取中", color: "#8B5CF6", bg: "#EDE9FE" },
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
  if (mode === "live") return "权威回包";
  if (mode === "loading") return "加载中";
  if (mode === "idle") return "未运行";
  return "非权威数据";
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
      source: String(o.source ?? `来源片段 ${i + 1}`),
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
  source_label?: string;
  document_kind?: string;
  sensitivity?: string;
  retention_policy?: string;
  template_revision?: string;
  processing_progress?: number;
  current_page?: number;
  total_pages?: number;
  extraction_confidence?: number | null;
  usage_units?: number;
  processing_attempts?: number;
  run_evidence_ref?: string;
  lineage_ref?: string;
  receipt_ref?: string;
  receipt_refs?: string[];
  review_status?: string;
  reviewed_by?: string;
  reviewed_at?: number | null;
  downstream_ref?: string;
  org_id?: string;
  project_id?: string;
  source_id?: string;
  template_id?: string;
  content_type?: string;
  parser?: string;
  updated_at?: number;
};

const API_DOCUMENT_KEYS = new Set([
  "id", "name", "source_id", "template_id", "file_type", "status", "extracted_fields",
  "size_bytes", "content_type", "content_sha256", "ocr_text", "parser", "error_message",
  "ontology_object_id", "history", "org_id", "project_id", "source_label", "document_kind",
  "sensitivity", "retention_policy", "template_revision", "processing_progress", "current_page",
  "total_pages", "extraction_confidence", "usage_units", "run_evidence_ref", "lineage_ref",
  "processing_attempts",
  "receipt_ref", "receipt_refs", "review_status", "reviewed_by", "reviewed_at", "downstream_ref",
  "created_at", "updated_at",
]);

export function parseApiDocument(value: unknown): ApiDocument {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("文档回包不是对象");
  const record = value as Record<string, unknown>;
  const unknown = Object.keys(record).filter((key) => !API_DOCUMENT_KEYS.has(key));
  if (unknown.length) throw new Error(`文档回包含未知字段：${unknown.join(", ")}`);
  for (const key of ["id", "name", "org_id", "project_id", "receipt_ref", "lineage_ref"] as const) {
    if (typeof record[key] !== "string" || !(record[key] as string).trim()) throw new Error(`文档回包缺少 ${key}`);
  }
  if (record.receipt_refs !== undefined && (!Array.isArray(record.receipt_refs) || record.receipt_refs.some((item) => typeof item !== "string"))) {
    throw new Error("文档回包 receipt_refs 非法");
  }
  return record as ApiDocument;
}

export type DocumentStats = {
  total: number;
  processing: number;
  average_confidence: number | null;
  template_count: number;
};

export type ManagedExtractionTemplate = {
  id: string;
  name: string;
  description: string;
  fields: Array<{ name?: string; label?: string }>;
  doc_type: string;
  revision: number;
  validation_rules: Array<{ field?: string; rule?: string }>;
  model_route: string;
  estimated_cost_units: number;
  approval_gate: string;
  active: boolean;
  change_note: string;
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
    sourceLabel: doc.source_label || "来源未标注",
    documentKind: doc.document_kind || "business_document",
    sensitivity: doc.sensitivity || "internal",
    retentionPolicy: doc.retention_policy || "project_default",
    templateRevision: doc.template_revision || undefined,
    processingProgress: Number(doc.processing_progress || 0),
    currentPage: Number(doc.current_page || 0),
    totalPages: Number(doc.total_pages || 0),
    extractionConfidence: typeof doc.extraction_confidence === "number" ? doc.extraction_confidence : undefined,
    usageUnits: Number(doc.usage_units || 0),
    processingAttempts: Number(doc.processing_attempts || 0),
    runEvidenceRef: doc.run_evidence_ref || undefined,
    lineageRef: doc.lineage_ref || undefined,
    receiptRef: doc.receipt_ref || undefined,
    receiptRefs: doc.receipt_refs || [],
    reviewStatus: doc.review_status || "pending",
    reviewedBy: doc.reviewed_by || undefined,
    reviewedAt: doc.reviewed_at == null ? undefined : formatTimestamp(doc.reviewed_at),
    downstreamRef: doc.downstream_ref || undefined,
  };
}

export function requireMatchingDocument(
  document: unknown,
  expectedId: string,
  operation: string,
): ApiDocument {
  const parsed = parseApiDocument(document);
  if (parsed.id !== expectedId) {
    throw new Error(`${operation}响应文档错配：期望 ${expectedId}，实际 ${parsed.id}`);
  }
  return parsed;
}

export async function uploadDocumentFile(
  file: File,
  fetchImpl: typeof fetch = fetch,
  governance: DocumentGovernanceInput = DEFAULT_DOCUMENT_GOVERNANCE,
): Promise<ApiDocument> {
  const params = new URLSearchParams({
    name: file.name,
    source_label: governance.sourceLabel,
    document_kind: governance.documentKind,
    sensitivity: governance.sensitivity,
    retention_policy: governance.retentionPolicy,
  });
  const path = `/api/datasource/documents/upload?${params.toString()}`;
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
  return parseApiDocument(await response.json());
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
    { key: "extracting", title: "智能提取" },
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
  const inputRef = useRef<HTMLInputElement>(null);

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
      role="button"
      tabIndex={0}
      aria-label="选择待导入文档"
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
      onClick={() => inputRef.current?.click()}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          inputRef.current?.click();
        }
      }}
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
        ref={inputRef}
        id="doc-file-input"
        aria-label="选择待导入文档"
        type="file"
        multiple
        style={{ display: "none" }}
        accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.ppt,.pptx"
        onChange={(e) => {
          handleFiles(e.target.files);
          e.target.value = "";
        }}
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
        <div style={{ flex: "0 0 230px", minHeight: 240, padding: 12, background: "var(--aos-surface-hover)", border: "1px solid var(--aos-border)", borderRadius: 4 }}>
          <strong style={{ display: "block", fontSize: 12, marginBottom: 8 }}>原文对照 · 服务端解析</strong>
          <div style={{ fontSize: 11, color: "var(--aos-text-secondary)", marginBottom: 8 }}>
            {doc.totalPages > 0 ? `第 ${doc.currentPage || 1}/${doc.totalPages} 页` : "页码以服务端回包为准"}
          </div>
          <pre style={{ whiteSpace: "pre-wrap", maxHeight: 190, overflow: "auto", fontSize: 11, lineHeight: 1.55, margin: 0 }}>
            {doc.ocrText || "服务端尚未返回可对照原文"}
          </pre>
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
          <div style={{ marginTop: 8, fontSize: 11, color: "var(--aos-text-tertiary)" }}>人工校正只在服务端确认保存后生效。</div>
        </div>
      </div>
    </div>
  );
}

function DocumentGovernancePanel({ doc }: { doc: DocItem }) {
  const confidence = doc.extractionConfidence == null ? "尚无" : `${(doc.extractionConfidence * 100).toFixed(1)}%`;
  return <section data-testid="document-governance-panel" style={{ border: "1px solid var(--aos-border)", background: "var(--aos-surface)", padding: 12, marginBottom: 12 }}>
    <strong style={{ display: "block", marginBottom: 8 }}>来源、治理与运行证据</strong>
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 8, fontSize: 12 }}>
      <span>来源：{doc.sourceLabel}</span><span>文档类型：{doc.documentKind}</span><span>敏感级别：{doc.sensitivity}</span><span>保留策略：{doc.retentionPolicy}</span>
      <span>模板版本：{doc.templateRevision || "尚未抽取"}</span><span>处理进度：{doc.processingProgress}%</span><span>页码：{doc.totalPages ? `${doc.currentPage}/${doc.totalPages}` : "尚无"}</span><span>最低置信度：{confidence}</span><span>安全处理次数：{doc.processingAttempts}</span>
      <span>用量：{doc.usageUnits ? `${doc.usageUnits} 字符` : "尚无"}</span><span>上传/抽取 Receipt：{doc.receiptRef ? "已取得" : "尚未取得"}</span><span>谱系：{doc.lineageRef ? "已取得" : "尚未取得"}</span><span>运行证据：{doc.runEvidenceRef ? "已取得" : "尚未抽取"}</span>
      <span>复核状态：{doc.reviewStatus}</span><span>复核人：{doc.reviewedBy || "尚未复核"}</span><span>复核时间：{doc.reviewedAt || "尚未复核"}</span><span>下游交付：{doc.downstreamRef || "尚未交付"}</span>
    </div>
    <details style={{ marginTop: 8, fontSize: 11 }}><summary>技术标识（审计用）</summary><pre style={{ whiteSpace: "pre-wrap" }}>{[doc.receiptRef, doc.lineageRef, doc.runEvidenceRef].filter(Boolean).join("\n") || "暂无"}</pre></details>
  </section>;
}

function TemplateGovernancePanel({
  templates,
  busy,
  onCreate,
  onRevise,
  onCompare,
  onRollback,
}: {
  templates: ManagedExtractionTemplate[];
  busy: boolean;
  onCreate: () => void;
  onRevise: (template: ManagedExtractionTemplate) => void;
  onCompare: (template: ManagedExtractionTemplate) => void;
  onRollback: (template: ManagedExtractionTemplate) => void;
}) {
  return (
    <section data-testid="template-governance-panel" style={{ border: "1px solid var(--aos-border)", background: "var(--aos-surface)", padding: 14, marginBottom: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", marginBottom: 10 }}>
        <div><strong>提取模板治理</strong><div style={{ fontSize: 12, color: "var(--aos-text-secondary)", marginTop: 3 }}>模板字段、校验、模型路由、成本与审批门均由当前租户服务端版本控制。</div></div>
        <button type="button" disabled={busy} onClick={onCreate} style={batchBtnStyle}>新建合同模板</button>
      </div>
      {templates.length === 0 ? (
        <div style={{ padding: 12, border: "1px dashed var(--aos-border)", color: "var(--aos-text-secondary)", fontSize: 13 }}>当前租户尚无自定义模板；可新建模板，不会注入示例文档。</div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(290px, 1fr))", gap: 10 }}>
          {templates.map((template) => (
            <article key={template.id} data-testid={`managed-template-${template.id}`} style={{ border: "1px solid var(--aos-border)", padding: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}><strong>{template.name}</strong><span>v{template.revision}</span></div>
              <p style={{ margin: "8px 0", fontSize: 13 }}>{template.description || "无说明"}</p>
              <div style={{ fontSize: 12, color: "var(--aos-text-secondary)", lineHeight: 1.8 }}>
                <div>中文字段：{(template.fields || []).map((field) => field.label || field.name).filter(Boolean).join("、") || "未配置"}</div>
                <div>校验：{(template.validation_rules || []).map((rule) => `${rule.field || "字段"} ${rule.rule || "规则"}`).join("；") || "未配置"}</div>
                <div>模型路由：{template.model_route} · 预计成本 {template.estimated_cost_units} 单位</div>
                <div>审批门：{template.approval_gate} · 变更：{template.change_note}</div>
              </div>
              <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
                <button type="button" disabled={busy} onClick={() => onRevise(template)} style={batchBtnStyle}>保存新版本</button>
                <button type="button" disabled={busy} onClick={() => onCompare(template)} style={batchBtnStyle}>比较版本</button>
                <button type="button" disabled={busy || template.revision <= 1} onClick={() => onRollback(template)} style={batchBtnStyle}>回滚到 v1</button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
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
          <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--aos-text)", margin: 0 }}>结构化提取结果</h3>
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
  const exportFields = () => {
    const blob = new Blob([JSON.stringify({ document: doc.title, receiptRef: doc.receiptRef, lineageRef: doc.lineageRef, fields }, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${doc.title.replace(/\.[^.]+$/, "")}-提取结果.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

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
        写入目标本体对象类型
        <select
          aria-label="写入目标本体对象类型"
          data-testid="ontology-type-select"
          value={objectTypeId}
          onChange={(event) => onObjectTypeChange(event.target.value)}
          style={{ display: "block", width: "100%", marginTop: 4, padding: "6px 8px" }}
        >
          <option value="">请选择当前已有的本体对象类型</option>
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

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }} aria-label="结果交付">
        <button type="button" onClick={exportFields} disabled={!doc.receiptRef || fields.length === 0} data-testid="document-export-btn" style={batchBtnStyle}>导出审核结果</button>
        <a className="btn" data-testid="document-task-handoff" aria-disabled={!doc.receiptRef} href={doc.receiptRef ? `/aip/assist?documentId=${encodeURIComponent(doc.id)}&lineageRef=${encodeURIComponent(doc.lineageRef || "")}` : undefined}>交付任务协作</a>
        <a className="btn" data-testid="document-logic-handoff" aria-disabled={!doc.receiptRef} href={doc.receiptRef ? `/aip/logic?documentId=${encodeURIComponent(doc.id)}&lineageRef=${encodeURIComponent(doc.lineageRef || "")}` : undefined}>交付业务逻辑</a>
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
  const requestedDocumentId = useMemo(() => new URLSearchParams(window.location.search).get("documentId")?.trim() || "", []);
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
  const [governance, setGovernance] = useState<DocumentGovernanceInput>(DEFAULT_DOCUMENT_GOVERNANCE);
  const [managedTemplates, setManagedTemplates] = useState<ManagedExtractionTemplate[]>([]);

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
        const [documents, currentStats, templateCatalog] = await Promise.all([
          apiGet<{ items: ApiDocument[]; total: number }>("/api/datasource/documents?page=1&page_size=100"),
          apiGet<DocumentStats>("/api/datasource/documents/stats"),
          apiGet<{ items: ManagedExtractionTemplate[] }>("/api/datasource/extraction-templates"),
        ]);
        if (cancelled) return;
        const mapped = documents.items.map((item) => mapApiDocument(parseApiDocument(item)));
        setDocs(mapped);
        setStats(currentStats);
        setManagedTemplates((templateCatalog.items || []).filter((item) => (
          typeof item.id === "string" && typeof item.name === "string" && typeof item.revision === "number"
        )));
        const requestedDocument = requestedDocumentId ? mapped.find((item) => item.id === requestedDocumentId) : undefined;
        if (requestedDocument) setSelectedId(requestedDocument.id);
        else if (mapped[0]) setSelectedId(mapped[0].id);
        if (requestedDocumentId && !requestedDocument) setStatusMsg("交付文档在当前租户中不存在或不可见；未切换到其他租户数据。");
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
  }, [requestedDocumentId]);

  const createManagedTemplate = useCallback(async () => {
    setActionBusy(true);
    try {
      const created = await apiPost<ManagedExtractionTemplate>("/api/datasource/extraction-templates", {
        name: "供应商合同字段模板",
        description: "提取合同主体、合同金额、有效期和续签日",
        doc_type: "supplier_contract",
        fields: [
          { name: "party_a", label: "甲方" },
          { name: "party_b", label: "乙方" },
          { name: "contract_amount", label: "合同金额" },
          { name: "effective_period", label: "有效期" },
          { name: "renewal_date", label: "续签日" },
        ],
        validation_rules: [{ field: "合同金额", rule: "required" }, { field: "有效期", rule: "required" }],
        model_route: "deterministic_document_parser",
        estimated_cost_units: 2,
        approval_gate: "manual_review",
      });
      setManagedTemplates((current) => [...current, created]);
      await reportWriteSuccess(`模板已保存 · ${created.name} v${created.revision}`);
    } catch (error) {
      setStatusMsg(`模板保存失败，未生成本地替代：${String((error as Error).message || error)}`);
    } finally {
      setActionBusy(false);
    }
  }, [reportWriteSuccess]);

  const reviseManagedTemplate = useCallback(async (template: ManagedExtractionTemplate) => {
    setActionBusy(true);
    try {
      const updated = await apiPut<ManagedExtractionTemplate>(`/api/datasource/extraction-templates/${encodeURIComponent(template.id)}`, {
        expected_revision: template.revision,
        description: `${template.description.replace(/（第 \d+ 次修订）$/, "")}（第 ${template.revision} 次修订）`,
        change_note: "人工保存新版本",
      });
      setManagedTemplates((current) => current.map((item) => item.id === updated.id ? updated : item));
      setStatusMsg(`模板新版本已保存 · ${updated.name} v${updated.revision}`);
    } catch (error) {
      setStatusMsg(`模板保存失败：${String((error as Error).message || error)}`);
    } finally {
      setActionBusy(false);
    }
  }, []);

  const rollbackManagedTemplate = useCallback(async (template: ManagedExtractionTemplate) => {
    setActionBusy(true);
    try {
      const updated = await apiPost<ManagedExtractionTemplate>(`/api/datasource/extraction-templates/${encodeURIComponent(template.id)}/rollback`, {
        expected_revision: template.revision,
        target_revision: 1,
      });
      setManagedTemplates((current) => current.map((item) => item.id === updated.id ? updated : item));
      setStatusMsg(`模板已回滚并生成审计版本 · ${updated.name} v${updated.revision}`);
    } catch (error) {
      setStatusMsg(`模板回滚失败：${String((error as Error).message || error)}`);
    } finally {
      setActionBusy(false);
    }
  }, []);

  const compareManagedTemplate = useCallback(async (template: ManagedExtractionTemplate) => {
    setActionBusy(true);
    try {
      const response = await apiGet<{ items: ManagedExtractionTemplate[] }>(`/api/datasource/extraction-templates/${encodeURIComponent(template.id)}/versions`);
      const versions = response.items || [];
      if (!versions.length) throw new Error("服务端未返回模板历史版本");
      const first = versions[0];
      const latest = versions[versions.length - 1];
      const firstFields = (first.fields || []).map((field) => field.label || field.name).filter(Boolean);
      const latestFields = (latest.fields || []).map((field) => field.label || field.name).filter(Boolean);
      const added = latestFields.filter((field) => !firstFields.includes(field));
      const removed = firstFields.filter((field) => !latestFields.includes(field));
      setStatusMsg(`版本比较 v${first.revision} → v${latest.revision} · 新增字段 ${added.join("、") || "无"} · 移除字段 ${removed.join("、") || "无"} · 共 ${versions.length} 个审计版本`);
    } catch (error) {
      setStatusMsg(`模板版本比较失败：${String((error as Error).message || error)}`);
    } finally {
      setActionBusy(false);
    }
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
      await reportWriteSuccess(`抽取完成 · 权威回包 · ${mapped.extractedFields?.length || 0} 字段`);
    } catch (e) {
      setDataMode(doc.extractedFields?.length ? "live" : "idle");
      setStatusMsg(`抽取失败，未生成演示结果：${String((e as Error).message || e)}`);
    } finally {
      setExtractRunning(false);
    }
  }, [docs, selectedId, selectedTemplate, replaceDocument, reportWriteSuccess]);

  const runPipelineTrial = useCallback(async () => {
    const doc = docs.find((d) => d.id === selectedId) ?? docs[0];
    if (!doc) {
      setStatusMsg("请先上传并选择文档后再试运行");
      return;
    }
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
      const templateLabel = DOCINTEL_PIPELINE_TEMPLATES.find((template) => template.id === pipelineTpl)?.label || pipelineTpl;
      setStatusMsg(`管道试运行成功 · 权威回包 · ${templateLabel}`);
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
      const results = await Promise.allSettled(files.map((file) => uploadDocumentFile(file, fetch, governance)));
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
  }, [governance, reportWriteSuccess]);

  const handleEditField = useCallback(async (id: string, value: string) => {
    if (!selectedDoc) return;
    const next = extractFields.map((field) => field.id === id ? { ...field, value, confidence: Math.max(field.confidence, 0.95) } : field);
    setActionBusy(true);
    try {
      const res = await apiPut<ApiDocument>(`/api/datasource/documents/${encodeURIComponent(selectedDoc.id)}`, { extracted_fields: next });
      replaceDocument(requireMatchingDocument(res, selectedDoc.id, "字段保存"));
      await reportWriteSuccess("字段修正已保存 · 权威回包");
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
      await reportWriteSuccess("文字识别校正已保存 · 权威回包");
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
      await reportWriteSuccess("本体写入成功 · 已生成业务对象");
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
      await reportWriteSuccess("已退回修正 · 权威回包");
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
        const parsed = current.items.map(parseApiDocument);
        const currentIds = new Set(parsed.map((doc) => doc.id));
        deleted = new Set(ids.filter((id) => deletedByResponse.has(id) || !currentIds.has(id)));
        setDocs(parsed.filter((doc) => !deleted.has(doc.id)).map(mapApiDocument));
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
      {/* 文档处理能力说明 */}
      <div className="w4-e1-notice" data-testid="docintel-merge-notice">
        <strong>文档处理能力统一在此页完成</strong>
        <span>导入、文字识别、结构化提取、审核与试运行使用同一份当前租户文档。</span>
      </div>

      {/* E1：轻量管道能力条 */}
      <div className="w4-e1-pipeline-strip" data-testid="docintel-pipeline-strip">
        <div className="w4-e1-pipeline-nodes" aria-label="文档处理流程">
          <span className="w4-e1-node">输入</span>
          <span className="w4-e1-arrow">→</span>
          <span className="w4-e1-node is-llm">智能识别</span>
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
        <StatCard value={String(stats.total)} label="文档总数" trend="来自当前文档服务" />
        <StatCard value={stats.average_confidence == null ? "—" : `${(stats.average_confidence * 100).toFixed(1)}%`} label="平均提取置信度" trend="按后端提取字段计算" />
        <StatCard value={String(stats.processing)} label="处理中" trend="按后端状态计算" />
        <StatCard value={String(stats.template_count)} label="提取模板" trend="来自当前模板服务" />
      </div>

      <TemplateGovernancePanel
        templates={managedTemplates}
        busy={actionBusy}
        onCreate={() => void createManagedTemplate()}
        onRevise={(template) => void reviseManagedTemplate(template)}
        onCompare={(template) => void compareManagedTemplate(template)}
        onRollback={(template) => void rollbackManagedTemplate(template)}
      />

      {/* 拖拽上传区 */}
      <section data-testid="document-import-governance" style={{ display: "grid", gridTemplateColumns: "2fr 1fr 1fr 1fr", gap: 10, padding: 12, marginBottom: 12, border: "1px solid var(--aos-border)", background: "var(--aos-surface)" }}>
        <label style={{ fontSize: 12 }}>业务来源<input aria-label="业务来源" value={governance.sourceLabel} onChange={(event) => setGovernance((current) => ({ ...current, sourceLabel: event.target.value }))} style={{ display: "block", width: "100%", marginTop: 4, padding: 7 }} /></label>
        <label style={{ fontSize: 12 }}>文档类型<select aria-label="业务文档类型" value={governance.documentKind} onChange={(event) => setGovernance((current) => ({ ...current, documentKind: event.target.value }))} style={{ display: "block", width: "100%", marginTop: 4, padding: 7 }}><option value="business_document">通用业务文档</option><option value="supplier_contract">供应商合同</option><option value="invoice">发票</option><option value="finance_report">经营报告</option><option value="purchase_order">采购单</option></select></label>
        <label style={{ fontSize: 12 }}>敏感级别<select aria-label="敏感级别" value={governance.sensitivity} onChange={(event) => setGovernance((current) => ({ ...current, sensitivity: event.target.value as DocumentGovernanceInput["sensitivity"] }))} style={{ display: "block", width: "100%", marginTop: 4, padding: 7 }}><option value="public">公开</option><option value="internal">内部</option><option value="restricted">受限</option></select></label>
        <label style={{ fontSize: 12 }}>保留策略<select aria-label="保留策略" value={governance.retentionPolicy} onChange={(event) => setGovernance((current) => ({ ...current, retentionPolicy: event.target.value as DocumentGovernanceInput["retentionPolicy"] }))} style={{ display: "block", width: "100%", marginTop: 4, padding: 7 }}><option value="project_default">项目默认</option><option value="30_days">30 天</option><option value="180_days">180 天</option><option value="permanent">长期保留</option></select></label>
      </section>
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
      {selectedDoc ? <DocumentGovernancePanel doc={selectedDoc} /> : null}

      {/* 主体：左文件列表 + 右提取面板 */}
      <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
        {/* 文件列表 */}
        <div style={{ flex: "0 0 400px" }}>
          {/* 全选 */}
          {docs.length > 0 ? <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, padding: "0 4px" }}>
            <input
              type="checkbox"
              aria-label="选择全部文档"
              checked={selectedIds.size === docs.length && docs.length > 0}
              onChange={toggleSelectAll}
              style={{ cursor: "pointer" }}
            />
            <span style={{ fontSize: 12, color: "var(--aos-text-secondary)" }}>全选 ({docs.length})</span>
          </div> : null}

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
          {selectedDoc ? <DocumentGovernancePanel doc={selectedDoc} /> : null}
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
