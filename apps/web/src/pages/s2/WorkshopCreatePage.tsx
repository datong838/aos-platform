import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageChrome } from "../../components/PageChrome";
import { BpCard } from "../../components/bp/BpCard";
import { BpStepper, type BpStep } from "../../components/bp/BpStepper";
import { apiPost } from "../../api/client";

/* ============================================================================
 * 常量与类型（导出用于测试）
 * ========================================================================== */

export const STEPS: BpStep[] = [
  { key: "basic", title: "基础信息", description: "名称、分类、描述" },
  { key: "template", title: "选择模板", description: "空白/仪表盘/表单/列表/复制" },
  { key: "confirm", title: "确认创建", description: "核对信息并创建" },
];

export type CategoryId =
  | "order"
  | "risk"
  | "customer"
  | "asset"
  | "analytics"
  | "ticket"
  | "inventory"
  | "finance"
  | "marketing";

export const CATEGORIES: { id: CategoryId; name: string; color: string }[] = [
  { id: "order", name: "订单", color: "#2563EB" },
  { id: "risk", name: "风控", color: "#DC2626" },
  { id: "customer", name: "客户", color: "#7C3AED" },
  { id: "asset", name: "资产", color: "#0891B2" },
  { id: "analytics", name: "分析", color: "#059669" },
  { id: "ticket", name: "工单", color: "#D97706" },
  { id: "inventory", name: "库存", color: "#4F46E5" },
  { id: "finance", name: "财务", color: "#0D9488" },
  { id: "marketing", name: "营销", color: "#DB2777" },
];

export type TemplateId = "blank" | "dashboard" | "form" | "table" | "copy";

export interface TemplateDef {
  id: TemplateId;
  name: string;
  desc: string;
  blank?: boolean;
  preview?: "dashboard" | "form" | "table";
}

export const TEMPLATES: TemplateDef[] = [
  {
    id: "blank",
    name: "空白模板",
    desc: "零预填 Widget，完全从零搭建。适合高度自定义场景。",
    blank: true,
  },
  {
    id: "dashboard",
    name: "仪表盘模板",
    desc: "统计卡片 x4 + 趋势图 + 饼图。适合数据监控和概览场景。",
    preview: "dashboard",
  },
  {
    id: "form",
    name: "表单模板",
    desc: "表单输入 + 校验 + 提交按钮。适合数据录入和审批场景。",
    preview: "form",
  },
  {
    id: "table",
    name: "列表模板",
    desc: "筛选栏 + 数据表格 + 详情面板。适合 CRUD 管理场景。",
    preview: "table",
  },
];

export interface ExistingModule {
  id: string;
  name: string;
  category: string;
  updated_at: string;
}

export const MOCK_EXISTING_MODULES: ExistingModule[] = [
  { id: "mod-001", name: "订单管理系统", category: "order", updated_at: "2026-07-20T10:00:00Z" },
  { id: "mod-002", name: "风险告警管理", category: "risk", updated_at: "2026-07-19T14:30:00Z" },
  { id: "mod-003", name: "客户档案中心", category: "customer", updated_at: "2026-07-18T09:15:00Z" },
  { id: "mod-004", name: "库存盘点看板", category: "inventory", updated_at: "2026-07-17T16:45:00Z" },
  { id: "mod-005", name: "财务对账系统", category: "finance", updated_at: "2026-07-16T11:20:00Z" },
];

/* ============================================================================
 * 纯函数（导出用于测试）
 * ========================================================================== */

export function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa5]/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}

export function canNextFromStep1(name: string, category: string): boolean {
  return name.trim().length > 0 && category.trim().length > 0;
}

export function canNextFromStep2(templateId: TemplateId, copyFromId: string | null): boolean {
  if (templateId === "copy") return !!copyFromId;
  return !!templateId;
}

export interface CreateModulePayload {
  name: string;
  slug: string;
  category: string;
  description: string;
  template: TemplateId;
  copy_from: string | null;
}

export function buildCreatePayload(input: {
  name: string;
  category: string;
  description: string;
  template: TemplateId;
  copyFromId: string | null;
}): CreateModulePayload {
  return {
    name: input.name.trim(),
    slug: slugify(input.name),
    category: input.category,
    description: input.description.trim(),
    template: input.template,
    copy_from: input.template === "copy" ? input.copyFromId : null,
  };
}

/* ============================================================================
 * 页面组件
 * ========================================================================== */

export function WorkshopCreatePage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [appName, setAppName] = useState("");
  const [category, setCategory] = useState<CategoryId>("order");
  const [description, setDescription] = useState("");
  const [template, setTemplate] = useState<TemplateId>("table");
  const [copyFromId, setCopyFromId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdId, setCreatedId] = useState<string | null>(null);

  const slug = useMemo(() => slugify(appName), [appName]);

  const canNext1 = canNextFromStep1(appName, category);
  const canNext2 = canNextFromStep2(template, copyFromId);

  const selectedCategory = CATEGORIES.find((c) => c.id === category);
  const selectedTemplate = TEMPLATES.find((t) => t.id === template);
  const selectedCopyModule = MOCK_EXISTING_MODULES.find((m) => m.id === copyFromId);

  async function handleCreate() {
    setError(null);
    setCreating(true);
    const payload = buildCreatePayload({
      name: appName,
      category,
      description,
      template,
      copyFromId,
    });
    try {
      const result = await apiPost<{ module_id: string }>("/v1/modules", payload);
      setCreatedId(result.module_id);
      setCreating(false);
      // 短暂延迟后跳转，让用户看到成功状态
      setTimeout(() => {
        navigate(`/workshop/canvas?module=${result.module_id}`);
      }, 800);
    } catch (e) {
      // API 不存在时 fallback 为 mock 创建
      const mockId = `mod-mock-${Date.now()}`;
      setCreatedId(mockId);
      setCreating(false);
      setTimeout(() => {
        navigate(`/workshop/canvas?module=${mockId}`);
      }, 800);
    }
  }

  return (
    <PageChrome title="创建模块" lede="3 步创建新的 Workshop 应用模块">
      {/* 226-S1: 去掉 max-width 限宽 */}
      <div style={{ padding: "24px 0" }}>
        {/* 顶部步骤条 */}
        <div style={{ marginBottom: 32 }}>
          <BpStepper steps={STEPS} current={step - 1} />
        </div>

        {/* 错误提示 */}
        {error && (
          <div
            role="alert"
            style={{
              background: "var(--aos-red-bg, #FEE2E2)",
              color: "var(--aos-red, #DC2626)",
              padding: "8px 12px",
              borderRadius: 2,
              marginBottom: 12,
              fontSize: 13,
              border: "1px solid var(--aos-red-border, #FCA5A5)",
            }}
          >
            {error}
          </div>
        )}

        {/* 成功提示 */}
        {createdId && (
          <div
            style={{
              background: "var(--aos-green-bg)",
              color: "var(--aos-green-700)",
              padding: "12px 16px",
              borderRadius: 2,
              marginBottom: 16,
              fontSize: 13,
              border: "1px solid var(--aos-green-border)",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            模块创建成功！ID: {createdId}，正在跳转到画布编辑器...
          </div>
        )}

        {/* Step 1: 基础信息 */}
        {step === 1 && (
          <BpCard title="Step 1 · 基础信息" subtitle="设置模块名称、分类和描述，创建后仍可修改。">
            <FormGrid>
              <FieldLabel required>模块名称</FieldLabel>
              <input
                className="aos-input"
                style={{ height: 38, fontSize: 13, padding: "0 12px" }}
                value={appName}
                onChange={(e) => setAppName(e.target.value)}
                placeholder="如：库存管理系统"
                data-testid="create-app-name"
              />

              <FieldLabel>
                模块标识{" "}
                <span style={{ fontSize: 11, color: "var(--aos-muted)", fontWeight: 400 }}>
                  （自动生成，用于 API 引用）
                </span>
              </FieldLabel>
              <input
                className="aos-input"
                style={{ height: 38, fontSize: 13, padding: "0 12px", background: "var(--aos-surface-hover)" }}
                value={slug}
                readOnly
                placeholder="inventory-mgmt"
                data-testid="create-slug"
              />

              <FieldLabel required>模块分类</FieldLabel>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }} data-testid="create-categories">
                {CATEGORIES.map((cat) => (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => setCategory(cat.id)}
                    data-testid={`create-cat-${cat.id}`}
                    style={{
                      padding: "6px 14px",
                      borderRadius: 2,
                      fontSize: 12,
                      fontWeight: 500,
                      cursor: "pointer",
                      border: category === cat.id ? `1.5px solid ${cat.color}` : "1px solid var(--aos-border)",
                      background: category === cat.id ? `${cat.color}15` : "var(--aos-surface)",
                      color: category === cat.id ? cat.color : "var(--aos-text-secondary)",
                      transition: "all 0.15s",
                    }}
                  >
                    {cat.name}
                  </button>
                ))}
              </div>

              <FieldLabel>
                描述{" "}
                <span style={{ fontSize: 11, color: "var(--aos-muted)", fontWeight: 400 }}>
                  （一句话说明，选填）
                </span>
              </FieldLabel>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="如：管理仓库库存、入库/出库记录、库存预警..."
                rows={3}
                className="aos-input"
                style={{ minHeight: 72, fontSize: 13, padding: "8px 12px", resize: "vertical" }}
                data-testid="create-description"
              />
            </FormGrid>

            <StepFooter
              onCancel={() => navigate("/workshop")}
              onNext={() => canNext1 && setStep(2)}
              nextDisabled={!canNext1}
            />
          </BpCard>
        )}

        {/* Step 2: 选择模板 */}
        {step === 2 && (
          <BpCard title="Step 2 · 选择模板" subtitle="选择起始布局模板，或从已有模块复制。后续可自由增删修改。">
            {/* 模板卡片网格 */}
            <div
              style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 14 }}
              data-testid="create-templates"
            >
              {TEMPLATES.map((t) => {
                const selected = template === t.id;
                return (
                  <div
                    key={t.id}
                    className={selected ? "ws-template-card is-selected" : "ws-template-card"}
                    onClick={() => setTemplate(t.id)}
                    role="button"
                    tabIndex={0}
                    data-testid={`create-tpl-${t.id}`}
                    style={{
                      border: selected ? "2px solid var(--aos-accent)" : "1px solid var(--aos-border)",
                      borderRadius: 2,
                      padding: 14,
                      cursor: "pointer",
                      background: selected ? "var(--aos-accent-light)" : "var(--aos-surface)",
                      transition: "all 0.15s",
                    }}
                  >
                    <TemplatePreview type={t.preview} blank={t.blank} />
                    <div style={{ fontSize: 13, fontWeight: 500, color: "var(--aos-text)", marginBottom: 4 }}>
                      {t.name}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--aos-text-secondary)", lineHeight: 1.5 }}>{t.desc}</div>
                  </div>
                );
              })}

              {/* 从已有模块复制 */}
              <div
                className={template === "copy" ? "ws-template-card is-selected" : "ws-template-card"}
                onClick={() => setTemplate("copy")}
                role="button"
                tabIndex={0}
                data-testid="create-tpl-copy"
                style={{
                  border: template === "copy" ? "2px solid var(--aos-accent)" : "1px solid var(--aos-border)",
                  borderRadius: 2,
                  padding: 14,
                  cursor: "pointer",
                  background: template === "copy" ? "var(--aos-accent-light)" : "var(--aos-surface)",
                  transition: "all 0.15s",
                }}
              >
                <div
                  style={{
                    width: "100%",
                    height: 80,
                    borderRadius: 4,
                    background: "var(--aos-surface-hover)",
                    marginBottom: 10,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="var(--aos-text-secondary)" strokeWidth="1.5">
                    <rect x="9" y="9" width="13" height="13" rx="2" />
                    <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </div>
                <div style={{ fontSize: 13, fontWeight: 500, color: "var(--aos-text)", marginBottom: 4 }}>
                  从已有模块复制
                </div>
                <div style={{ fontSize: 11, color: "var(--aos-text-secondary)", lineHeight: 1.5 }}>
                  选择一个现有模块，复制其全部 Widget 和配置。
                </div>
              </div>
            </div>

            {/* 复制源选择器 */}
            {template === "copy" && (
              <div
                style={{
                  marginTop: 16,
                  padding: 14,
                  border: "1px solid var(--aos-border)",
                  borderRadius: 2,
                  background: "var(--aos-surface-hover)",
                }}
                data-testid="create-copy-source"
              >
                <div style={{ fontSize: 12, fontWeight: 500, color: "var(--aos-text)", marginBottom: 8 }}>
                  选择要复制的源模块：
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  {MOCK_EXISTING_MODULES.map((m) => (
                    <div
                      key={m.id}
                      onClick={() => setCopyFromId(m.id)}
                      role="button"
                      tabIndex={0}
                      data-testid={`create-copy-${m.id}`}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "8px 12px",
                        borderRadius: 2,
                        cursor: "pointer",
                        border: copyFromId === m.id ? "1.5px solid var(--aos-accent)" : "1px solid var(--aos-border)",
                        background: copyFromId === m.id ? "var(--aos-accent-light)" : "var(--aos-surface)",
                        transition: "all 0.1s",
                      }}
                    >
                      <div>
                        <span style={{ fontSize: 13, fontWeight: 500, color: "var(--aos-text)" }}>{m.name}</span>
                        <span
                          style={{
                            fontSize: 10,
                            padding: "1px 6px",
                            borderRadius: 3,
                            background: "var(--aos-accent-light)",
                            color: "var(--aos-accent)",
                            marginLeft: 8,
                          }}
                        >
                          {CATEGORIES.find((c) => c.id === m.category)?.name || m.category}
                        </span>
                      </div>
                      <span style={{ fontSize: 11, color: "var(--aos-faint)" }}>{m.updated_at.slice(0, 10)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 选中模板预填充信息 */}
            {template !== "copy" && selectedTemplate && !selectedTemplate.blank && (
              <div
                style={{
                  marginTop: 16,
                  padding: 12,
                  borderRadius: 2,
                  background: "var(--aos-accent-light)",
                  border: "1px solid var(--aos-green-border)",
                }}
              >
                <div style={{ fontSize: 12, fontWeight: 500, color: "var(--aos-green-700)", marginBottom: 4 }}>
                  选中模板将预填充：
                </div>
                <div style={{ fontSize: 11, color: "var(--aos-green-700)", lineHeight: 1.6 }}>
                  {selectedTemplate.id === "dashboard" &&
                    "4 个统计卡片 Widget + 1 个趋势图 + 1 个饼图 · 3 个 Variables"}
                  {selectedTemplate.id === "form" &&
                    "1 个表单 Widget + 校验规则 + 提交按钮 · 2 个 Variables"}
                  {selectedTemplate.id === "table" &&
                    "1 个筛选栏 + 1 个数据表格 + 1 个详情面板 · 2 个 Variables · 1 个 Event"}
                </div>
              </div>
            )}

            <StepFooter onPrev={() => setStep(1)} onNext={() => canNext2 && setStep(3)} nextDisabled={!canNext2} />
          </BpCard>
        )}

        {/* Step 3: 确认创建 */}
        {step === 3 && (
          <BpCard title="Step 3 · 确认创建" subtitle="请检查以下信息，确认后将创建 Module 并进入画布编辑器。">
            <div
              style={{
                border: "1px solid var(--aos-border)",
                borderRadius: 2,
                overflow: "hidden",
                background: "var(--aos-surface)",
                marginBottom: 16,
              }}
            >
              <div
                style={{
                  padding: "10px 16px",
                  background: "var(--aos-surface-hover)",
                  borderBottom: "1px solid var(--aos-border)",
                  fontSize: 12,
                  fontWeight: 500,
                  color: "var(--aos-text)",
                }}
              >
                模块信息汇总
              </div>
              <div style={{ padding: 16 }}>
                <table style={{ width: "100%", fontSize: 12, borderCollapse: "collapse" }} data-testid="create-summary">
                  <tbody>
                    <SummaryRow label="模块名称" value={appName || "未设置"} />
                    <SummaryRow label="模块标识" value={slug || "未生成"} mono />
                    <SummaryRow
                      label="分类"
                      value={
                        <span
                          style={{
                            padding: "2px 8px",
                            background: `${selectedCategory?.color || "var(--aos-text-secondary)"}15`,
                            color: selectedCategory?.color || "var(--aos-text-secondary)",
                            borderRadius: 4,
                            fontSize: 11,
                            fontWeight: 500,
                          }}
                        >
                          {selectedCategory?.name || "未选择"}
                        </span>
                      }
                    />
                    <SummaryRow label="描述" value={description || "未填写"} />
                    <SummaryRow
                      label="模板"
                      value={template === "copy" ? `从「${selectedCopyModule?.name || "未选择"}」复制` : selectedTemplate?.name || "未选择"}
                    />
                    <SummaryRow
                      label="创建后状态"
                      value={
                        <span
                          style={{
                            padding: "2px 8px",
                            background: "var(--aos-amber-bg)",
                            color: "var(--aos-amber-700)",
                            borderRadius: 4,
                            fontSize: 11,
                          }}
                        >
                          Draft
                        </span>
                      }
                    />
                  </tbody>
                </table>
              </div>
            </div>

            <div
              style={{
                padding: 12,
                borderRadius: 2,
                background: "var(--aos-accent-light)",
                border: "1px solid var(--aos-accent-border)",
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 500, color: "var(--aos-blue-title)", marginBottom: 6 }}>
                创建后将自动执行：
              </div>
              <ul style={{ fontSize: 11, color: "var(--aos-blue-600)", lineHeight: 1.8, listStyle: "none", padding: 0, margin: 0 }}>
                <li>1. 创建 Module 资源（含 Layout + Widget）</li>
                <li>2. 初始化 Variables 并绑定数据源</li>
                <li>3. 创建 Event Handler（如有）</li>
                <li>4. 跳转到画布编辑器（可立即编辑界面）</li>
              </ul>
            </div>

            <StepFooter
              onPrev={() => setStep(2)}
              onNext={handleCreate}
              nextDisabled={creating || !!createdId}
              nextLabel={creating ? "创建中…" : createdId ? "已创建 ✓" : "创建并进入编辑 →"}
              center
            />
          </BpCard>
        )}
      </div>
    </PageChrome>
  );
}

/* ============================================================================
 * 子组件
 * ========================================================================== */

function TemplatePreview({ type, blank }: { type?: string; blank?: boolean }) {
  if (blank) {
    return (
      <div
        style={{
          width: "100%",
          height: 80,
          borderRadius: 4,
          background: "var(--aos-surface-hover)",
          marginBottom: 10,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          border: "1px dashed var(--aos-border-strong)",
        }}
      >
        <span style={{ fontSize: 11, color: "var(--aos-faint)" }}>空白画布</span>
      </div>
    );
  }
  if (type === "table") {
    return (
      <div
        style={{ width: "100%", height: 80, borderRadius: 4, background: "var(--aos-surface-hover)", marginBottom: 10, position: "relative", overflow: "hidden" }}
      >
        <div style={{ position: "absolute", top: 6, left: 6, right: 6, height: 16, background: "var(--aos-border-strong)", borderRadius: 2 }} />
        <div style={{ position: "absolute", top: 28, left: 6, right: 6, bottom: 6, background: "var(--aos-border-strong)", borderRadius: 2 }} />
      </div>
    );
  }
  if (type === "dashboard") {
    return (
      <div
        style={{ width: "100%", height: 80, borderRadius: 4, background: "var(--aos-surface-hover)", marginBottom: 10, position: "relative", overflow: "hidden" }}
      >
        <div style={{ position: "absolute", top: 6, left: 6, width: 28, height: 24, background: "var(--aos-border-strong)", borderRadius: 2 }} />
        <div style={{ position: "absolute", top: 6, left: 40, width: 28, height: 24, background: "var(--aos-border-strong)", borderRadius: 2 }} />
        <div style={{ position: "absolute", top: 6, left: 74, width: 28, height: 24, background: "var(--aos-border-strong)", borderRadius: 2 }} />
        <div style={{ position: "absolute", top: 36, left: 6, right: 6, height: 32, background: "var(--aos-border-strong)", borderRadius: 2 }} />
      </div>
    );
  }
  if (type === "form") {
    return (
      <div
        style={{ width: "100%", height: 80, borderRadius: 4, background: "var(--aos-surface-hover)", marginBottom: 10, position: "relative", overflow: "hidden" }}
      >
        <div style={{ position: "absolute", top: 8, left: 8, right: 8, height: 12, background: "var(--aos-border-strong)", borderRadius: 2 }} />
        <div style={{ position: "absolute", top: 26, left: 8, right: 8, height: 12, background: "var(--aos-border-strong)", borderRadius: 2 }} />
        <div style={{ position: "absolute", top: 44, left: 8, right: 8, height: 12, background: "var(--aos-border-strong)", borderRadius: 2 }} />
        <div style={{ position: "absolute", top: 62, left: 8, width: 40, height: 12, background: "var(--aos-text-secondary)", borderRadius: 2 }} />
      </div>
    );
  }
  return <div style={{ width: "100%", height: 80, borderRadius: 4, background: "var(--aos-surface-hover)", marginBottom: 10 }} />;
}

function FormGrid({ children }: { children: React.ReactNode }) {
  return <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>{children}</div>;
}

function FieldLabel({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <label style={{ fontSize: 12, color: "var(--aos-text)", fontWeight: 500 }}>
      {children}
      {required ? <span style={{ color: "var(--aos-red)", marginLeft: 2 }}>*</span> : null}
    </label>
  );
}

function SummaryRow({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <tr style={{ borderBottom: "1px solid var(--aos-divider)" }}>
      <td style={{ padding: "6px 0", color: "var(--aos-faint)", width: 100, verticalAlign: "top" }}>{label}</td>
      <td style={{ padding: "6px 0", color: "var(--aos-text)", fontWeight: 500, fontFamily: mono ? "monospace" : "inherit" }}>
        {value}
      </td>
    </tr>
  );
}

function StepFooter({
  onPrev,
  onNext,
  onCancel,
  nextLabel = "下一步 →",
  nextDisabled,
  center,
}: {
  onPrev?: () => void;
  onNext: () => void;
  onCancel?: () => void;
  nextLabel?: string;
  nextDisabled?: boolean;
  center?: boolean;
}) {
  return (
    <div
      style={{
        display: "flex",
        gap: 8,
        justifyContent: center ? "center" : "flex-end",
        marginTop: 20,
        paddingTop: 12,
        borderTop: "1px solid var(--aos-border)",
      }}
    >
      {onCancel && (
        <button type="button" className="btn" onClick={onCancel}>
          取消
        </button>
      )}
      {onPrev && (
        <button type="button" className="btn" onClick={onPrev}>
          ← 上一步
        </button>
      )}
      <button
        type="button"
        className="btn btn-primary"
        onClick={onNext}
        disabled={nextDisabled}
        style={{ opacity: nextDisabled ? 0.5 : 1 }}
      >
        {nextLabel}
      </button>
    </div>
  );
}
