import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { PageChrome } from "../../components/PageChrome";
import { apiPost } from "../../api/client";

/* ============================================================================
 * 常量（对齐 workshop-create.html 四步）
 * ========================================================================== */

export type CreateStepKey = "basic" | "binding" | "template" | "confirm";

export const STEPS: { key: CreateStepKey; title: string; description: string }[] = [
  { key: "basic", title: "基本信息", description: "名称、图标、业务域" },
  { key: "binding", title: "数据绑定", description: "对象类型与属性" },
  { key: "template", title: "模板选择", description: "起始布局模板" },
  { key: "confirm", title: "确认创建", description: "核对并进入画布" },
];

export type DomainId = "运营" | "分析" | "风控" | "供应链" | "客服" | "自定义";

export const DOMAINS: DomainId[] = ["运营", "分析", "风控", "供应链", "客服", "自定义"];

export type IconId = "box" | "chart" | "alert" | "users" | "globe" | "truck";

export const ICONS: { id: IconId; label: string }[] = [
  { id: "box", label: "立方体" },
  { id: "chart", label: "图表" },
  { id: "alert", label: "告警" },
  { id: "users", label: "用户" },
  { id: "globe", label: "地球" },
  { id: "truck", label: "物流" },
];

export type ObjTypeId = "Order" | "Product" | "Inventory" | "RiskAlert" | "Customer" | "Supplier";

export const OBJ_GROUPS: { title: string; items: { id: ObjTypeId; label: string }[] }[] = [
  {
    title: "业务对象",
    items: [
      { id: "Order", label: "Order（订单）" },
      { id: "Product", label: "Product（商品）" },
      { id: "Inventory", label: "Inventory（库存）" },
      { id: "RiskAlert", label: "RiskAlert（风险告警）" },
    ],
  },
  {
    title: "用户对象",
    items: [
      { id: "Customer", label: "Customer（客户）" },
      { id: "Supplier", label: "Supplier（供应商）" },
    ],
  },
];

export const OBJ_PROPS: Record<ObjTypeId, { name: string; boundDefault: boolean }[]> = {
  Order: [
    { name: "order_id", boundDefault: true },
    { name: "customer_name", boundDefault: true },
    { name: "total_amount", boundDefault: true },
    { name: "status", boundDefault: true },
    { name: "created_at", boundDefault: true },
    { name: "shipping_address", boundDefault: false },
    { name: "payment_method", boundDefault: false },
    { name: "discount_code", boundDefault: false },
    { name: "tax_amount", boundDefault: false },
    { name: "remark", boundDefault: false },
  ],
  Product: [
    { name: "product_id", boundDefault: true },
    { name: "name", boundDefault: true },
    { name: "sku", boundDefault: true },
    { name: "price", boundDefault: true },
    { name: "category", boundDefault: false },
  ],
  Inventory: [
    { name: "sku", boundDefault: true },
    { name: "warehouse", boundDefault: true },
    { name: "qty", boundDefault: true },
    { name: "updated_at", boundDefault: true },
  ],
  RiskAlert: [
    { name: "alert_id", boundDefault: true },
    { name: "level", boundDefault: true },
    { name: "title", boundDefault: true },
    { name: "status", boundDefault: true },
  ],
  Customer: [
    { name: "customer_id", boundDefault: true },
    { name: "name", boundDefault: true },
    { name: "phone", boundDefault: false },
    { name: "tier", boundDefault: true },
  ],
  Supplier: [
    { name: "supplier_id", boundDefault: true },
    { name: "name", boundDefault: true },
    { name: "region", boundDefault: false },
  ],
};

export type TemplateId = "blank" | "table" | "dashboard" | "explorer";

export interface TemplateDef {
  id: TemplateId;
  name: string;
  desc: string;
  fillHint: string;
  preview: "blank" | "table" | "dashboard" | "explorer";
}

export const TEMPLATES: TemplateDef[] = [
  {
    id: "blank",
    name: "空白模板",
    desc: "零预填 Widget，完全从零搭建。适合高度自定义场景。",
    fillHint: "无预填 Widget / Variables / Event。",
    preview: "blank",
  },
  {
    id: "table",
    name: "表格列表模板",
    desc: "筛选栏 + 数据表格 + 详情面板。适合 CRUD 管理场景，如订单管理。",
    fillHint:
      "1 个 Layout（首页） · 3 个 Widget（FilterBar + DataTable + DetailPanel）\n2 个 Variables（all_orders: ObjectSet, selected_order: Object）\n1 个 Event（onRowClick → selected_order.setValue）",
    preview: "table",
  },
  {
    id: "dashboard",
    name: "仪表盘模板",
    desc: "统计卡片 x4 + 趋势图 + 饼图。适合数据监控和概览场景。",
    fillHint: "1 个 Layout · 4 个统计卡片 + 趋势图 + 饼图 · 3 个 Variables",
    preview: "dashboard",
  },
  {
    id: "explorer",
    name: "对象探索模板",
    desc: "对象列表 + 属性筛选 + 图表探索 + Actions。适合 Ontology 数据探索。",
    fillHint: "1 个 Layout · 对象列表 + 属性筛选 + 图表 · Actions 区 · 2 个 Variables",
    preview: "explorer",
  },
];

/* ============================================================================
 * 纯函数
 * ========================================================================== */

export function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa5]/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}

/** 对齐视觉稿：下一步不强制校验；完成时要求名称非空 */
export function canFinishCreate(name: string): boolean {
  return name.trim().length > 0;
}

export function defaultBoundProps(obj: ObjTypeId): string[] {
  return OBJ_PROPS[obj].filter((p) => p.boundDefault).map((p) => p.name);
}

export interface CreateModulePayload {
  name: string;
  slug: string;
  domain: DomainId;
  icon: IconId;
  description: string;
  object_type: ObjTypeId;
  bound_props: string[];
  template: TemplateId;
}

export function buildCreatePayload(input: {
  name: string;
  domain: DomainId;
  icon: IconId;
  description: string;
  objectType: ObjTypeId;
  boundProps: string[];
  template: TemplateId;
}): CreateModulePayload {
  return {
    name: input.name.trim(),
    slug: slugify(input.name),
    domain: input.domain,
    icon: input.icon,
    description: input.description.trim(),
    object_type: input.objectType,
    bound_props: [...input.boundProps],
    template: input.template,
  };
}

/* ============================================================================
 * 页面
 * ========================================================================== */

export function WorkshopCreatePage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [appName, setAppName] = useState("");
  const [icon, setIcon] = useState<IconId>("box");
  const [domain, setDomain] = useState<DomainId>("供应链");
  const [description, setDescription] = useState("");
  const [objectType, setObjectType] = useState<ObjTypeId>("Order");
  const [boundProps, setBoundProps] = useState<string[]>(() => defaultBoundProps("Order"));
  const [template, setTemplate] = useState<TemplateId>("table");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const slug = useMemo(() => slugify(appName), [appName]);
  const selectedTemplate = TEMPLATES.find((t) => t.id === template)!;
  const selectedIcon = ICONS.find((i) => i.id === icon)!;
  const objLabel = OBJ_GROUPS.flatMap((g) => g.items).find((i) => i.id === objectType)?.label ?? objectType;

  function goStep(n: number) {
    setStep(Math.min(4, Math.max(1, n)));
  }

  function selectObject(id: ObjTypeId) {
    setObjectType(id);
    setBoundProps(defaultBoundProps(id));
  }

  function toggleProp(name: string) {
    setBoundProps((prev) => (prev.includes(name) ? prev.filter((p) => p !== name) : [...prev, name]));
  }

  async function handleCreate() {
    if (!canFinishCreate(appName)) {
      setError("请填写模块名称后再创建。");
      goStep(1);
      return;
    }
    setError(null);
    setCreating(true);
    const payload = buildCreatePayload({
      name: appName,
      domain,
      icon,
      description,
      objectType,
      boundProps,
      template,
    });
    try {
      const result = await apiPost<{ module_id: string }>("/v1/modules", payload);
      setTimeout(() => navigate(`/workshop/canvas?module=${result.module_id}`), 600);
    } catch {
      const mockId = `mod-mock-${Date.now()}`;
      setTimeout(() => navigate(`/workshop/canvas?module=${mockId}`), 600);
    } finally {
      setCreating(false);
    }
  }

  return (
    <PageChrome title="新建 Module" lede="四步创建 Workshop 应用模块：基本信息 → 数据绑定 → 模板选择 → 确认创建">
      <div className="ws-create-page">
        <div className="ws-create-layout">
          {/* 左侧步骤导航 */}
          <aside className="ws-create-nav" aria-label="创建步骤">
            <h2 className="ws-create-nav-title">创建步骤</h2>
            <div className="ws-create-step-list" id="stepNav">
              {STEPS.map((s, idx) => {
                const n = idx + 1;
                const cls =
                  n === step
                    ? "ws-create-step-nav-item is-active"
                    : n < step
                      ? "ws-create-step-nav-item is-done"
                      : "ws-create-step-nav-item";
                return (
                  <button
                    key={s.key}
                    type="button"
                    className={cls}
                    data-step={n}
                    data-testid={`create-step-nav-${n}`}
                    onClick={() => goStep(n)}
                  >
                    <span className="ws-step-num" aria-hidden>
                      {n < step ? (
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
                          <path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      ) : (
                        n
                      )}
                    </span>
                    <span>{s.title}</span>
                  </button>
                );
              })}
            </div>
            <div className="ws-create-tip">
              <div className="ws-create-tip-title">提示</div>
              <div className="ws-create-tip-body">左侧导航可随时跳转任意步骤修改，无需按顺序走完。</div>
            </div>
          </aside>

          {/* 右侧配置区 */}
          <div className="ws-create-main">
            {error && (
              <div role="alert" className="ws-warning-box" style={{ marginBottom: 16 }}>
                {error}
              </div>
            )}

            {step === 1 && (
              <section data-testid="create-panel-1">
                <h3 className="ws-create-panel-title">基本信息</h3>
                <p className="ws-create-panel-desc">设置模块名称、图标和业务域，创建后仍可修改。</p>

                <div className="ws-create-field">
                  <label className="ws-create-label">
                    模块名称 <span className="ws-create-req">*</span>
                  </label>
                  <input
                    className="ws-create-input"
                    value={appName}
                    onChange={(e) => setAppName(e.target.value)}
                    placeholder="如：库存管理系统"
                    data-testid="create-app-name"
                  />
                </div>

                <div className="ws-create-field">
                  <label className="ws-create-label">
                    模块标识 <span className="ws-create-label-hint">（自动生成，用于 API 引用）</span>
                  </label>
                  <input
                    className="ws-create-input is-readonly"
                    value={slug}
                    readOnly
                    placeholder="inventory-mgmt"
                    data-testid="create-slug"
                  />
                </div>

                <div className="ws-create-field">
                  <label className="ws-create-label">
                    模块图标 <span className="ws-create-label-hint">（选择一个）</span>
                  </label>
                  <div className="ws-create-icon-row" data-testid="create-icons">
                    {ICONS.map((ic) => (
                      <button
                        key={ic.id}
                        type="button"
                        className={icon === ic.id ? "ws-icon-pick is-selected" : "ws-icon-pick"}
                        aria-label={ic.label}
                        data-testid={`create-icon-${ic.id}`}
                        onClick={() => setIcon(ic.id)}
                      >
                        <IconSvg id={ic.id} selected={icon === ic.id} />
                      </button>
                    ))}
                  </div>
                </div>

                <div className="ws-create-field">
                  <label className="ws-create-label">
                    业务域 <span className="ws-create-label-hint">（选择一个）</span>
                  </label>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }} data-testid="create-domains">
                    {DOMAINS.map((d) => (
                      <button
                        key={d}
                        type="button"
                        className={domain === d ? "ws-domain-chip is-selected" : "ws-domain-chip"}
                        data-testid={`create-domain-${d}`}
                        onClick={() => setDomain(d)}
                      >
                        {d}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="ws-create-field">
                  <label className="ws-create-label">
                    用途描述 <span className="ws-create-label-hint">（一句话说明，选填）</span>
                  </label>
                  <textarea
                    className="ws-create-textarea"
                    rows={3}
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="如：管理仓库库存、入库/出库记录、库存预警..."
                    data-testid="create-description"
                  />
                </div>
              </section>
            )}

            {step === 2 && (
              <section data-testid="create-panel-2">
                <h3 className="ws-create-panel-title">数据绑定</h3>
                <p className="ws-create-panel-desc">
                  选择本体中的对象类型作为数据源。Module 的 Widget 将通过 Object Set 引用这些数据。
                </p>

                <div className="ws-create-bind-row">
                  <div className="ws-create-bind-panel is-half">
                    <div className="ws-create-bind-head">本体对象类型</div>
                    <div className="ws-create-bind-body" data-testid="create-objtypes">
                      {OBJ_GROUPS.map((g) => (
                        <div key={g.title}>
                          <div className="ws-objtype-group-title">{g.title}</div>
                          {g.items.map((item) => (
                            <button
                              key={item.id}
                              type="button"
                              className={
                                objectType === item.id ? "ws-objtype-node is-selected" : "ws-objtype-node"
                              }
                              style={{ width: "100%", border: "none", background: "transparent", textAlign: "left" }}
                              data-testid={`create-obj-${item.id}`}
                              onClick={() => selectObject(item.id)}
                            >
                              {item.label}
                            </button>
                          ))}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="ws-create-bind-panel is-flex">
                    <div className="ws-create-bind-head">{objectType} 属性列表</div>
                    <div style={{ padding: 8 }}>
                      <div style={{ fontSize: 11, color: "var(--aos-text-secondary)", marginBottom: 6 }}>
                        勾选要展示的属性（自动绑定到 Widget）：
                      </div>
                      <div data-testid="create-props">
                        {OBJ_PROPS[objectType].map((p) => (
                          <button
                            key={p.name}
                            type="button"
                            className={boundProps.includes(p.name) ? "ws-prop-chip is-bound" : "ws-prop-chip"}
                            onClick={() => toggleProp(p.name)}
                          >
                            {p.name}
                          </button>
                        ))}
                      </div>
                    </div>
                    <div style={{ padding: "8px 12px", borderTop: "0.5px solid var(--aos-border)" }}>
                      <div style={{ fontSize: 11, color: "var(--aos-text-secondary)", marginBottom: 4 }}>
                        初始过滤条件（选填）
                      </div>
                      <div className="ws-create-filter-box">status != &quot;cancelled&quot;</div>
                    </div>
                  </div>
                </div>

                <div className="ws-warning-box">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path
                      d="M12 9v4M12 17h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                  <span>
                    当前用户对 {objectType} 对象有读取权限。写入操作需在创建后通过 Action 配置单独授权。
                  </span>
                </div>
              </section>
            )}

            {step === 3 && (
              <section data-testid="create-panel-3">
                <h3 className="ws-create-panel-title">模板选择</h3>
                <p className="ws-create-panel-desc">选择起始布局模板，系统将预填充 Widget 和变量。后续可自由增删修改。</p>

                <div className="ws-create-template-grid" data-testid="create-templates">
                  {TEMPLATES.map((t) => (
                    <button
                      key={t.id}
                      type="button"
                      className={template === t.id ? "ws-template-card is-selected" : "ws-template-card"}
                      style={{ textAlign: "left", width: "100%" }}
                      data-testid={`create-tpl-${t.id}`}
                      onClick={() => setTemplate(t.id)}
                    >
                      <TemplatePreview type={t.preview} />
                      <div className="ws-create-template-name">{t.name}</div>
                      <div className="ws-create-template-desc">{t.desc}</div>
                    </button>
                  ))}
                </div>

                <div className="ws-create-fill-box">
                  <div className="ws-create-fill-title">选中模板将预填充：</div>
                  <div className="ws-create-fill-body" style={{ whiteSpace: "pre-line" }}>
                    {selectedTemplate.fillHint}
                  </div>
                </div>
              </section>
            )}

            {step === 4 && (
              <section data-testid="create-panel-4">
                <h3 className="ws-create-panel-title">确认创建</h3>
                <p className="ws-create-panel-desc">请检查以下信息，确认后将创建 Module 并进入画布编辑器。</p>

                <div className="ws-create-summary">
                  <div className="ws-create-summary-head">Module 信息汇总</div>
                  <div className="ws-create-summary-body">
                    <table className="ws-create-summary-table" data-testid="create-summary">
                      <tbody>
                        <tr>
                          <td>模块名称</td>
                          <td style={{ fontWeight: 500 }}>{appName.trim() || "未填写"}</td>
                        </tr>
                        <tr>
                          <td>模块标识</td>
                          <td style={{ fontFamily: "monospace", color: "var(--aos-text-secondary)" }}>
                            {slug || "—"}
                          </td>
                        </tr>
                        <tr>
                          <td>模块图标</td>
                          <td>{selectedIcon.label}</td>
                        </tr>
                        <tr>
                          <td>业务域</td>
                          <td>
                            <span className="ws-create-badge-domain">{domain}</span>
                          </td>
                        </tr>
                        <tr>
                          <td>数据绑定</td>
                          <td>
                            {objLabel} · {boundProps.length} 个属性
                          </td>
                        </tr>
                        <tr>
                          <td>选中模板</td>
                          <td>{selectedTemplate.name}</td>
                        </tr>
                        <tr>
                          <td>创建后状态</td>
                          <td>
                            <span className="ws-create-badge-draft">Draft</span>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="ws-blue-box">
                  <div className="ws-blue-box-title">创建后将自动执行：</div>
                  <ul style={{ listStyle: "none", padding: 0, margin: 0, lineHeight: 1.8 }}>
                    <li>1. 创建 Module 资源（含 1 个 Layout + Widget）</li>
                    <li>2. 创建 Variables 并绑定 ObjectSet / Object</li>
                    <li>3. 创建 Event Handler（如模板需要）</li>
                    <li>4. 跳转到画布编辑器（可立即编辑界面）</li>
                  </ul>
                </div>
              </section>
            )}

            {/* 底部操作栏 — 对齐视觉稿：下一步始终可点 */}
            <div className="ws-create-footer">
              <div className="ws-create-step-indicator" data-testid="create-step-indicator">
                步骤 {step} / 4
              </div>
              <div className="ws-create-footer-actions">
                {step === 1 ? (
                  <Link to="/workshop" className="ws-back-btn" style={{ textDecoration: "none", display: "inline-flex", alignItems: "center" }}>
                    取消创建
                  </Link>
                ) : (
                  <button type="button" className="ws-back-btn" data-testid="create-btn-back" onClick={() => goStep(step - 1)}>
                    ← 上一步
                  </button>
                )}
                {step < 4 ? (
                  <button
                    type="button"
                    className="ws-next-btn"
                    data-testid="create-btn-next"
                    onClick={() => goStep(step + 1)}
                  >
                    下一步 →
                  </button>
                ) : (
                  <button
                    type="button"
                    className="ws-finish-btn"
                    data-testid="create-btn-finish"
                    disabled={creating}
                    onClick={() => void handleCreate()}
                  >
                    {creating ? "创建中…" : "创建并进入编辑 →"}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </PageChrome>
  );
}

/* ============================================================================
 * 子组件
 * ========================================================================== */

function IconSvg({ id, selected }: { id: IconId; selected: boolean }) {
  const stroke = selected ? "#0F6E56" : "#444441";
  const common = { width: 20, height: 20, viewBox: "0 0 24 24", fill: "none", stroke, strokeWidth: 1.5 } as const;
  switch (id) {
    case "box":
      return (
        <svg {...common}>
          <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "chart":
      return (
        <svg {...common}>
          <path d="M3 3v18h18M9 17V9M15 17V5M21 17v-4" strokeLinecap="round" />
        </svg>
      );
    case "alert":
      return (
        <svg {...common}>
          <path d="M12 9v4M12 17h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "users":
      return (
        <svg {...common}>
          <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2M9 11a4 4 0 100-8 4 4 0 000 8zM23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "globe":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="10" />
          <path d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "truck":
      return (
        <svg {...common}>
          <path d="M1 3h15v13H1zM16 8h4l3 3v5h-7V8z" strokeLinecap="round" strokeLinejoin="round" />
          <circle cx="5.5" cy="18.5" r="2.5" />
          <circle cx="18.5" cy="18.5" r="2.5" />
        </svg>
      );
  }
}

function TemplatePreview({ type }: { type: TemplateDef["preview"] }) {
  if (type === "blank") {
    return (
      <div className="ws-template-preview is-blank">
        <span className="ws-template-preview-blank-text">空白画布</span>
      </div>
    );
  }
  if (type === "table") {
    return (
      <div className="ws-template-preview">
        <div style={{ position: "absolute", top: 6, left: 6, right: 6, height: 18, background: "var(--aos-border-strong)", borderRadius: 2 }} />
        <div style={{ position: "absolute", top: 30, left: 6, right: 6, bottom: 6, background: "var(--aos-border-strong)", borderRadius: 2 }} />
      </div>
    );
  }
  if (type === "dashboard") {
    return (
      <div className="ws-template-preview">
        <div style={{ position: "absolute", top: 6, left: 6, width: 32, height: 28, background: "var(--aos-border-strong)", borderRadius: 2 }} />
        <div style={{ position: "absolute", top: 6, left: 44, width: 32, height: 28, background: "var(--aos-border-strong)", borderRadius: 2 }} />
        <div style={{ position: "absolute", top: 6, left: 82, width: 32, height: 28, background: "var(--aos-border-strong)", borderRadius: 2 }} />
        <div style={{ position: "absolute", top: 40, left: 6, right: 6, height: 28, background: "var(--aos-border-strong)", borderRadius: 2 }} />
      </div>
    );
  }
  return (
    <div className="ws-template-preview">
      <div style={{ position: "absolute", top: 6, left: 6, width: 40, bottom: 6, background: "var(--aos-border-strong)", borderRadius: 2 }} />
      <div style={{ position: "absolute", top: 6, left: 52, right: 6, height: 32, background: "var(--aos-border-strong)", borderRadius: 2 }} />
      <div style={{ position: "absolute", top: 44, left: 52, right: 6, bottom: 6, background: "var(--aos-border-strong)", borderRadius: 2 }} />
    </div>
  );
}
