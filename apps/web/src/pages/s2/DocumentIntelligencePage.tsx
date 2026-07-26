import { useState } from "react";
import { PageChrome } from "../../components/PageChrome";

type DocStatus = "success" | "processing" | "failed" | "pending";
type DocType = "pdf" | "word" | "excel" | "image" | "ppt";

type DocItem = {
  id: string;
  title: string;
  type: DocType;
  size: string;
  status: DocStatus;
  uploadedAt: string;
};

type ExtractField = {
  name: string;
  type: string;
  value: string;
};

const DOCS: DocItem[] = [
  { id: "d1", title: "2024年度财务报告.pdf", type: "pdf", size: "2.4 MB", status: "success", uploadedAt: "2024-07-20 14:32" },
  { id: "d2", title: "合同模板-采购协议.docx", type: "word", size: "856 KB", status: "success", uploadedAt: "2024-07-19 10:15" },
  { id: "d3", title: "供应商清单-2024Q3.xlsx", type: "excel", size: "1.2 MB", status: "processing", uploadedAt: "2024-07-26 09:20" },
  { id: "d4", title: "发票扫描件-0821.jpg", type: "image", size: "3.8 MB", status: "success", uploadedAt: "2024-07-22 16:48" },
  { id: "d5", title: "技术规格说明书-v2.1.pdf", type: "pdf", size: "5.6 MB", status: "success", uploadedAt: "2024-07-18 11:02" },
  { id: "d6", title: "季度汇报-Q3.pptx", type: "ppt", size: "8.2 MB", status: "pending", uploadedAt: "2024-07-26 08:00" },
  { id: "d7", title: "合同-甲方公司.pdf", type: "pdf", size: "1.8 MB", status: "failed", uploadedAt: "2024-07-17 14:22" },
  { id: "d8", title: "营业执照扫描件.png", type: "image", size: "2.1 MB", status: "success", uploadedAt: "2024-07-16 09:35" },
];

const EXTRACT_FIELDS: ExtractField[] = [
  { name: "报告期间", type: "日期", value: "2024-01-01 ~ 2024-12-31" },
  { name: "公司名称", type: "文本", value: "某某科技有限公司" },
  { name: "总收入", type: "数字", value: "¥ 128,450,000" },
  { name: "净利润", type: "数字", value: "¥ 45,230,000" },
  { name: "总资产", type: "数字", value: "¥ 580,120,000" },
  { name: "负债率", type: "百分比", value: "42.3%" },
  { name: "审计意见", type: "分类", value: "无保留意见" },
  { name: "审计师", type: "文本", value: "普华永道" },
];

const TYPE_META: Record<DocType, { color: string; label: string; bg: string }> = {
  pdf: { color: "#DC2626", label: "PDF", bg: "#FEE2E2" },
  word: { color: "#2563EB", label: "Word", bg: "#DBEAFE" },
  excel: { color: "#16A34A", label: "Excel", bg: "#DCFCE7" },
  image: { color: "#9333EA", label: "图片", bg: "#F3E8FF" },
  ppt: { color: "#EA580C", label: "PPT", bg: "#FFEDD5" },
};

const STATUS_META: Record<DocStatus, { label: string; bg: string; color: string }> = {
  success: { label: "已提取", bg: "#DCFCE7", color: "#166534" },
  processing: { label: "处理中", bg: "#FEF3C7", color: "#92400E" },
  failed: { label: "提取失败", bg: "#FEE2E2", color: "#991B1B" },
  pending: { label: "等待中", bg: "#F3F4F6", color: "#374151" },
};

type FilterId = "all" | "processing" | "success" | "failed";

function DocIcon({ type }: { type: DocType }) {
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

function StatCard({ value, label, trend, trendUp }: { value: string; label: string; trend: string; trendUp?: boolean }) {
  return (
    <div
      style={{
        background: "#fff",
        border: "1px solid #E5E7EB",
        borderRadius: 8,
        padding: 16,
      }}
    >
      <div style={{ fontSize: 24, fontWeight: 600, color: "#111827", lineHeight: 1.2 }}>{value}</div>
      <div style={{ fontSize: 12, color: "#6B7280", marginTop: 4 }}>{label}</div>
      <div
        style={{
          fontSize: 11,
          marginTop: 6,
          color: trendUp ? "#16A34A" : "#6B7280",
        }}
      >
        {trendUp ? "↑ " : ""}
        {trend}
      </div>
    </div>
  );
}

export function DocumentIntelligencePage() {
  const [filter, setFilter] = useState<FilterId>("all");
  const [selectedId, setSelectedId] = useState<string>("d1");

  const filteredDocs = DOCS.filter((d) => {
    if (filter === "all") return true;
    return d.status === filter;
  });

  const selectedDoc = DOCS.find((d) => d.id === selectedId) ?? DOCS[0];

  return (
    <PageChrome title="文档智能" lede="导入文档、配置提取模板，自动识别并结构化关键字段">
      {/* 顶部统计卡片 */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16, marginBottom: 24 }}>
        <StatCard value="1,284" label="文档总数" trend="12.5% 本周" trendUp />
        <StatCard value="98.2%" label="提取准确率" trend="2.1% 本月" trendUp />
        <StatCard value="24" label="处理中" trend="平均耗时 45s" />
        <StatCard value="156" label="提取模板" trend="12 个内置" />
      </div>

      {/* 筛选栏 */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: 16,
        }}
      >
        <div style={{ display: "flex", gap: 8 }}>
          {([
            { id: "all", label: "全部文档" },
            { id: "processing", label: "处理中" },
            { id: "success", label: "已完成" },
            { id: "failed", label: "失败" },
          ] as const).map((f) => {
            const active = filter === f.id;
            return (
              <button
                key={f.id}
                type="button"
                onClick={() => setFilter(f.id)}
                style={{
                  padding: "6px 12px",
                  fontSize: 13,
                  borderRadius: 6,
                  border: active ? "1px solid #4F46E5" : "1px solid #E5E7EB",
                  background: active ? "#4F46E5" : "#fff",
                  color: active ? "#fff" : "#374151",
                  cursor: "pointer",
                }}
              >
                {f.label}
              </button>
            );
          })}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <select
            style={{
              padding: "6px 12px",
              fontSize: 13,
              borderRadius: 6,
              border: "1px solid #E5E7EB",
              background: "#fff",
              color: "#374151",
            }}
          >
            <option>按时间排序</option>
            <option>按名称排序</option>
            <option>按大小排序</option>
          </select>
        </div>
      </div>

      {/* 主体：左文档网格 + 右详情面板 */}
      <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
        {/* 文档网格 */}
        <div style={{ flex: 1 }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
              gap: 16,
            }}
          >
            {filteredDocs.map((doc) => {
              const statusMeta = STATUS_META[doc.status];
              const isSelected = doc.id === selectedId;
              return (
                <div
                  key={doc.id}
                  onClick={() => setSelectedId(doc.id)}
                  style={{
                    border: isSelected ? "1px solid #4F46E5" : "1px solid #E5E7EB",
                    borderRadius: 8,
                    overflow: "hidden",
                    cursor: "pointer",
                    background: "#fff",
                    boxShadow: isSelected ? "0 0 0 3px rgba(79, 70, 229, 0.1)" : "none",
                    transition: "all 0.15s",
                  }}
                >
                  <div
                    style={{
                      height: 140,
                      background: "#F9FAFB",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      borderBottom: "1px solid #F3F4F6",
                    }}
                  >
                    <DocIcon type={doc.type} />
                  </div>
                  <div style={{ padding: 12 }}>
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 500,
                        color: "#111827",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {doc.title}
                    </div>
                    <div
                      style={{
                        fontSize: 11,
                        color: "#6B7280",
                        marginTop: 4,
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <span>{doc.size}</span>
                      <span
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          padding: "2px 6px",
                          borderRadius: 4,
                          fontSize: 10,
                          fontWeight: 500,
                          background: statusMeta.bg,
                          color: statusMeta.color,
                        }}
                      >
                        {statusMeta.label}
                      </span>
                    </div>
                    <div style={{ fontSize: 10, color: "#9CA3AF", marginTop: 4 }}>{doc.uploadedAt}</div>
                  </div>
                </div>
              );
            })}
          </div>

          {filteredDocs.length === 0 && (
            <div
              style={{
                padding: "40px 20px",
                textAlign: "center",
                color: "#9CA3AF",
                fontSize: 13,
                border: "1px dashed #E5E7EB",
                borderRadius: 8,
                background: "#FAFAFA",
              }}
            >
              当前筛选条件下暂无文档
            </div>
          )}
        </div>

        {/* 右侧详情面板 */}
        <div
          style={{
            width: 320,
            borderLeft: "1px solid #E5E7EB",
            paddingLeft: 24,
          }}
        >
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, color: "#9CA3AF" }}>当前模板</div>
            <h3 style={{ fontSize: 14, fontWeight: 600, color: "#111827", margin: "4px 0 0" }}>
              提取字段 · 财务报告模板
            </h3>
          </div>

          <div>
            {EXTRACT_FIELDS.map((field, idx) => (
              <div
                key={field.name}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "8px 0",
                  borderBottom: idx === EXTRACT_FIELDS.length - 1 ? "none" : "1px solid #F3F4F6",
                }}
              >
                <div style={{ display: "flex", alignItems: "center" }}>
                  <span style={{ fontSize: 12, fontWeight: 500, color: "#374151" }}>{field.name}</span>
                  <span
                    style={{
                      fontSize: 10,
                      padding: "1px 4px",
                      borderRadius: 3,
                      background: "#EEF2FF",
                      color: "#4F46E5",
                      marginLeft: 6,
                    }}
                  >
                    {field.type}
                  </span>
                </div>
                <span
                  style={{
                    fontSize: 12,
                    color: "#6B7280",
                    maxWidth: 180,
                    textAlign: "right",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {field.value}
                </span>
              </div>
            ))}
          </div>

          {/* 文档信息 */}
          <div style={{ marginTop: 24, paddingTop: 16, borderTop: "1px solid #E5E7EB" }}>
            <h4
              style={{
                fontSize: 11,
                fontWeight: 600,
                color: "#6B7280",
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                marginBottom: 12,
              }}
            >
              文档信息
            </h4>
            <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#9CA3AF" }}>文件名</span>
                <span style={{ color: "#374151", maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {selectedDoc.title}
                </span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#9CA3AF" }}>文件大小</span>
                <span style={{ color: "#374151" }}>{selectedDoc.size}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#9CA3AF" }}>上传时间</span>
                <span style={{ color: "#374151" }}>{selectedDoc.uploadedAt}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#9CA3AF" }}>处理耗时</span>
                <span style={{ color: "#374151" }}>2 分 15 秒</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "#9CA3AF" }}>置信度</span>
                <span style={{ color: "#16A34A", fontWeight: 500 }}>96.8%</span>
              </div>
            </div>
          </div>

          {/* 操作按钮 */}
          <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 8 }}>
            <button
              type="button"
              style={{
                width: "100%",
                padding: "8px 12px",
                fontSize: 13,
                borderRadius: 6,
                border: "1px solid #E5E7EB",
                background: "#fff",
                color: "#374151",
                cursor: "pointer",
              }}
            >
              查看原始文档
            </button>
            <button
              type="button"
              style={{
                width: "100%",
                padding: "8px 12px",
                fontSize: 13,
                borderRadius: 6,
                border: "1px solid #4F46E5",
                background: "#4F46E5",
                color: "#fff",
                cursor: "pointer",
              }}
            >
              重新提取
            </button>
          </div>
        </div>
      </div>
    </PageChrome>
  );
}
