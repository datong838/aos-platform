import { describe, it, expect } from "vitest";
import {
  nextState,
  canTransition,
  isTerminal,
  getStepIndex,
  shouldEnterNeedsCorrection,
  inferFileType,
  validateFile,
  formatFileSize,
  getConfidenceLevel,
  getConfidenceColor,
  getReviewTargetState,
  STATE_FLOW,
  STATE_META,
  TYPE_META,
  TEMPLATES,
  CONFIDENCE_THRESHOLD,
  ALLOWED_EXTENSIONS,
  pathLabel,
  normalizeExtractFields,
  DOCINTEL_PIPELINE_TEMPLATES,
  type DocState,
  type ExtractField,
} from "./DocumentIntelligencePage";

/* ================================================================
 *  1. 状态转换合法性
 * ================================================================ */
describe("DocumentIntelligencePage · 状态机 nextState", () => {
  it("uploaded → processing_ocr", () => {
    expect(nextState("uploaded")).toBe("processing_ocr");
  });

  it("processing_ocr → extracting", () => {
    expect(nextState("processing_ocr")).toBe("extracting");
  });

  it("extracting → review", () => {
    expect(nextState("extracting")).toBe("review");
  });

  it("review 为终态，nextState 返回自身", () => {
    expect(nextState("review")).toBe("review");
  });

  it("failed 为终态，nextState 返回自身", () => {
    expect(nextState("failed")).toBe("failed");
  });

  it("needs_correction 为终态，nextState 返回自身", () => {
    expect(nextState("needs_correction")).toBe("needs_correction");
  });

  it("STATE_FLOW 包含 4 个主流程状态", () => {
    expect(STATE_FLOW).toEqual(["uploaded", "processing_ocr", "extracting", "review"]);
  });
});

/* ================================================================
 *  2. canTransition 合法性判断
 * ================================================================ */
describe("DocumentIntelligencePage · canTransition", () => {
  it("主流程顺序流转合法", () => {
    expect(canTransition("uploaded", "processing_ocr")).toBe(true);
    expect(canTransition("processing_ocr", "extracting")).toBe(true);
    expect(canTransition("extracting", "review")).toBe(true);
  });

  it("跳步流转不合法（uploaded → extracting）", () => {
    expect(canTransition("uploaded", "extracting")).toBe(false);
  });

  it("反向流转不合法（review → extracting）", () => {
    expect(canTransition("review", "extracting")).toBe(false);
  });

  it("任意非终态 → failed 合法", () => {
    expect(canTransition("uploaded", "failed")).toBe(true);
    expect(canTransition("processing_ocr", "failed")).toBe(true);
    expect(canTransition("extracting", "failed")).toBe(true);
  });

  it("extracting → needs_correction 合法", () => {
    expect(canTransition("extracting", "needs_correction")).toBe(true);
  });

  it("needs_correction → extracting 合法（修正后重试）", () => {
    expect(canTransition("needs_correction", "extracting")).toBe(true);
  });

  it("needs_correction → review 合法（人工直接确认）", () => {
    expect(canTransition("needs_correction", "review")).toBe(true);
  });

  it("failed → uploaded 合法（重试从头上传）", () => {
    expect(canTransition("failed", "uploaded")).toBe(true);
  });

  it("相同状态返回 true", () => {
    expect(canTransition("uploaded", "uploaded")).toBe(true);
  });
});

/* ================================================================
 *  3. isTerminal 终态判断
 * ================================================================ */
describe("DocumentIntelligencePage · isTerminal", () => {
  it("review 是终态", () => {
    expect(isTerminal("review")).toBe(true);
  });

  it("failed 是终态", () => {
    expect(isTerminal("failed")).toBe(true);
  });

  it("uploaded 不是终态", () => {
    expect(isTerminal("uploaded")).toBe(false);
  });

  it("processing_ocr 不是终态", () => {
    expect(isTerminal("processing_ocr")).toBe(false);
  });
});

/* ================================================================
 *  4. getStepIndex 步骤索引
 * ================================================================ */
describe("DocumentIntelligencePage · getStepIndex", () => {
  it("uploaded → 索引 0", () => {
    expect(getStepIndex("uploaded")).toBe(0);
  });

  it("processing_ocr → 索引 1", () => {
    expect(getStepIndex("processing_ocr")).toBe(1);
  });

  it("extracting → 索引 2", () => {
    expect(getStepIndex("extracting")).toBe(2);
  });

  it("review → 索引 3", () => {
    expect(getStepIndex("review")).toBe(3);
  });

  it("needs_correction 映射到 extracting 阶段 → 索引 2", () => {
    expect(getStepIndex("needs_correction")).toBe(2);
  });
});

/* ================================================================
 *  5. needs_correction 流转（置信度判断）
 * ================================================================ */
describe("DocumentIntelligencePage · shouldEnterNeedsCorrection", () => {
  it("所有字段置信度 ≥ 阈值 → false", () => {
    const fields: ExtractField[] = [
      { id: "1", name: "A", type: "text", value: "v1", confidence: 0.95, source: "P1" },
      { id: "2", name: "B", type: "text", value: "v2", confidence: 0.88, source: "P2" },
    ];
    expect(shouldEnterNeedsCorrection(fields)).toBe(false);
  });

  it("存在字段置信度 < 阈值 → true", () => {
    const fields: ExtractField[] = [
      { id: "1", name: "A", type: "text", value: "v1", confidence: 0.95, source: "P1" },
      { id: "2", name: "B", type: "text", value: "v2", confidence: 0.65, source: "P2" },
    ];
    expect(shouldEnterNeedsCorrection(fields)).toBe(true);
  });

  it("空字段列表 → false", () => {
    expect(shouldEnterNeedsCorrection([])).toBe(false);
  });

  it("阈值边界值：正好等于阈值 → false", () => {
    const fields: ExtractField[] = [
      { id: "1", name: "A", type: "text", value: "v1", confidence: CONFIDENCE_THRESHOLD, source: "P1" },
    ];
    expect(shouldEnterNeedsCorrection(fields)).toBe(false);
  });
});

/* ================================================================
 *  6. 文件类型验证
 * ================================================================ */
describe("DocumentIntelligencePage · inferFileType", () => {
  it(".pdf → pdf", () => {
    expect(inferFileType("report.pdf")).toBe("pdf");
  });

  it(".docx → word", () => {
    expect(inferFileType("contract.docx")).toBe("word");
  });

  it(".doc → word", () => {
    expect(inferFileType("old.doc")).toBe("word");
  });

  it(".xlsx → excel", () => {
    expect(inferFileType("data.xlsx")).toBe("excel");
  });

  it(".jpg → image", () => {
    expect(inferFileType("scan.jpg")).toBe("image");
  });

  it(".png → image", () => {
    expect(inferFileType("photo.png")).toBe("image");
  });

  it(".pptx → ppt", () => {
    expect(inferFileType("slides.pptx")).toBe("ppt");
  });

  it("未知扩展名 → 默认 pdf", () => {
    expect(inferFileType("unknown.xyz")).toBe("pdf");
  });
});

describe("DocumentIntelligencePage · validateFile", () => {
  it("合法 PDF 文件 → null", () => {
    expect(validateFile("report.pdf", 1024)).toBeNull();
  });

  it("合法图片文件 → null", () => {
    expect(validateFile("scan.jpg", 2048 * 1024)).toBeNull();
  });

  it("不支持的扩展名 → 错误消息", () => {
    const err = validateFile("file.txt", 1024);
    expect(err).not.toBeNull();
    expect(err).toContain("不支持");
  });

  it("文件过大 → 错误消息", () => {
    const err = validateFile("big.pdf", 60 * 1024 * 1024);
    expect(err).not.toBeNull();
    expect(err).toContain("超过限制");
  });

  it("ALLOWED_EXTENSIONS 包含常见类型", () => {
    expect(ALLOWED_EXTENSIONS).toContain("pdf");
    expect(ALLOWED_EXTENSIONS).toContain("docx");
    expect(ALLOWED_EXTENSIONS).toContain("xlsx");
    expect(ALLOWED_EXTENSIONS).toContain("jpg");
    expect(ALLOWED_EXTENSIONS).toContain("png");
  });
});

/* ================================================================
 *  7. formatFileSize
 * ================================================================ */
describe("DocumentIntelligencePage · formatFileSize", () => {
  it("小于 1KB → 字节显示", () => {
    expect(formatFileSize(500)).toBe("500 B");
  });

  it("KB 级别", () => {
    expect(formatFileSize(2048)).toBe("2.0 KB");
  });

  it("MB 级别", () => {
    expect(formatFileSize(2 * 1024 * 1024)).toBe("2.0 MB");
  });
});

/* ================================================================
 *  8. 置信度
 * ================================================================ */
describe("DocumentIntelligencePage · getConfidenceLevel", () => {
  it("> 0.9 → high", () => {
    expect(getConfidenceLevel(0.95)).toBe("high");
    expect(getConfidenceLevel(0.91)).toBe("high");
  });

  it("0.7 ~ 0.9 → medium", () => {
    expect(getConfidenceLevel(0.7)).toBe("medium");
    expect(getConfidenceLevel(0.85)).toBe("medium");
    expect(getConfidenceLevel(0.9)).toBe("medium");
  });

  it("< 0.7 → low", () => {
    expect(getConfidenceLevel(0.69)).toBe("low");
    expect(getConfidenceLevel(0.5)).toBe("low");
  });
});

describe("DocumentIntelligencePage · getConfidenceColor", () => {
  it("high → 绿色 #10B981", () => {
    expect(getConfidenceColor(0.95)).toBe("#10B981");
  });

  it("medium → 橙色 #F59E0B", () => {
    expect(getConfidenceColor(0.8)).toBe("#F59E0B");
  });

  it("low → 红色 #EF4444", () => {
    expect(getConfidenceColor(0.6)).toBe("#EF4444");
  });
});

/* ================================================================
 *  9. 审批操作
 * ================================================================ */
describe("DocumentIntelligencePage · getReviewTargetState", () => {
  it("approve → review", () => {
    expect(getReviewTargetState("approve")).toBe("review");
  });

  it("reject → needs_correction", () => {
    expect(getReviewTargetState("reject")).toBe("needs_correction");
  });
});

/* ================================================================
 *  10. 提取模板渲染
 * ================================================================ */
describe("DocumentIntelligencePage · TEMPLATES", () => {
  it("至少包含 5 种模板", () => {
    expect(TEMPLATES.length).toBeGreaterThanOrEqual(5);
  });

  it("包含 invoice / contract / purchase_order / finance_report / custom", () => {
    const ids = TEMPLATES.map((t) => t.id);
    expect(ids).toContain("invoice");
    expect(ids).toContain("contract");
    expect(ids).toContain("purchase_order");
    expect(ids).toContain("finance_report");
    expect(ids).toContain("custom");
  });

  it("每个模板有 label 和至少 1 个字段", () => {
    for (const t of TEMPLATES) {
      expect(t.label.length).toBeGreaterThan(0);
      expect(t.fields.length).toBeGreaterThan(0);
    }
  });
});

/* ================================================================
 *  11. STATE_META 元数据
 * ================================================================ */
describe("DocumentIntelligencePage · STATE_META", () => {
  it("包含全部 6 个状态的元数据", () => {
    const states: DocState[] = ["uploaded", "processing_ocr", "extracting", "review", "failed", "needs_correction"];
    for (const s of states) {
      expect(STATE_META[s]).toBeDefined();
      expect(STATE_META[s].label.length).toBeGreaterThan(0);
      expect(STATE_META[s].color).toMatch(/^#/);
      expect(STATE_META[s].bg).toMatch(/^#/);
    }
  });

  it("uploaded 颜色为蓝色 #3B82F6", () => {
    expect(STATE_META.uploaded.color).toBe("#3B82F6");
  });

  it("processing_ocr 颜色为橙色 #F59E0B", () => {
    expect(STATE_META.processing_ocr.color).toBe("#F59E0B");
  });

  it("extracting 颜色为紫色 #8B5CF6", () => {
    expect(STATE_META.extracting.color).toBe("#8B5CF6");
  });

  it("review 颜色为绿色 #10B981", () => {
    expect(STATE_META.review.color).toBe("#10B981");
  });

  it("failed 颜色为红色 #EF4444", () => {
    expect(STATE_META.failed.color).toBe("#EF4444");
  });
});

/* ================================================================
 *  12. TYPE_META
 * ================================================================ */
describe("DocumentIntelligencePage · TYPE_META", () => {
  it("包含 5 种文件类型", () => {
    expect(Object.keys(TYPE_META)).toHaveLength(5);
    expect(TYPE_META.pdf).toBeDefined();
    expect(TYPE_META.word).toBeDefined();
    expect(TYPE_META.excel).toBeDefined();
    expect(TYPE_META.image).toBeDefined();
    expect(TYPE_META.ppt).toBeDefined();
  });
});

/* ================================================================
 *  13. W4-A8 / E1 纯函数
 * ================================================================ */
describe("DocumentIntelligencePage · W4 pathLabel / extract helpers", () => {
  it("pathLabel 映射 live/demo/loading/idle", () => {
    expect(pathLabel("live")).toBe("真 API");
    expect(pathLabel("demo")).toBe("演示路径");
    expect(pathLabel("loading")).toBe("加载中");
    expect(pathLabel("idle")).toBe("未运行");
  });

  it("normalizeExtractFields 过滤非法项并钳制置信度", () => {
    const fields = normalizeExtractFields([
      { id: "1", name: "公司", value: "A", confidence: 1.5 },
      null,
      { field: "别名", text: "B" },
    ]);
    expect(fields).toHaveLength(2);
    expect(fields[0].confidence).toBe(1);
    expect(fields[1].name).toBe("别名");
    expect(fields[1].value).toBe("B");
  });

  it("DOCINTEL_PIPELINE_TEMPLATES 含 6 个视觉稿模板", () => {
    expect(DOCINTEL_PIPELINE_TEMPLATES).toHaveLength(6);
    expect(DOCINTEL_PIPELINE_TEMPLATES.map((t) => t.id)).toContain("entity");
  });
});
