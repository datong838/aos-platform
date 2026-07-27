import { useState, useMemo, useCallback } from "react";
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
 *  Mock 数据
 * ========================================================================= */

const INITIAL_DOCS: DocItem[] = [
  {
    id: "d1",
    title: "2024年度财务报告.pdf",
    type: "pdf",
    size: 2_411_724,
    status: "review",
    uploadedAt: "2024-07-20 14:32",
    ocrText: "某某科技有限公司 2024 年度财务报告\n总收入：¥128,450,000\n净利润：¥45,230,000",
    history: [
      { state: "uploaded", timestamp: "2024-07-20 14:32", note: "文件上传成功" },
      { state: "processing_ocr", timestamp: "2024-07-20 14:33", note: "OCR 识别完成，置信度 96.8%" },
      { state: "extracting", timestamp: "2024-07-20 14:34", note: "LLM 结构化提取完成" },
      { state: "review", timestamp: "2024-07-20 14:35", note: "进入人工审核" },
    ],
  },
  {
    id: "d2",
    title: "合同模板-采购协议.docx",
    type: "word",
    size: 876_544,
    status: "review",
    uploadedAt: "2024-07-19 10:15",
  },
  {
    id: "d3",
    title: "供应商清单-2024Q3.xlsx",
    type: "excel",
    size: 1_258_291,
    status: "processing_ocr",
    uploadedAt: "2024-07-26 09:20",
    ocrProgress: 65,
  },
  {
    id: "d4",
    title: "发票扫描件-0821.jpg",
    type: "image",
    size: 3_984_576,
    status: "needs_correction",
    uploadedAt: "2024-07-22 16:48",
    errorMessage: "部分字段置信度低于阈值",
  },
  {
    id: "d5",
    title: "合同-甲方公司.pdf",
    type: "pdf",
    size: 1_887_436,
    status: "failed",
    uploadedAt: "2024-07-17 14:22",
    errorMessage: "OCR 识别失败：文件已加密",
  },
];

const MOCK_EXTRACT_FIELDS: ExtractField[] = [
  { id: "f1", name: "报告期间", type: "日期", value: "2024-01-01 ~ 2024-12-31", confidence: 0.98, source: "P1 L1" },
  { id: "f2", name: "公司名称", type: "文本", value: "某某科技有限公司", confidence: 0.95, source: "P1 L3" },
  { id: "f3", name: "总收入", type: "数字", value: "¥ 128,450,000", confidence: 0.92, source: "P3 L12" },
  { id: "f4", name: "净利润", type: "数字", value: "¥ 45,230,000", confidence: 0.89, source: "P3 L15" },
  { id: "f5", name: "总资产", type: "数字", value: "¥ 580,120,000", confidence: 0.86, source: "P4 L8" },
  { id: "f6", name: "负债率", type: "百分比", value: "42.3%", confidence: 0.65, source: "P4 L20" },
  { id: "f7", name: "审计意见", type: "分类", value: "无保留意见", confidence: 0.91, source: "P5 L3" },
  { id: "f8", name: "审计师", type: "文本", value: "普华永道", confidence: 0.94, source: "P5 L5" },
];

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
}: {
  fields: ExtractField[];
  onEditField: (id: string, value: string) => void;
  selectedTemplate: TemplateId;
  onTemplateChange: (id: TemplateId) => void;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  return (
    <div style={{ background: "var(--aos-surface)", border: "1px solid var(--aos-border)", borderRadius: 2, padding: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, color: "var(--aos-text)" }}>LLM 结构化提取结果</h3>
        <select
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
}: {
  fields: ExtractField[];
  doc: DocItem;
  onApprove: () => void;
  onReject: () => void;
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
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <button
          type="button"
          onClick={onApprove}
          style={{
            flex: 1,
            padding: "8px 12px",
            fontSize: 13,
            fontWeight: 500,
            borderRadius: 2,
            border: "1px solid var(--aos-green)",
            background: "var(--aos-green)",
            color: "var(--text-on-brand)",
            cursor: "pointer",
          }}
        >
          ✓ 确认入库（写入本体 Objects）
        </button>
        <button
          type="button"
          onClick={onReject}
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
  const [docs, setDocs] = useState<DocItem[]>(INITIAL_DOCS);
  const [selectedId, setSelectedId] = useState<string>("d1");
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateId>("finance_report");
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [extractFields, setExtractFields] = useState<ExtractField[]>(MOCK_EXTRACT_FIELDS);

  const selectedDoc = useMemo(() => docs.find((d) => d.id === selectedId) ?? docs[0], [docs, selectedId]);

  const handleFiles = useCallback((files: File[]) => {
    const newDocs: DocItem[] = files.map((f, i) => {
      const now = new Date().toISOString().replace("T", " ").slice(0, 16);
      return {
        id: `upload-${Date.now()}-${i}`,
        title: f.name,
        type: inferFileType(f.name),
        size: f.size,
        status: "uploaded",
        uploadedAt: now,
        history: [{ state: "uploaded", timestamp: now, note: `文件上传成功 (${formatFileSize(f.size)})` }],
      };
    });
    setDocs((prev) => [...newDocs, ...prev]);
    if (newDocs.length > 0) setSelectedId(newDocs[0].id);
  }, []);

  const handleEditField = useCallback((id: string, value: string) => {
    setExtractFields((prev) => prev.map((f) => (f.id === id ? { ...f, value, confidence: Math.max(f.confidence, 0.95) } : f)));
  }, []);

  const handleCorrectOcr = useCallback((text: string) => {
    setDocs((prev) => prev.map((d) => (d.id === selectedId ? { ...d, ocrText: text } : d)));
  }, [selectedId]);

  const handleApprove = useCallback(() => {
    setDocs((prev) =>
      prev.map((d) =>
        d.id === selectedId
          ? { ...d, status: "review", history: [...(d.history ?? []), { state: "review", timestamp: new Date().toISOString().replace("T", " ").slice(0, 16), note: "审核通过，已写入本体 Objects" }] }
          : d,
      ),
    );
  }, [selectedId]);

  const handleReject = useCallback(() => {
    setDocs((prev) =>
      prev.map((d) =>
        d.id === selectedId
          ? { ...d, status: "needs_correction", history: [...(d.history ?? []), { state: "needs_correction", timestamp: new Date().toISOString().replace("T", " ").slice(0, 16), note: "审核退回，需人工修正" }] }
          : d,
      ),
    );
  }, [selectedId]);

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

  const handleBatchDelete = useCallback(() => {
    setDocs((prev) => prev.filter((d) => !selectedIds.has(d.id)));
    setSelectedIds(new Set());
  }, [selectedIds]);

  const handleBatchReprocess = useCallback(() => {
    setDocs((prev) =>
      prev.map((d) =>
        selectedIds.has(d.id)
          ? { ...d, status: "uploaded", ocrProgress: 0, errorMessage: undefined }
          : d,
      ),
    );
  }, [selectedIds]);

  return (
    <PageChrome title="文档智能" lede="导入文档、配置提取模板，自动识别并结构化关键字段">
      {/* 顶部统计卡片 */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
        <StatCard value="1,284" label="文档总数" trend="12.5% 本周" trendUp />
        <StatCard value="98.2%" label="提取准确率" trend="2.1% 本月" trendUp />
        <StatCard value="24" label="处理中" trend="平均耗时 45s" />
        <StatCard value="156" label="提取模板" trend="12 个内置" />
      </div>

      {/* 拖拽上传区 */}
      <UploadDropZone onFiles={handleFiles} />

      {/* 批量操作栏 */}
      {selectedIds.size > 0 && (
        <div style={{ display: "flex", gap: 8, marginBottom: 12, padding: "8px 12px", background: "var(--aos-accent-light)", borderRadius: 2, alignItems: "center" }}>
          <span style={{ fontSize: 12, color: "var(--aos-accent)" }}>已选择 {selectedIds.size} 个文件</span>
          <button type="button" onClick={handleBatchReprocess} style={batchBtnStyle}>重新处理</button>
          <button type="button" onClick={handleBatchDelete} style={{ ...batchBtnStyle, color: "var(--aos-red)", borderColor: "var(--aos-red-border)" }}>删除</button>
        </div>
      )}

      {/* 状态步骤条 */}
      <StateStepper state={selectedDoc.status} errorMessage={selectedDoc.errorMessage} />

      {/* 主体：左文件列表 + 右提取面板 */}
      <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
        {/* 文件列表 */}
        <div style={{ flex: "0 0 400px" }}>
          {/* 全选 */}
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8, padding: "0 4px" }}>
            <input
              type="checkbox"
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
          <OcrPanel doc={selectedDoc} onCorrectText={handleCorrectOcr} />
          <ExtractionPanel
            fields={extractFields}
            onEditField={handleEditField}
            selectedTemplate={selectedTemplate}
            onTemplateChange={setSelectedTemplate}
          />
          <ReviewPanel fields={extractFields} doc={selectedDoc} onApprove={handleApprove} onReject={handleReject} />
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
