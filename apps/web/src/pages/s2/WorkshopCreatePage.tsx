import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageChrome } from "../../components/PageChrome";
import { BpCard } from "../../components/bp/BpCard";
import { BpStepper, type BpStep } from "../../components/bp/BpStepper";
import { apiPost } from "../../api/client";

const STEPS: BpStep[] = [
  { key: "basic", title: "基本信息", description: "填写应用名称与类型" },
  { key: "data", title: "数据绑定", description: "选择应用访问的数据源" },
  { key: "template", title: "模板选择", description: "选择初始化模板" },
  { key: "confirm", title: "确认创建", description: "核对信息并创建" },
];

const ICONS = [
  {
    id: "box",
    name: "立方体",
    svg: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    id: "chart",
    name: "图表",
    svg: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M3 3v18h18M9 17V9M15 17V5M21 17v-4" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    id: "alert",
    name: "告警",
    svg: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M12 9v4M12 17h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    id: "users",
    name: "用户",
    svg: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2M9 11a4 4 0 100-8 4 4 0 000 8zM23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    id: "globe",
    name: "地球",
    svg: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <circle cx="12" cy="12" r="10" />
        <path d="M2 12h20M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    id: "truck",
    name: "卡车",
    svg: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
        <path d="M1 3h15v13H1zM16 8h4l3 3v5h-7V8z" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="5.5" cy="18.5" r="2.5" />
        <circle cx="18.5" cy="18.5" r="2.5" />
      </svg>
    ),
  },
];

const DOMAINS = ["运营", "分析", "风控", "供应链", "客服", "自定义"];

const OBJ_TYPE_GROUPS = [
  {
    title: "业务对象",
    items: [
      { id: "Order", name: "Order（订单）", icon: "order" },
      { id: "Product", name: "Product（商品）", icon: "box" },
      { id: "Inventory", name: "Inventory（库存）", icon: "grid" },
      { id: "RiskAlert", name: "RiskAlert（风险告警）", icon: "alert" },
    ],
  },
  {
    title: "用户对象",
    items: [
      { id: "Customer", name: "Customer（客户）", icon: "users" },
      { id: "Supplier", name: "Supplier（供应商）", icon: "truck" },
    ],
  },
];

const PROPS_MAP: Record<string, string[]> = {
  Order: ["order_id", "customer_name", "total_amount", "status", "created_at", "shipping_address", "payment_method", "discount_code", "tax_amount", "remark"],
  Product: ["product_id", "sku", "name", "category", "price", "stock", "description", "image_url", "created_at", "updated_at"],
  Inventory: ["inv_id", "warehouse", "product_id", "quantity", "min_stock", "max_stock", "last_check", "location", "status", "remark"],
  RiskAlert: ["alert_id", "type", "severity", "status", "source", "message", "triggered_at", "resolved_at", "assignee", "remark"],
  Customer: ["customer_id", "name", "email", "phone", "level", "address", "created_at", "last_order_at", "total_spent", "tags"],
  Supplier: ["supplier_id", "name", "contact", "phone", "email", "address", "rating", "cooperation_since", "payment_terms", "remark"],
};

const TEMPLATES = [
  {
    id: "blank",
    name: "空白模板",
    desc: "零预填 Widget，完全从零搭建。适合高度自定义场景。",
    blank: true,
  },
  {
    id: "table",
    name: "表格列表模板",
    desc: "筛选栏 + 数据表格 + 详情面板。适合 CRUD 管理场景，如订单管理。",
    preview: "table",
  },
  {
    id: "dashboard",
    name: "仪表盘模板",
    desc: "统计卡片 x4 + 趋势图 + 饼图。适合数据监控和概览场景。",
    preview: "dashboard",
  },
  {
    id: "explorer",
    name: "对象探索模板",
    desc: "对象列表 + 属性筛选 + 图表探索 + Actions。适合 Ontology 数据探索。",
    preview: "explorer",
  },
];

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fa5]/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}

function ObjIcon({ type }: { type: string }) {
  const common = { width: 14, height: 14, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.5 };
  switch (type) {
    case "order":
      return (
        <svg {...common}>
          <path d="M4 13h4l2 3h4l2-3h4v6H4v-6zM4 13l2-8h12l2 8" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "box":
      return (
        <svg {...common}>
          <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "grid":
      return (
        <svg {...common}>
          <rect x="3" y="3" width="7" height="7" rx="1" />
          <rect x="14" y="3" width="7" height="7" rx="1" />
          <rect x="3" y="14" width="7" height="7" rx="1" />
          <rect x="14" y="14" width="7" height="7" rx="1" />
        </svg>
      );
    case "alert":
      return (
        <svg {...common}>
          <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "users":
      return (
        <svg {...common}>
          <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2M9 11a4 4 0 100-8 4 4 0 000 8z" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    case "truck":
      return (
        <svg {...common}>
          <path d="M1 3h15v13H1zM16 8h4l3 3v5h-7V8z" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      );
    default:
      return null;
  }
}

function TemplatePreview({ type, blank }: { type?: string; blank?: boolean }) {
  if (blank) {
    return (
      <div className="ws-template-preview is-blank">
        <span className="ws-template-preview-blank-text">空白画布</span>
      </div>
    );
  }
  if (type === "table") {
    return (
      <div className="ws-template-preview">
        <div style={{ position: "absolute", top: 6, left: 6, right: 6, height: 18, background: "var(--aos-border)", borderRadius: 2 }} />
        <div style={{ position: "absolute", top: 30, left: 6, right: 6, bottom: 6, background: "var(--aos-border)", borderRadius: 2 }} />
      </div>
    );
  }
  if (type === "dashboard") {
    return (
      <div className="ws-template-preview">
        <div style={{ position: "absolute", top: 6, left: 6, width: 32, height: 28, background: "var(--aos-border)", borderRadius: 2 }} />
        <div style={{ position: "absolute", top: 6, left: 44, width: 32, height: 28, background: "var(--aos-border)", borderRadius: 2 }} />
        <div style={{ position: "absolute", top: 6, left: 82, width: 32, height: 28, background: "var(--aos-border)", borderRadius: 2 }} />
        <div style={{ position: "absolute", top: 40, left: 6, right: 6, height: 28, background: "var(--aos-border)", borderRadius: 2 }} />
      </div>
    );
  }
  if (type === "explorer") {
    return (
      <div className="ws-template-preview">
        <div style={{ position: "absolute", top: 6, left: 6, width: 40, bottom: 6, background: "var(--aos-border)", borderRadius: 2 }} />
        <div style={{ position: "absolute", top: 6, left: 52, right: 6, height: 32, background: "var(--aos-border)", borderRadius: 2 }} />
        <div style={{ position: "absolute", top: 44, left: 52, right: 6, bottom: 6, background: "var(--aos-border)", borderRadius: 2 }} />
      </div>
    );
  }
  return <div className="ws-template-preview" />;
}

export function WorkshopCreatePage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [appName, setAppName] = useState("");
  const [appDescription, setAppDescription] = useState("");
  const appType = "dashboard";
  const [selectedTemplate, setSelectedTemplate] = useState("table");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [icon, setIcon] = useState("box");
  const [domain, setDomain] = useState("供应链");
  const [selectedObjType, setSelectedObjType] = useState("Order");
  const [boundProps, setBoundProps] = useState<string[]>(["order_id", "customer_name", "total_amount", "status", "created_at"]);

  const slug = useMemo(() => slugify(appName), [appName]);

  const currentProps = PROPS_MAP[selectedObjType] ?? [];

  function toggleProp(prop: string) {
    setBoundProps((prev) =>
      prev.includes(prop) ? prev.filter((p) => p !== prop) : [...prev, prop],
    );
  }

  function handleObjTypeChange(objId: string) {
    setSelectedObjType(objId);
    setBoundProps(PROPS_MAP[objId]?.slice(0, 5) ?? []);
  }

  async function handleCreate() {
    if (!appName.trim()) {
      setError("请输入应用名称");
      return;
    }
    setError(null);
    setCreating(true);
    try {
      const result = await apiPost<{ module_id: string }>("/v1/modules", {
        name: appName,
        description: appDescription,
        type: appType,
        data_sources: [selectedObjType],
        template: selectedTemplate,
        icon,
        domain,
        slug,
      });
      setCreating(false);
      navigate(`/workshop/canvas?module=${result.module_id}`);
    } catch (e) {
      setError(String((e as Error).message || e));
      setCreating(false);
    }
  }

  const canNextFromStep1 = !!appName.trim();
  const selectedTemplateData = TEMPLATES.find((t) => t.id === selectedTemplate);
  const selectedIconData = ICONS.find((i) => i.id === icon);

  return (
    <PageChrome title="创建应用" lede="4 步创建新的 Workshop 应用">
      <div style={{ maxWidth: 900, margin: "0 auto", padding: "24px 0" }}>
        <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: 32, alignItems: "start" }}>
          <BpStepper steps={STEPS} current={step - 1} />

          <div>
            {error && (
              <div
                role="alert"
                style={{
                  background: "var(--aos-red-bg)",
                  color: "var(--aos-red)",
                  padding: "8px 12px",
                  borderRadius: 4,
                  marginBottom: 12,
                  fontSize: 13,
                  border: "1px solid var(--aos-red-border)",
                }}
              >
                {error}
              </div>
            )}

            {step === 1 && (
              <BpCard title="基本信息" subtitle="设置模块名称、图标和业务域，创建后仍可修改。">
                <FormGrid>
                  <FieldLabel required>模块名称</FieldLabel>
                  <input
                    className="bp-cron-input"
                    style={{ height: 36, fontFamily: "inherit", fontSize: 13, padding: "0 12px" }}
                    value={appName}
                    onChange={(e) => setAppName(e.target.value)}
                    placeholder="如：库存管理系统"
                  />

                  <FieldLabel>
                    模块标识 <span style={{ fontSize: 11, color: "var(--aos-text-secondary)", fontWeight: 400 }}>（自动生成，用于 API 引用）</span>
                  </FieldLabel>
                  <input
                    className="ws-slug-input"
                    value={slug}
                    readOnly
                    placeholder="inventory-mgmt"
                  />

                  <FieldLabel>
                    模块图标 <span style={{ fontSize: 11, color: "var(--aos-text-secondary)", fontWeight: 400 }}>（选择一个）</span>
                  </FieldLabel>
                  <div style={{ display: "flex", gap: 8 }}>
                    {ICONS.map((i) => (
                      <div
                        key={i.id}
                        className={icon === i.id ? "ws-icon-pick is-selected" : "ws-icon-pick"}
                        onClick={() => setIcon(i.id)}
                        role="button"
                        tabIndex={0}
                        aria-label={`选择图标 ${i.name}`}
                        style={{ color: icon === i.id ? "var(--aos-accent)" : "var(--aos-text)" }}
                      >
                        {i.svg}
                      </div>
                    ))}
                  </div>

                  <FieldLabel>
                    业务域 <span style={{ fontSize: 11, color: "var(--aos-text-secondary)", fontWeight: 400 }}>（选择一个）</span>
                  </FieldLabel>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {DOMAINS.map((d) => (
                      <span
                        key={d}
                        className={domain === d ? "ws-domain-chip is-selected" : "ws-domain-chip"}
                        onClick={() => setDomain(d)}
                        role="button"
                        tabIndex={0}
                      >
                        {d}
                      </span>
                    ))}
                  </div>

                  <FieldLabel>
                    用途描述 <span style={{ fontSize: 11, color: "var(--aos-text-secondary)", fontWeight: 400 }}>（一句话说明，选填）</span>
                  </FieldLabel>
                  <textarea
                    value={appDescription}
                    onChange={(e) => setAppDescription(e.target.value)}
                    placeholder="如：管理仓库库存、入库/出库记录、库存预警..."
                    rows={3}
                    className="bp-code-editor-textarea"
                    style={{ minHeight: 70, fontSize: 13 }}
                  />
                </FormGrid>
                <StepFooter
                  onCancel={() => navigate("/workshop")}
                  onNext={() => canNextFromStep1 && setStep(2)}
                  nextDisabled={!canNextFromStep1}
                />
              </BpCard>
            )}

            {step === 2 && (
              <BpCard title="数据绑定" subtitle="选择本体中的对象类型作为数据源。Module 的 Widget 将通过 Object Set 引用这些数据。">
                <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
                  <div style={{ width: "50%", border: "0.5px solid var(--aos-border-strong)", borderRadius: 8, overflow: "hidden", background: "var(--aos-card)" }}>
                    <div style={{ padding: "8px 12px", background: "var(--aos-surface-hover)", borderBottom: "0.5px solid var(--aos-border-strong)", fontSize: 12, fontWeight: 500, color: "var(--aos-text)" }}>
                      本体对象类型
                    </div>
                    <div style={{ padding: 6, maxHeight: 280, overflowY: "auto" }}>
                      {OBJ_TYPE_GROUPS.map((group) => (
                        <div key={group.title}>
                          <div className="ws-objtype-group-title">{group.title}</div>
                          {group.items.map((item) => (
                            <div
                              key={item.id}
                              className={selectedObjType === item.id ? "ws-objtype-node is-selected" : "ws-objtype-node"}
                              onClick={() => handleObjTypeChange(item.id)}
                              role="button"
                              tabIndex={0}
                            >
                              <ObjIcon type={item.icon} />
                              {item.name}
                            </div>
                          ))}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div style={{ flex: 1, border: "0.5px solid var(--aos-border-strong)", borderRadius: 8, overflow: "hidden", background: "var(--aos-card)", display: "flex", flexDirection: "column" }}>
                    <div style={{ padding: "8px 12px", background: "var(--aos-surface-hover)", borderBottom: "0.5px solid var(--aos-border-strong)", fontSize: 12, fontWeight: 500, color: "var(--aos-text)" }}>
                      {selectedObjType} 属性列表
                    </div>
                    <div style={{ padding: 8, flex: 1 }}>
                      <div style={{ fontSize: 11, color: "var(--aos-text-secondary)", marginBottom: 6 }}>
                        勾选要展示的属性（自动绑定到 Widget）：
                      </div>
                      <div>
                        {currentProps.map((prop) => (
                          <span
                            key={prop}
                            className={boundProps.includes(prop) ? "ws-prop-chip is-bound" : "ws-prop-chip"}
                            onClick={() => toggleProp(prop)}
                            role="button"
                            tabIndex={0}
                          >
                            {prop}
                          </span>
                        ))}
                      </div>
                    </div>
                    <div style={{ padding: "8px 12px", borderTop: "0.5px solid var(--aos-surface-hover)" }}>
                      <div style={{ fontSize: 11, color: "var(--aos-text-secondary)", marginBottom: 4 }}>初始过滤条件（选填）</div>
                      <div style={{ fontSize: 11, color: "var(--aos-text)", background: "var(--aos-surface-hover)", padding: "6px 8px", borderRadius: 4, fontFamily: "monospace" }}>
                        status != "cancelled"
                      </div>
                    </div>
                  </div>
                </div>

                <div className="ws-warning-box">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M12 9v4M12 17h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                  <span>当前用户对 {selectedObjType} 对象有读取权限。写入操作需在创建后通过 Action 配置单独授权。</span>
                </div>

                <StepFooter
                  onPrev={() => setStep(1)}
                  onNext={() => setStep(3)}
                />
              </BpCard>
            )}

            {step === 3 && (
              <BpCard title="模板选择" subtitle="选择起始布局模板，系统将预填充 Widget 和变量。后续可自由增删修改。">
                <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 14 }}>
                  {TEMPLATES.map((t) => {
                    const selected = selectedTemplate === t.id;
                    return (
                      <div
                        key={t.id}
                        className={selected ? "ws-template-card is-selected" : "ws-template-card"}
                        onClick={() => setSelectedTemplate(t.id)}
                        role="button"
                        tabIndex={0}
                      >
                        <TemplatePreview type={t.preview} blank={t.blank} />
                        <div style={{ fontSize: 13, fontWeight: 500, color: "var(--aos-text)", marginBottom: 4 }}>{t.name}</div>
                        <div style={{ fontSize: 11, color: "var(--aos-text-secondary)", lineHeight: 1.5 }}>{t.desc}</div>
                      </div>
                    );
                  })}
                </div>

                <div className="ws-info-box" style={{ marginTop: 16 }}>
                  <div className="ws-info-box-title">选中模板将预填充：</div>
                  <div>
                    1 个 Layout（首页） · 3 个 Widget（FilterBar + DataTable + DetailPanel）<br />
                    2 个 Variables（all_orders: ObjectSet, selected_order: Object）<br />
                    1 个 Event（onRowClick → selected_order.setValue）
                  </div>
                </div>

                <StepFooter
                  onPrev={() => setStep(2)}
                  onNext={() => setStep(4)}
                />
              </BpCard>
            )}

            {step === 4 && (
              <BpCard title="确认创建" subtitle="请检查以下信息，确认后将创建 Module 并进入画布编辑器。">
                <div style={{ border: "0.5px solid var(--aos-border-strong)", borderRadius: 8, overflow: "hidden", background: "var(--aos-card)", marginBottom: 16 }}>
                  <div style={{ padding: "12px 16px", background: "var(--aos-surface-hover)", borderBottom: "0.5px solid var(--aos-border-strong)", fontSize: 12, fontWeight: 500, color: "var(--aos-text)" }}>
                    Module 信息汇总
                  </div>
                  <div style={{ padding: 16 }}>
                    <table className="ws-summary-table">
                      <tbody>
                        <tr>
                          <td>模块名称</td>
                          <td style={{ fontWeight: 500 }}>{appName || "未设置"}</td>
                        </tr>
                        <tr>
                          <td>模块标识</td>
                          <td style={{ fontFamily: "monospace", color: "var(--aos-text-secondary)" }}>{slug || "未生成"}</td>
                        </tr>
                        <tr>
                          <td>模块图标</td>
                          <td style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <span style={{ color: "var(--aos-accent)" }}>{selectedIconData?.svg}</span>
                            {selectedIconData?.name}
                          </td>
                        </tr>
                        <tr>
                          <td>业务域</td>
                          <td>
                            <span className="ws-summary-badge domain">{domain}</span>
                          </td>
                        </tr>
                        <tr>
                          <td>数据绑定</td>
                          <td>
                            {selectedObjType} · {boundProps.length} 个属性
                          </td>
                        </tr>
                        <tr>
                          <td>选中模板</td>
                          <td>{selectedTemplateData?.name}</td>
                        </tr>
                        <tr>
                          <td>创建后状态</td>
                          <td>
                            <span className="ws-summary-badge draft">Draft</span>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="ws-blue-box">
                  <div className="ws-blue-box-title">创建后将自动执行：</div>
                  <ul>
                    <li>1. 创建 Module 资源（含 1 个 Layout + 3 个 Widget）</li>
                    <li>2. 创建 2 个 Variables 并绑定 ObjectSet / Object</li>
                    <li>3. 创建 1 个 Event Handler</li>
                    <li>4. 跳转到画布编辑器（可立即编辑界面）</li>
                  </ul>
                </div>

                <StepFooter
                  onPrev={() => setStep(3)}
                  onNext={handleCreate}
                  nextDisabled={creating}
                  nextLabel={creating ? "创建中…" : "创建并进入编辑 →"}
                  center
                />
              </BpCard>
            )}
          </div>
        </div>
      </div>
    </PageChrome>
  );
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
        borderTop: "1px solid var(--aos-divider)",
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
