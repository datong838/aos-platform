import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { S2Chrome } from "./shared";
import { BpBanner, BpToolbar } from "./blueprintUi";
import { MOCK_VERSIONS } from "./WikiDetailPage";

/* ────────────── Types ────────────── */

export type DiffViewMode = "side" | "inline" | "unified";
export type DiffLineType = "same" | "add" | "del" | "mod";

export interface DiffLine {
  type: DiffLineType;
  leftNum: number | null;
  rightNum: number | null;
  leftContent?: string;
  rightContent?: string;
}

export interface DiffSummary {
  added: number;
  deleted: number;
  modified: number;
  total: number;
}

export interface WikiVersionContent {
  version: number;
  label: string;
  author: string;
  timestamp: string;
  content: string;
  commitMessage: string;
}

/* ────────────── Constants ────────────── */

export const MOCK_VERSION_CONTENTS: WikiVersionContent[] = [
  {
    version: 9,
    label: "v9 (当前)",
    author: "大同",
    timestamp: "2026-07-25T16:42:00Z",
    commitMessage: "新增跨境发货因子和新客首单判定",
    content: [
      "# 订单风险分诊规范",
      "",
      "## 风险等级定义",
      "- **low**：金额 < $100，无异常因子",
      "- **medium**：金额 $100~$500，1 个风险因子",
      "  或跨境发货 + 新客首单",
      "- **high**：金额 > $500，2+ 风险因子",
      "- **critical**：金额 > $2000 或疑似欺诈",
      "",
      "## 风险因子清单",
      "1. 金额超过阈值（$500）",
      "2. 频繁退款的会员（>3次/月）",
      "3. 跨境发货（东南亚/中东/非洲）",
      "4. 新客首单（注册 < 7 天）",
      "",
      "## LLM 提示词",
      "你是订单风险评估助手。分析订单风险等级",
      "（low/medium/high/critical）。",
      "高风险因子：金额 > $500、跨境发货、",
      "新客首单、频繁退款的会员。",
      "",
      "## 升级流程",
      "high → 通知主管",
      "critical → 冻结订单 + 安全团队介入",
    ].join("\n"),
  },
  {
    version: 8,
    label: "v8",
    author: "风控组",
    timestamp: "2026-07-24T14:30:00Z",
    commitMessage: "调整 medium 等级阈值从 $200 到 $100",
    content: [
      "# 订单风险分诊规范",
      "",
      "## 风险等级定义",
      "- **low**：金额 < $100，无异常因子",
      "- **medium**：金额 $100~$500，1 个风险因子",
      "- **high**：金额 > $500，2+ 风险因子",
      "- **critical**：金额 > $2000 或疑似欺诈",
      "",
      "## 风险因子清单",
      "1. 金额超过阈值（$500）",
      "2. 频繁退款的会员（>3次/月）",
      "",
      "## LLM 提示词",
      "你是订单风险评估助手。分析订单风险等级。",
      "高风险因子：金额 > $500、频繁退款。",
      "",
      "## 升级流程",
      "high → 通知主管",
      "critical → 冻结订单 + 安全团队介入",
    ].join("\n"),
  },
  {
    version: 7,
    label: "v7",
    author: "大同",
    timestamp: "2026-07-22T10:00:00Z",
    commitMessage: "补充 critical 级别的安全团队介入流程",
    content: [
      "# 订单风险分诊规范",
      "",
      "## 风险等级定义",
      "- **low**：金额 < $200",
      "- **medium**：金额 $200~$500",
      "- **high**：金额 > $500",
      "",
      "## 风险因子清单",
      "1. 金额超过阈值",
      "",
      "## 升级流程",
      "high → 通知主管",
      "critical → 冻结订单 + 安全团队介入",
    ].join("\n"),
  },
];

/* ────────────── Pure functions ────────────── */

/** Compute a simple line-based diff using LCS algorithm. */
export function computeDiff(oldText: string, newText: string): DiffLine[] {
  const oldLines = oldText.split("\n");
  const newLines = newText.split("\n");
  const m = oldLines.length;
  const n = newLines.length;

  // LCS table
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      if (oldLines[i] === newLines[j]) {
        dp[i][j] = dp[i + 1][j + 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
      }
    }
  }

  // Backtrack to build diff
  const result: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < m && j < n) {
    if (oldLines[i] === newLines[j]) {
      result.push({ type: "same", leftNum: i + 1, rightNum: j + 1, leftContent: oldLines[i], rightContent: newLines[j] });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      result.push({ type: "del", leftNum: i + 1, rightNum: null, leftContent: oldLines[i] });
      i++;
    } else {
      result.push({ type: "add", leftNum: null, rightNum: j + 1, rightContent: newLines[j] });
      j++;
    }
  }
  while (i < m) {
    result.push({ type: "del", leftNum: i + 1, rightNum: null, leftContent: oldLines[i] });
    i++;
  }
  while (j < n) {
    result.push({ type: "add", leftNum: null, rightNum: j + 1, rightContent: newLines[j] });
    j++;
  }

  // Mark consecutive del+add pairs as "mod" (in-place modifications)
  for (let k = 0; k < result.length - 1; k++) {
    if (result[k].type === "del" && result[k + 1].type === "add") {
      result[k] = { ...result[k], type: "mod", rightNum: result[k + 1].rightNum, rightContent: result[k + 1].rightContent };
      result[k + 1] = { ...result[k + 1], type: "mod", leftNum: result[k].leftNum, leftContent: result[k].leftContent };
    }
  }

  return result;
}

export function summarizeDiff(lines: DiffLine[]): DiffSummary {
  let added = 0;
  let deleted = 0;
  let modified = 0;
  const modSeen = new Set<number>();
  for (const line of lines) {
    if (line.type === "add") added++;
    else if (line.type === "del") deleted++;
    else if (line.type === "mod" && !modSeen.has(line.leftNum ?? -1)) {
      modified++;
      modSeen.add(line.leftNum ?? -1);
    }
  }
  return { added, deleted, modified, total: added + deleted + modified };
}

export function diffLineTypeColor(type: DiffLineType): string {
  return { same: "#9CA3AF", add: "#22C55E", del: "#EF4444", mod: "#F59E0B" }[type];
}

export function diffLineTypeBg(type: DiffLineType): string {
  return {
    same: "transparent",
    add: "var(--aos-green-bg)",
    del: "var(--aos-red-bg)",
    mod: "var(--aos-amber-bg)",
  }[type];
}

export function diffLineTypeLabel(type: DiffLineType): string {
  return { same: " ", add: "+", del: "-", mod: "~" }[type];
}

export function filterDiffLines(lines: DiffLine[], showSame: boolean): DiffLine[] {
  return showSame ? lines : lines.filter((l) => l.type !== "same");
}

export function inlineDiff(lines: DiffLine[]): { type: DiffLineType; content: string; lineNum: number | null }[] {
  const result: { type: DiffLineType; content: string; lineNum: number | null }[] = [];
  for (const line of lines) {
    if (line.type === "same") {
      result.push({ type: "same", content: line.leftContent ?? "", lineNum: line.leftNum });
    } else if (line.type === "del") {
      result.push({ type: "del", content: line.leftContent ?? "", lineNum: line.leftNum });
    } else if (line.type === "add") {
      result.push({ type: "add", content: line.rightContent ?? "", lineNum: line.rightNum });
    } else {
      result.push({ type: "del", content: line.leftContent ?? "", lineNum: line.leftNum });
      result.push({ type: "add", content: line.rightContent ?? "", lineNum: line.rightNum });
    }
  }
  return result;
}

/* ────────────── Component ────────────── */

export function WikiDiffPage() {
  const { wikiId = "wiki-covid-homepage" } = useParams();
  const [leftVersion, setLeftVersion] = useState(8);
  const [rightVersion, setRightVersion] = useState(9);
  const [viewMode, setViewMode] = useState<DiffViewMode>("side");
  const [showSame, setShowSame] = useState(true);
  const [showRestoreModal, setShowRestoreModal] = useState(false);
  const [restoreMsg, setRestoreMsg] = useState("");

  const leftContent = useMemo(
    () => MOCK_VERSION_CONTENTS.find((v) => v.version === leftVersion) ?? MOCK_VERSION_CONTENTS[0],
    [leftVersion],
  );
  const rightContent = useMemo(
    () => MOCK_VERSION_CONTENTS.find((v) => v.version === rightVersion) ?? MOCK_VERSION_CONTENTS[0],
    [rightVersion],
  );

  const diffLines = useMemo(
    () => computeDiff(leftContent.content, rightContent.content),
    [leftContent, rightContent],
  );
  const summary = useMemo(() => summarizeDiff(diffLines), [diffLines]);
  const filtered = useMemo(() => filterDiffLines(diffLines, showSame), [diffLines, showSame]);

  function confirmRestore() {
    setShowRestoreModal(false);
    setRestoreMsg(`已恢复到 v${leftVersion}`);
  }

  const leftOnly = useMemo(
    () => filtered.filter((l) => l.type === "del" || l.type === "same" || l.type === "mod"),
    [filtered],
  );
  const rightOnly = useMemo(
    () => filtered.filter((l) => l.type === "add" || l.type === "same" || l.type === "mod"),
    [filtered],
  );

  return (
    <S2Chrome title="版本对比" lede={`${wikiId} · main 分支`}>
      <div className="ont-page">
        <BpToolbar>
          <Link to={`/ontology/wiki/${encodeURIComponent(wikiId)}`} className="btn-nav">
            ← 返回编辑
          </Link>
          <button
            type="button"
            className="btn-primary"
            onClick={() => setShowRestoreModal(true)}
          >
            恢复到 v{leftVersion}
          </button>
        </BpToolbar>

        {restoreMsg && <p className="bp-prop-ok">{restoreMsg}</p>}

        {/* 版本选择器 + 视图切换 */}
        <div style={styles.selectorBar}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <select
              className="aos-input"
              style={styles.versionSelect}
              value={leftVersion}
              onChange={(e) => setLeftVersion(Number(e.target.value))}
            >
              {MOCK_VERSION_CONTENTS.map((v) => (
                <option key={v.version} value={v.version}>
                  {v.label}
                </option>
              ))}
            </select>
            <span style={{ color: "var(--aos-text-tertiary)", fontSize: "0.75rem" }}>vs</span>
            <select
              className="aos-input"
              style={styles.versionSelect}
              value={rightVersion}
              onChange={(e) => setRightVersion(Number(e.target.value))}
            >
              {MOCK_VERSION_CONTENTS.map((v) => (
                <option key={v.version} value={v.version}>
                  {v.label}
                </option>
              ))}
            </select>
          </div>
          <div style={styles.viewModeSwitch}>
            {(["side", "inline", "unified"] as DiffViewMode[]).map((vm) => (
              <button
                key={vm}
                type="button"
                style={viewMode === vm ? styles.viewModeActive : styles.viewModeBtn}
                onClick={() => setViewMode(vm)}
              >
                {vm === "side" ? "并排" : vm === "inline" ? "行内" : "统一"}
              </button>
            ))}
          </div>
        </div>

        {/* 变更摘要 */}
        <div style={styles.summaryBar}>
          <div style={styles.summaryItem}>
            <div style={{ ...styles.summaryDot, background: "#22C55E" }} />
            <span style={{ fontSize: "0.7rem", color: "var(--aos-text-secondary)" }}>
              新增 <strong style={{ color: "#22C55E" }}>{summary.added}</strong>
            </span>
          </div>
          <div style={styles.summaryItem}>
            <div style={{ ...styles.summaryDot, background: "#EF4444" }} />
            <span style={{ fontSize: "0.7rem", color: "var(--aos-text-secondary)" }}>
              删除 <strong style={{ color: "#EF4444" }}>{summary.deleted}</strong>
            </span>
          </div>
          <div style={styles.summaryItem}>
            <div style={{ ...styles.summaryDot, background: "#F59E0B" }} />
            <span style={{ fontSize: "0.7rem", color: "var(--aos-text-secondary)" }}>
              修改 <strong style={{ color: "#F59E0B" }}>{summary.modified}</strong>
            </span>
          </div>
          <div style={{ marginLeft: "auto", fontSize: "0.7rem", color: "var(--aos-text-tertiary)" }}>
            v{leftVersion} → v{rightVersion} · {rightContent.author} · {rightContent.commitMessage}
          </div>
        </div>

        <label style={{ display: "flex", alignItems: "center", gap: "4px", marginBottom: "0.5rem", fontSize: "0.7rem", color: "var(--aos-text-secondary)" }}>
          <input type="checkbox" checked={showSame} onChange={(e) => setShowSame(e.target.checked)} />
          显示未变更行
        </label>

        {/* Diff 对比区 */}
        {viewMode === "side" && (
          <div style={styles.sideGrid}>
            <div style={styles.diffPanel}>
              <div style={styles.diffPanelHeader}>
                <span style={styles.versionBadgeLeft}>{leftContent.label}</span>
                <span style={styles.diffDate}>{leftContent.timestamp.slice(0, 10)}</span>
                <span style={styles.diffAuthor}>{leftContent.author}</span>
              </div>
              <div style={styles.diffBlock}>
                {leftOnly.map((line, idx) => (
                  <div
                    key={idx}
                    style={{ ...styles.diffLineRow, background: diffLineTypeBg(line.type) }}
                  >
                    <span style={styles.diffLineNum}>{line.leftNum ?? ""}</span>
                    <span style={{ ...styles.diffPrefix, color: diffLineTypeColor(line.type) }}>
                      {diffLineTypeLabel(line.type)}
                    </span>
                    <span style={styles.diffContent}>{line.leftContent}</span>
                  </div>
                ))}
              </div>
            </div>
            <div style={{ ...styles.diffPanel, boxShadow: "0 0 0 2px var(--aos-indigo-border)" }}>
              <div style={styles.diffPanelHeader}>
                <span style={styles.versionBadgeRight}>{rightContent.label}</span>
                <span style={styles.diffDate}>{rightContent.timestamp.slice(0, 10)}</span>
                <span style={styles.diffAuthor}>{rightContent.author}</span>
              </div>
              <div style={styles.diffBlock}>
                {rightOnly.map((line, idx) => (
                  <div
                    key={idx}
                    style={{ ...styles.diffLineRow, background: diffLineTypeBg(line.type) }}
                  >
                    <span style={styles.diffLineNum}>{line.rightNum ?? ""}</span>
                    <span style={{ ...styles.diffPrefix, color: diffLineTypeColor(line.type) }}>
                      {diffLineTypeLabel(line.type)}
                    </span>
                    <span style={styles.diffContent}>{line.rightContent}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {viewMode === "inline" && (
          <div style={styles.diffPanel}>
            <div style={styles.diffPanelHeader}>
              <span style={{ ...styles.versionBadgeRight }}>行内视图</span>
              <span style={styles.diffDate}>v{leftVersion} → v{rightVersion}</span>
            </div>
            <div style={styles.diffBlock}>
              {inlineDiff(filtered).map((line, idx) => (
                <div
                  key={idx}
                  style={{ ...styles.diffLineRow, background: diffLineTypeBg(line.type) }}
                >
                  <span style={styles.diffLineNum}>{line.lineNum ?? ""}</span>
                  <span style={{ ...styles.diffPrefix, color: diffLineTypeColor(line.type) }}>
                    {diffLineTypeLabel(line.type)}
                  </span>
                  <span style={styles.diffContent}>{line.content}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {viewMode === "unified" && (
          <div style={styles.diffPanel}>
            <div style={styles.diffPanelHeader}>
              <span style={{ ...styles.versionBadgeRight }}>统一视图</span>
              <span style={styles.diffDate}>v{leftVersion} → v{rightVersion}</span>
            </div>
            <div style={styles.diffBlock}>
              {filtered.map((line, idx) => (
                <div
                  key={idx}
                  style={{ ...styles.diffLineRow, background: diffLineTypeBg(line.type) }}
                >
                  <span style={{ ...styles.diffLineNum, width: 24 }}>{line.leftNum ?? ""}</span>
                  <span style={{ ...styles.diffLineNum, width: 24 }}>{line.rightNum ?? ""}</span>
                  <span style={{ ...styles.diffPrefix, color: diffLineTypeColor(line.type) }}>
                    {diffLineTypeLabel(line.type)}
                  </span>
                  <span style={styles.diffContent}>
                    {line.type === "add" ? line.rightContent : line.leftContent}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 版本时间线 */}
        <div style={{ marginTop: "1rem" }}>
          <h3 style={styles.sectionTitle}>版本历史</h3>
          <div style={styles.versionTimeline}>
            {MOCK_VERSIONS.map((v) => (
              <div
                key={v.version}
                style={{
                  ...styles.versionTimelineRow,
                  ...(v.version === rightVersion ? styles.versionTimelineActive : {}),
                }}
                onClick={() => setRightVersion(v.version)}
              >
                <span
                  style={
                    v.version === rightVersion
                      ? styles.versionBadgeCurrent
                      : styles.versionBadgeOld
                  }
                >
                  v{v.version}
                </span>
                <span style={{ flex: 1, fontSize: "0.75rem" }}>{v.message}</span>
                <span style={styles.versionMeta}>
                  {v.author} · {v.timestamp.slice(0, 10)}
                </span>
                {v.version === rightVersion && (
                  <span style={{ ...styles.currentTag, color: "var(--aos-indigo-600)" }}>
                    查看
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* 恢复确认 Modal */}
        {showRestoreModal && (
          <div style={styles.modalOverlay} onClick={() => setShowRestoreModal(false)}>
            <div style={styles.modalCard} onClick={(e) => e.stopPropagation()}>
              <div style={styles.modalHeader}>
                <span style={{ fontWeight: 600, fontSize: "0.85rem" }}>恢复到 v{leftVersion}</span>
                <button type="button" style={styles.modalClose} onClick={() => setShowRestoreModal(false)}>
                  ×
                </button>
              </div>
              <div style={{ padding: "1rem" }}>
                <BpBanner tone="warn">
                  确认后将版本回退到 v{leftVersion}，v{rightVersion} 的所有变更将被丢弃。
                </BpBanner>
                <div style={{ marginTop: "0.75rem" }}>
                  <p style={{ fontSize: "0.7rem", color: "var(--aos-text-secondary)", marginBottom: "0.25rem" }}>
                    将丢弃的变更：
                  </p>
                  <ul style={{ fontSize: "0.7rem", color: "var(--aos-text-secondary)", lineHeight: 1.8, paddingLeft: "1.25rem", listStyle: "disc" }}>
                    {diffLines.filter((l) => l.type !== "same").slice(0, 8).map((l, idx) => (
                      <li key={idx}>
                        <span style={{ color: diffLineTypeColor(l.type), fontWeight: 600 }}>
                          {diffLineTypeLabel(l.type)}
                        </span>{" "}
                        {(l.rightContent ?? l.leftContent ?? "").slice(0, 60)}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
              <div style={styles.modalFooter}>
                <button type="button" style={styles.modalCancelBtn} onClick={() => setShowRestoreModal(false)}>
                  取消
                </button>
                <button type="button" style={styles.modalConfirmBtn} onClick={confirmRestore}>
                  确认恢复
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </S2Chrome>
  );
}

/* ────────────── Styles ────────────── */

const styles: Record<string, React.CSSProperties> = {
  selectorBar: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: "0.75rem",
    flexWrap: "wrap",
    gap: "0.5rem",
  },
  versionSelect: { fontSize: "0.7rem", padding: "4px 8px", minWidth: 100 },
  viewModeSwitch: { display: "flex", borderRadius: "2px", overflow: "hidden", border: "1px solid var(--aos-border)" },
  viewModeBtn: { padding: "4px 12px", fontSize: "0.7rem", border: "none", background: "var(--aos-surface)", color: "var(--aos-text-secondary)", cursor: "pointer" },
  viewModeActive: { padding: "4px 12px", fontSize: "0.7rem", border: "none", background: "var(--aos-indigo-600)", color: "var(--text-on-brand)", fontWeight: 600, cursor: "pointer" },
  summaryBar: {
    display: "flex",
    alignItems: "center",
    gap: "1rem",
    padding: "0.5rem 0.75rem",
    border: "1px solid var(--aos-border)",
    borderRadius: "2px",
    marginBottom: "0.75rem",
    background: "var(--aos-surface)",
  },
  summaryItem: { display: "flex", alignItems: "center", gap: "4px" },
  summaryDot: { width: 8, height: 8, borderRadius: "50%" },
  sideGrid: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" },
  diffPanel: { border: "1px solid var(--aos-border)", borderRadius: "2px", overflow: "hidden", background: "var(--aos-surface)" },
  diffPanelHeader: { display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.4rem 0.75rem", borderBottom: "1px solid var(--aos-border)", background: "var(--aos-surface-hover)" },
  versionBadgeLeft: { padding: "1px 6px", borderRadius: "3px", background: "var(--aos-gray-100)", color: "var(--aos-text-secondary)", fontSize: "0.6rem", fontWeight: 600 },
  versionBadgeRight: { padding: "1px 6px", borderRadius: "3px", background: "var(--aos-indigo-bg)", color: "var(--aos-indigo-600)", fontSize: "0.6rem", fontWeight: 600 },
  diffDate: { fontSize: "0.65rem", color: "var(--aos-text-tertiary)" },
  diffAuthor: { fontSize: "0.6rem", color: "var(--aos-text-tertiary)", marginLeft: "auto" },
  diffBlock: { fontFamily: "'Menlo','Monaco',monospace", fontSize: "0.7rem", lineHeight: 1.7, padding: "0.5rem" },
  diffLineRow: { display: "flex", alignItems: "baseline", padding: "0 4px", borderRadius: "2px" },
  diffLineNum: { width: 32, textAlign: "right" as const, paddingRight: 8, color: "var(--aos-text-tertiary)", fontSize: "0.6rem", userSelect: "none", flexShrink: 0 },
  diffPrefix: { width: 12, textAlign: "center" as const, fontWeight: 600, flexShrink: 0 },
  diffContent: { whiteSpace: "pre-wrap" as const, wordBreak: "break-all" as const, color: "var(--aos-text-secondary)" },
  sectionTitle: { fontSize: "0.85rem", fontWeight: 600, color: "var(--aos-text)", marginBottom: "0.5rem" },
  versionTimeline: { border: "1px solid var(--aos-border)", borderRadius: "2px", background: "var(--aos-surface)" },
  versionTimelineRow: { display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.4rem 0.75rem", borderBottom: "1px solid var(--aos-border)", cursor: "pointer" },
  versionTimelineActive: { background: "var(--aos-indigo-bg)" },
  versionBadgeCurrent: { padding: "1px 6px", borderRadius: "3px", background: "var(--aos-indigo-bg)", color: "var(--aos-indigo-600)", fontSize: "0.6rem", fontWeight: 600, width: 28, textAlign: "center" as const },
  versionBadgeOld: { padding: "1px 6px", borderRadius: "3px", background: "var(--aos-gray-100)", color: "var(--aos-text-secondary)", fontSize: "0.6rem", fontWeight: 600, width: 28, textAlign: "center" as const },
  versionMeta: { fontSize: "0.6rem", color: "var(--aos-text-tertiary)" },
  currentTag: { fontSize: "0.6rem", fontWeight: 600 },
  modalOverlay: { position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)", zIndex: 10000, display: "flex", alignItems: "center", justifyContent: "center" },
  modalCard: { background: "var(--aos-surface)", borderRadius: "2px", width: 520, maxHeight: "85vh", overflowY: "auto" as const, boxShadow: "0 20px 60px rgba(0,0,0,0.15)" },
  modalHeader: { padding: "0.75rem 1.25rem", borderBottom: "1px solid var(--aos-border)", display: "flex", justifyContent: "space-between", alignItems: "center" },
  modalClose: { color: "var(--aos-text-tertiary)", fontSize: "1.1rem", background: "none", border: "none", cursor: "pointer" },
  modalFooter: { padding: "0.6rem 1.25rem", borderTop: "1px solid var(--aos-border)", background: "var(--aos-surface-hover)", display: "flex", justifyContent: "flex-end", gap: "0.5rem", borderRadius: "0 0 12px 12px" },
  modalCancelBtn: { padding: "4px 16px", fontSize: "0.7rem", border: "1px solid var(--aos-border-strong)", borderRadius: "2px", background: "var(--aos-surface)", color: "var(--aos-text-secondary)", cursor: "pointer" },
  modalConfirmBtn: { padding: "4px 16px", fontSize: "0.7rem", border: "none", borderRadius: "2px", background: "var(--aos-accent)", color: "var(--text-on-brand)", cursor: "pointer", fontWeight: 600 },
};
