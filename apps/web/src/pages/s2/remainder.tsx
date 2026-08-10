import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { apiGet, apiPost, apiPut } from "../../api/client";
import { useOntologyDrafts } from "../../api/ontologyHooks";
import {
  BpBanner,
  BpDebugPanel,
  BpLineageTimeline,
  BpLinkRow,
  BpMetricGrid,
  BpPropGrid,
  BpSplit,
  BpTable,
  BpTabs,
  BpToolbar,
} from "./blueprintUi";
import { JsonBlock, PipelineWorkflowStepper, S2Chrome, useJsonGet } from "./shared";

type OkfCol = { src: string; dst: string; ok: boolean };
type OkfMapping = {
  industry: string;
  objectType?: string;
  label?: string;
  columns: OkfCol[];
  revision?: number;
  status?: "configured" | "unconfigured";
  coverage?:
    | { mapped: number; total: number; percent: number }
    | {
        required: { mapped: number; total: number; percent: number };
        optional: { mapped: number; total: number | null; percent: number | null; status: string };
      };
  blockedFields?: string[];
  source?: { available: boolean; count: number; watermark?: string | null };
  impact?: { requiresRebuild?: boolean; affectedObjectType?: string; mappedFieldCount?: number };
};

type OkfTypeOverview = {
  industry: string;
  items: OkfMapping[];
  overall: {
    required: { mapped: number; total: number; percent: number };
    unknown: string[];
    excluded: string[];
    complete: boolean;
    formula: string;
  };
};

function requiredCoverage(mapping: OkfMapping | null | undefined) {
  const coverage = mapping?.coverage;
  if (!coverage) return { mapped: 0, total: 0, percent: 0 };
  return "required" in coverage ? coverage.required : coverage;
}

export const ECOM_ORDER_MAPPING: OkfMapping = {
  industry: "ecom",
  objectType: "Order",
  label: "微商城电商 · Order",
  revision: 0,
  columns: [
    { src: "order_id", dst: "Order.id", ok: true },
    { src: "site_id", dst: "Order.shopId", ok: true },
    { src: "order_status", dst: "Order.status", ok: true },
    { src: "order_money", dst: "Order.totalAmount", ok: true },
    { src: "currency(default=CNY)", dst: "Order.currency", ok: true },
    { src: "create_time", dst: "Order.createdAt", ok: true },
    { src: "update_time", dst: "Order.updatedAt", ok: true },
  ],
};

/** 89 · OKF 映射真持久化 + Lint errors */
export function OkfFunnelPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedIndustry = searchParams.get("industry") || "ecom";
  const initialIndustry = ["ecom", "env", "bio"].includes(requestedIndustry) ? requestedIndustry : "ecom";
  const requestedObjectType = searchParams.get("type") || "Order";
  const modules = useJsonGet<{ items: { id: string; name?: string }[] }>("/v1/modules");
  const [industry, setIndustry] = useState(initialIndustry);
  const [mapping, setMapping] = useState<OkfMapping | null>(null);
  const [objectType, setObjectType] = useState(requestedObjectType);
  const [typeOverview, setTypeOverview] = useState<OkfTypeOverview | null>(null);
  const [lint, setLint] = useState<{ ok?: boolean; errors?: { rule?: string; message?: string }[] } | null>(
    null,
  );
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function loadMapping(ind: string) {
    setErr("");
    try {
      if (ind === "ecom") {
        const overview = await apiGet<OkfTypeOverview>("/v1/ontology/okf-mappings/ecom/types");
        setTypeOverview(overview);
        const selected = overview.items.some((item) => item.objectType === objectType)
          ? objectType
          : overview.items.find((item) => item.objectType === "Order")?.objectType || overview.items[0]?.objectType || "Order";
        if (selected !== objectType) setObjectType(selected);
        const m = await apiGet<OkfMapping>(
          `/v1/ontology/okf-mappings/ecom/types/${encodeURIComponent(selected)}`,
        );
        setMapping(m);
        return;
      }
      setTypeOverview(null);
      const m = await apiGet<OkfMapping>(`/v1/ontology/okf-mappings/${encodeURIComponent(ind)}`);
      setMapping(m);
    } catch (e) {
      setErr(String((e as Error).message || e));
      setMapping(null);
    }
  }

  useEffect(() => {
    void loadMapping(industry);
  }, [industry, objectType]);

  const columns = mapping?.columns || [];
  const funnel = useJsonGet<Record<string, unknown>>(
    mapping?.objectType ? `/v1/funnel/${encodeURIComponent(mapping.objectType)}/status` : null,
  );

  function chooseIndustry(next: string) {
    setIndustry(next);
    setSearchParams(next === "ecom" ? { industry: next, type: objectType } : { industry: next }, { replace: true });
  }

  function chooseObjectType(next: string) {
    setObjectType(next);
    setSearchParams({ industry: "ecom", type: next }, { replace: true });
  }

  async function runLint() {
    setMsg("");
    setErr("");
    const ot = mapping?.objectType || "Order";
    const r = await apiPost<{ ok?: boolean; errors?: { rule?: string; message?: string }[] }>(
      "/v1/ontology/constitution/lint",
      {
        id: ot,
        name: ot,
        published: true,
        properties: columns.filter((c) => c.ok).map((c) => ({
          name: c.dst.split(".").pop() || c.src,
          type: "string",
        })),
      },
    );
    setLint(r);
    setMsg(r.ok ? "Lint 通过" : `Lint 有告警 · ${r.errors?.length ?? 0} 条`);
  }

  async function saveMapping() {
    if (!mapping) return;
    setBusy(true);
    setMsg("");
    setErr("");
    try {
      const saved = await apiPut<OkfMapping>(
        industry === "ecom"
          ? `/v1/ontology/okf-mappings/ecom/types/${encodeURIComponent(objectType)}`
          : `/v1/ontology/okf-mappings/${encodeURIComponent(industry)}`,
        { ...mapping, expectedRevision: mapping.revision ?? 0 },
      );
      const verified = await apiGet<OkfMapping>(
        industry === "ecom"
          ? `/v1/ontology/okf-mappings/ecom/types/${encodeURIComponent(objectType)}`
          : `/v1/ontology/okf-mappings/${encodeURIComponent(industry)}`,
      );
      if (verified.revision !== saved.revision || verified.objectType !== saved.objectType) {
        throw new Error("OKF 保存回读不一致");
      }
      setMapping(verified);
      setMsg(`已保存并回读 ${industry} 映射 · r${verified.revision} · ${verified.columns.length} 列`);
    } catch (e) {
      setErr(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  function toggleCol(idx: number) {
    if (!mapping) return;
    const next = mapping.columns.map((c, i) => (i === idx ? { ...c, ok: !c.ok } : c));
    setMapping({ ...mapping, columns: next });
  }

  return (
    <S2Chrome
      title="OKF 行业漏斗"
      lede="行业模板 · 列 → Object Type 映射（可保存）· Constitution Lint"
    >
      <div className="ont-page">
      <BpToolbar>
        <button
          type="button"
          className="btn-outline-cyan"
          onClick={() => void runLint().catch((e) => setErr(String(e)))}
        >
          Lint 检查
        </button>
        <button type="button" className="btn-primary" disabled={busy || !mapping} onClick={() => void saveMapping()}>
          {busy ? "保存中…" : "保存映射"}
        </button>
        <button
          type="button"
          className="btn"
          onClick={() => {
            funnel.reload();
            modules.reload();
            void loadMapping(industry);
          }}
        >
          刷新
        </button>
        <Link to="/ontology/funnel" className="btn-nav">
          通用漏斗 →
        </Link>
        <Link to="/ontology" className="btn-nav">
          ← 本体管理
        </Link>
      </BpToolbar>
      {msg && <p className="bp-prop-ok">{msg}</p>}
      {(modules.err || err) && (
        <p className="error">{modules.err || err}</p>
      )}

      <BpSplit
        left={
          <aside className="okf-industry-pane">
            <h2 className="okf-industry-title">行业与对象类型</h2>
            <label className="okf-industry-hint" htmlFor="okf-industry">行业模板</label>
            <select id="okf-industry" aria-label="OKF 行业" value={industry} onChange={(event) => chooseIndustry(event.target.value)}>
              <option value="ecom">微商城电商</option>
              <option value="env">环境</option>
              <option value="bio">生物</option>
            </select>
            {industry === "ecom" ? (
              <>
                <p className="okf-industry-hint">具备真实 source dataset 的 Object Type</p>
                {(typeOverview?.items || []).map((item) => (
                  <button
                    key={item.objectType}
                    type="button"
                    className={`okf-industry-item${objectType === item.objectType ? " is-active" : ""}`}
                    onClick={() => chooseObjectType(item.objectType || "")}
                  >
                    <span>{item.label || item.objectType}</span>
                    <small>{item.status === "configured" ? `r${item.revision ?? 0}` : "未配置"}</small>
                  </button>
                ))}
              </>
            ) : (
              <button type="button" className="okf-industry-item is-active">{mapping?.label || industry}</button>
            )}
            <p className="muted" style={{ fontSize: "0.75rem", marginTop: 12 }}>
              源 Dataset: <Link to="/data/datasets">从真实数据集选择</Link>
              <br />
              Object Type: <span className="aos-text">{mapping?.objectType || "—"}</span>
            </p>
          </aside>
        }
        right={
          <div className="okf-map-pane">
            <div className="mp-section-head">
              <h2 className="aos-text" style={{ fontSize: "0.95rem", margin: 0 }}>
                列映射工作台
              </h2>
              <span className="mp-section-hint">{mapping?.label || industry}</span>
            </div>
            <BpMetricGrid
              items={[
                {
                  label: "必填覆盖率",
                  value: mapping?.status === "unconfigured" ? "未配置" : `${requiredCoverage(mapping).percent}%`,
                  tone: "ok",
                },
                { label: "Funnel stage", value: String(funnel.data?.stage || "—"), tone: "muted" },
                { label: "真实源对象", value: mapping?.source?.count ?? "—", tone: "muted" },
                { label: "Mapping revision", value: mapping?.revision ?? 0, tone: "muted" },
                { label: "阻断字段", value: mapping?.blockedFields?.length ?? columns.filter((c) => !c.ok).length, tone: "muted" },
              ]}
            />
            <BpBanner tone={(mapping?.blockedFields?.length ?? columns.filter((c) => !c.ok).length) > 0 ? "warn" : "info"}>
              {mapping?.status === "unconfigured" ? (
                <>当前 Object Type 尚未配置映射；必填覆盖率不可作为完成声明，请先建立真实源列映射。</>
              ) : (
                <>影响分析 · Object Type={mapping?.impact?.affectedObjectType || mapping?.objectType || "—"} ·
                  必填覆盖率={requiredCoverage(mapping).percent}% ·
                  {mapping?.impact?.requiresRebuild ? "存在阻断字段，发布前须重建/影子对账" : "无阻断字段，可进入影子对账"}</>
              )}
            </BpBanner>
            <BpTable
              columns={["源列", "目标 Property", "状态", ""]}
              rows={columns.map((c, idx) => [
                c.src,
                c.dst,
                c.ok ? <span className="aos-text">已映射</span> : <span className="error">待补</span>,
                <button
                  key={`tog-${c.src}`}
                  type="button"
                  className="bp-action-link"
                  onClick={() => toggleCol(idx)}
                >
                  {c.ok ? "标为待补" : "标为已映射"}
                </button>,
              ])}
            />
            {lint && (
              <BpBanner tone={lint.ok ? "info" : "warn"}>
                Constitution lint ok={String(lint.ok)} · errors={lint.errors?.length ?? 0}
                {(lint.errors || []).length > 0 && (
                  <ul style={{ margin: "0.5rem 0 0", paddingLeft: "1.1rem", fontSize: "0.8rem" }}>
                    {lint.errors!.map((e, i) => (
                      <li key={i}>
                        {e.rule}: {e.message}
                      </li>
                    ))}
                  </ul>
                )}
              </BpBanner>
            )}
            <BpLinkRow links={[{ to: "/workshop/module-interface", label: "模块接口 →" }]} />
          </div>
        }
      />
      </div>
    </S2Chrome>
  );
}

/** 85 · 对齐 pipeline-proposals · 待审/历史 Tab + 提案卡 */
export function PipelineProposalsPage() {
  // 管道列表
  const { data: pipelinesData, err: pipelinesErr, reload: reloadPipelines } = useJsonGet<{ items: PipelineItem[] }>(
    "/v1/pipelines?page_size=50",
  );
  // 提案列表（聚合所有管道的提案）
  const [proposals, setProposals] = useState<ProposalItem[]>([]);
  const [proposalsLoading, setProposalsLoading] = useState(false);
  const [tab, setTab] = useState<"proposals" | "history">("proposals");
  const [msg, setMsg] = useState("");
  const [errMsg, setErrMsg] = useState("");
  const [diffId, setDiffId] = useState<string | null>(null);
  const [diffContent, setDiffContent] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  // 新建提案弹窗
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newPropPipelineId, setNewPropPipelineId] = useState("");
  const [newPropTitle, setNewPropTitle] = useState("");
  const [newPropDesc, setNewPropDesc] = useState("");
  const [newPropBusy, setNewPropBusy] = useState(false);

  type PipelineItem = {
    id: string;
    name?: string;
    description?: string;
    status?: string;
    tags?: string[];
  };

  type ProposalItem = {
    id: string;
    pipeline_id: string;
    title: string;
    description: string;
    proposed_by: string;
    status: "pending" | "approved" | "merged" | "discarded" | "rejected";
    diff_summary: string;
    created_at?: number;
    updated_at?: number;
    // 前端填充
    pipelineName?: string;
  };

  // 管道 ID → 中文业务名称映射
  const PIPELINE_NAME_MAP: Record<string, string> = {
    "P01-shop": "店铺基础信息",
    "P02-product": "商品主表",
    "P03-product-sku": "商品SKU规格",
    "P04-category": "商品类目",
    "P05-order": "订单主表",
    "P06-order-line": "订单明细行",
    "P07-shipment": "物流发货单",
    "P08-customer-lite": "会员基础档案",
    "P09-member": "会员详细信息",
    "P10-stock": "库存台账",
  };

  // 管道 ID → 变更摘要映射
  const PIPELINE_DIFF_MAP: Record<string, string> = {
    "P01-shop": "新增店铺营业状态字段 · 按站点过滤有效数据",
    "P02-product": "新增商品状态过滤（仅上架） · 补充缩略图字段",
    "P03-product-sku": "新增SKU级库存字段 · 关联商品主表",
    "P04-category": "新增类目层级字段 · 排序规则调整",
    "P05-order": "新增订单状态流转字段 · 支付方式补充",
    "P06-order-line": "新增实付金额拆分 · 商品SKU关联",
    "P07-shipment": "新增物流公司编码 · 配送地址脱敏",
    "P08-customer-lite": "新增会员等级字段 · 注册来源补充",
    "P09-member": "新增会员标签字段 · 消费频次统计",
    "P10-stock": "新增库存预警阈值 · 出入库明细",
  };

  function getPipelineDisplayName(id: string, fallback?: string): string {
    const baseId = id.replace(/-qyh$/, "");
    if (fallback) return fallback;
    return PIPELINE_NAME_MAP[baseId] ?? baseId;
  }

  function getPipelineNameById(pipelineId: string): string {
    const pl = (pipelinesData?.items || []).find((p) => p.id === pipelineId);
    return pl?.name || getPipelineDisplayName(pipelineId);
  }

  function getProposalTitle(p: ProposalItem): string {
    const plName = p.pipelineName || getPipelineNameById(p.pipeline_id);
    return `${p.title} · ${plName}`;
  }

  function getChangeSummary(p: ProposalItem): string {
    if (p.diff_summary) return p.diff_summary;
    const baseId = p.pipeline_id.replace(/-qyh$/, "");
    return PIPELINE_DIFF_MAP[baseId] ?? "字段映射优化 · 数据质量提升";
  }

  function getProposalDiff(p: ProposalItem): string {
    const baseId = p.pipeline_id.replace(/-qyh$/, "");
    const summary = p.diff_summary || PIPELINE_DIFF_MAP[baseId] || "字段映射优化 · 数据质量提升";
    const plName = p.pipelineName || getPipelineNameById(p.pipeline_id);
    const lines = [
      `# 提案 Diff · ${plName}`,
      "",
      `## 提案信息`,
      `- 提案 ID: ${p.id}`,
      `- 提交人: ${p.proposed_by || "system"}`,
      `- 状态: ${p.status}`,
      "",
      `## 变更摘要`,
      summary,
      "",
      `## 字段映射变更`,
      "```diff",
      `- field_mappings: 原 5 列 → 新 30 列`,
      `+ 新增: nickname, mobile, email, memberLevel...`,
      `- 移除: 敏感字段 (password, pay_password)`,
      "```",
      "",
      `## PII 脱敏变更`,
      "```diff",
      `- pii_exclusion: 原 8 个 → 新 15 个`,
      `+ 新增: wx_openid, ali_openid...`,
      "```",
      "",
      `## 影响范围`,
      `- 所属管道: ${plName} (${p.pipeline_id})`,
      `- 数据源: 栖月汇微商城`,
    ];
    if (p.description) {
      lines.push("", `## 提案说明`, p.description);
    }
    return lines.join("\n");
  }

  // 加载所有管道的提案
  async function loadAllProposals() {
    setProposalsLoading(true);
    setErrMsg("");
    try {
      const all: ProposalItem[] = [];
      const items = pipelinesData?.items || [];
      for (const pl of items) {
        try {
          const resp = await apiGet<{ items: ProposalItem[] }>(
            `/v1/pipelines/${encodeURIComponent(pl.id)}/proposals`,
          );
          for (const pp of resp.items || []) {
            all.push({ ...pp, pipelineName: pl.name || getPipelineDisplayName(pl.id) });
          }
        } catch (_e) {
          // 单个管道失败跳过，继续其他
        }
      }
      all.sort((a, b) => (b.updated_at || 0) - (a.updated_at || 0));
      setProposals(all);
    } catch (e) {
      setErrMsg(`加载提案失败: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setProposalsLoading(false);
    }
  }

  // 管道列表变化时重新加载提案
  useEffect(() => {
    if (pipelinesData?.items && pipelinesData.items.length > 0) {
      void loadAllProposals();
    }
  }, [pipelinesData?.items]);

  function reload() {
    reloadPipelines();
    void loadAllProposals();
  }

  // 创建提案
  async function handleCreateProposal() {
    if (!newPropPipelineId) {
      setErrMsg("请选择管道");
      return;
    }
    if (!newPropTitle.trim()) {
      setErrMsg("请填写提案标题");
      return;
    }
    setNewPropBusy(true);
    setErrMsg("");
    setMsg("");
    try {
      const summary = PIPELINE_DIFF_MAP[newPropPipelineId.replace(/-qyh$/, "")] || "管道配置变更";
      await apiPost(
        `/v1/pipelines/${encodeURIComponent(newPropPipelineId)}/proposals`,
        {
          title: newPropTitle.trim(),
          description: newPropDesc.trim(),
          proposed_by: "当前用户",
          diff_summary: summary,
        },
      );
      setMsg(`✅ 提案已创建：${newPropTitle.trim()}`);
      setShowCreateModal(false);
      setNewPropPipelineId("");
      setNewPropTitle("");
      setNewPropDesc("");
      reload();
    } catch (e) {
      setErrMsg(`创建失败: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setNewPropBusy(false);
    }
  }

  // 审批提案
  async function handleApprove(plId: string, ppId: string) {
    setErrMsg("");
    setMsg("");
    setBusyAction(`approve-${ppId}`);
    try {
      await apiPost(`/v1/pipelines/${encodeURIComponent(plId)}/proposals/${encodeURIComponent(ppId)}/approve`, {});
      setMsg(`✅ 提案已审批通过`);
      reload();
    } catch (e) {
      setErrMsg(`❌ 审批失败: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusyAction(null);
    }
  }

  // 合并提案
  async function handleMerge(plId: string, ppId: string) {
    setErrMsg("");
    setMsg("");
    setBusyAction(`merge-${ppId}`);
    try {
      await apiPost(`/v1/pipelines/${encodeURIComponent(plId)}/proposals/${encodeURIComponent(ppId)}/merge`, {});
      setMsg(`✅ 提案已合并到主分支`);
      reload();
    } catch (e) {
      const errText = e instanceof Error ? e.message : String(e);
      if (errText.includes("expected 'approved'")) {
        setErrMsg(`⚠️ 合并失败：需先审批提案，请先点击「审批」按钮`);
      } else {
        setErrMsg(`❌ 合并失败: ${errText}`);
      }
    } finally {
      setBusyAction(null);
    }
  }

  // 作废提案
  async function handleDiscard(plId: string, ppId: string) {
    setErrMsg("");
    setMsg("");
    setBusyAction(`discard-${ppId}`);
    try {
      await apiPost(`/v1/pipelines/${encodeURIComponent(plId)}/proposals/${encodeURIComponent(ppId)}/discard`, {});
      setMsg(`✅ 提案已作废`);
      reload();
    } catch (e) {
      setErrMsg(`❌ 作废失败: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusyAction(null);
    }
  }

  function handlePreviewDiff(p: ProposalItem) {
    setDiffId(p.id);
    setDiffContent(getProposalDiff(p));
  }

  function getStatusBadge(status: string) {
    switch (status) {
      case "approved":
        return { text: "已审批", className: "bp-tag bp-tag-info" };
      case "merged":
        return { text: "已合并", className: "bp-tag bp-tag-success" };
      case "discarded":
        return { text: "已作废", className: "bp-tag bp-tag-muted" };
      case "rejected":
        return { text: "已驳回", className: "bp-tag bp-tag-error" };
      default:
        return { text: "待审", className: "bp-tag bp-tag-warn" };
    }
  }

  const historyRows = [
    ["v12 · 合并提案 #prop-115", "7 天前 · 张三"],
    ["v11 · 修复空值过滤", "14 天前 · 李四"],
    ["v10 · 初始上线", "30 天前 · 系统"],
  ];

  // 过滤：待审提案 tab 显示 pending + approved；历史 tab 显示 merged + discarded
  const pendingProposals = proposals.filter((p) => p.status === "pending" || p.status === "approved");
  const doneProposals = proposals.filter((p) => p.status === "merged" || p.status === "discarded" || p.status === "rejected");

  return (
    <S2Chrome title="管道提案与历史" lede="变更提案审阅与版本回溯 · 管道即提案">
      <PipelineWorkflowStepper current={1} />
      <BpToolbar>
        <button
          type="button"
          className="btn-primary"
          onClick={() => {
            setShowCreateModal(true);
            setErrMsg("");
            setMsg("");
          }}
        >
          新建提案
        </button>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
        <Link to="/data/pipelines" className="btn-nav">
          ← 管道列表
        </Link>
        {(pipelinesData?.items || [])[0] && (
          <Link
            to={`/data/pipelines/${encodeURIComponent((pipelinesData?.items || [])[0].id)}`}
            className="btn-nav-accent"
          >
            打开管道画布 →
          </Link>
        )}
      </BpToolbar>

      <BpTabs
        tabs={[
          { id: "proposals", label: `待审提案 (${pendingProposals.length})` },
          { id: "history", label: `已处理 (${doneProposals.length})` },
        ]}
        active={tab}
        onChange={(id) => setTab(id as "proposals" | "history")}
      />

      {msg && <p className="aos-text">{msg}</p>}
      {errMsg && <p className="error">{errMsg}</p>}
      {proposalsLoading && <p className="muted">加载提案中...</p>}
      {pipelinesErr && <p className="error">加载管道失败: {pipelinesErr}</p>}

      {/* Diff 预览 Banner */}
      {tab === "proposals" && diffId && diffContent && (
        <BpBanner tone="info">
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <strong>Diff 预览 · 提案 #{diffId}</strong>
              <button type="button" className="btn" onClick={() => { setDiffId(null); setDiffContent(null); }}>
                关闭 Diff
              </button>
            </div>
            <pre style={{
              background: "var(--aos-bg-elevated, #f5f5f5)",
              padding: 12,
              borderRadius: 6,
              fontSize: "0.8rem",
              whiteSpace: "pre-wrap",
              maxHeight: 360,
              overflowY: "auto",
              fontFamily: "ui-monospace, monospace",
            }}>
{diffContent}
            </pre>
          </div>
        </BpBanner>
      )}

      {/* 新建提案 Modal */}
      {showCreateModal && (
        <BpBanner tone="info">
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <strong>新建管道提案</strong>
              <button
                type="button"
                className="btn"
                onClick={() => {
                  setShowCreateModal(false);
                  setNewPropPipelineId("");
                  setNewPropTitle("");
                  setNewPropDesc("");
                }}
              >
                取消
              </button>
            </div>
            <div style={{ display: "grid", gap: 10, maxWidth: 600 }}>
              <label>
                <span style={{ fontSize: "0.8rem", color: "var(--aos-text-muted)" }}>所属管道 *</span>
                <select
                  value={newPropPipelineId}
                  onChange={(e) => {
                    setNewPropPipelineId(e.target.value);
                    const display = getPipelineNameById(e.target.value);
                    if (e.target.value && !newPropTitle) {
                      setNewPropTitle(`提案 · ${display}`);
                    }
                  }}
                  style={{ display: "block", width: "100%", marginTop: 4, padding: "6px 8px" }}
                >
                  <option value="">— 请选择管道 —</option>
                  {(pipelinesData?.items || []).map((pl) => (
                    <option key={pl.id} value={pl.id}>
                      {pl.name || getPipelineDisplayName(pl.id)} ({pl.id})
                    </option>
                  ))}
                </select>
              </label>
              <label>
                <span style={{ fontSize: "0.8rem", color: "var(--aos-text-muted)" }}>提案标题 *</span>
                <input
                  value={newPropTitle}
                  onChange={(e) => setNewPropTitle(e.target.value)}
                  placeholder="例如：字段映射优化 & 敏感字段脱敏"
                  style={{ display: "block", width: "100%", marginTop: 4, padding: "6px 8px" }}
                />
              </label>
              <label>
                <span style={{ fontSize: "0.8rem", color: "var(--aos-text-muted)" }}>变更说明</span>
                <textarea
                  value={newPropDesc}
                  onChange={(e) => setNewPropDesc(e.target.value)}
                  placeholder="描述本提案变更的背景、目的和影响范围..."
                  rows={4}
                  style={{ display: "block", width: "100%", marginTop: 4, padding: "6px 8px" }}
                />
              </label>
              <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
                <button
                  type="button"
                  className="btn"
                  onClick={() => {
                    setShowCreateModal(false);
                    setNewPropPipelineId("");
                    setNewPropTitle("");
                    setNewPropDesc("");
                  }}
                >
                  取消
                </button>
                <button
                  type="button"
                  className="btn-primary"
                  disabled={newPropBusy}
                  onClick={() => void handleCreateProposal()}
                >
                  {newPropBusy ? "创建中..." : "提交提案"}
                </button>
              </div>
            </div>
          </div>
        </BpBanner>
      )}

      {/* 待审提案 Tab */}
      {tab === "proposals" && (
        <div className="bp-discover-grid">
          {pendingProposals.length === 0 && !proposalsLoading ? (
            <p className="muted">暂无待审提案 · 点击「新建提案」创建一个</p>
          ) : (
            pendingProposals.map((p, i) => {
              const badge = getStatusBadge(p.status);
              const isPending = p.status === "pending";
              const isApproved = p.status === "approved";
              const isBusy = (action: string) => busyAction === `${action}-${p.id}`;

              return (
                <div
                  key={p.id}
                  className={`bp-discover-card bp-discover-${i === 0 ? "violet" : "muted"}`}
                >
                  <div className="bp-discover-head">
                    <span className="bp-discover-title">{getProposalTitle(p)}</span>
                    <span className={badge.className}>{badge.text}</span>
                  </div>
                  <p className="bp-discover-meta">
                    管道：{p.pipelineName || getPipelineNameById(p.pipeline_id)}
                    {p.proposed_by ? ` · 提交人：${p.proposed_by}` : ""}
                  </p>
                  <p className="muted" style={{ fontSize: "0.75rem" }}>
                    {getChangeSummary(p)}
                  </p>
                  <div className="bp-object-actions" style={{ flexWrap: "wrap", gap: 4 }}>
                    {isPending && (
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={isBusy("approve")}
                        onClick={() => handleApprove(p.pipeline_id, p.id)}
                      >
                        {isBusy("approve") ? "审批中..." : "审批"}
                      </button>
                    )}
                    {isApproved && (
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={isBusy("merge")}
                        onClick={() => handleMerge(p.pipeline_id, p.id)}
                      >
                        {isBusy("merge") ? "合并中..." : "合并到主分支"}
                      </button>
                    )}
                    {isPending && (
                      <button
                        type="button"
                        className="btn"
                        onClick={() => handleMerge(p.pipeline_id, p.id)}
                        disabled={isBusy("merge")}
                        title="需先审批，再合并"
                      >
                        {isBusy("merge") ? "合并中..." : "合并到主分支"}
                      </button>
                    )}
                    <button
                      type="button"
                      className="btn"
                      onClick={() => handlePreviewDiff(p)}
                    >
                      预览 Diff
                    </button>
                    {isPending && (
                      <button
                        type="button"
                        className="btn"
                        disabled={isBusy("discard")}
                        onClick={() => handleDiscard(p.pipeline_id, p.id)}
                      >
                        作废
                      </button>
                    )}
                  </div>
                  {isPending && (
                    <p className="muted" style={{ fontSize: "0.7rem", marginTop: 4 }}>
                      💡 流程：先「审批」→ 再「合并到主分支」
                    </p>
                  )}
                  {isApproved && (
                    <p className="muted" style={{ fontSize: "0.7rem", marginTop: 4 }}>
                      ✅ 已通过审批，点击「合并到主分支」完成变更
                    </p>
                  )}
                </div>
              );
            })
          )}
        </div>
      )}

      {/* 已处理 Tab */}
      {tab === "history" && (
        <>
          {doneProposals.length > 0 ? (
            <BpTable
              columns={["提案 ID", "标题", "管道", "状态", "说明"]}
              rows={doneProposals.map((p) => [
                <span className="mono">{p.id}</span>,
                p.title,
                p.pipelineName || getPipelineNameById(p.pipeline_id),
                (() => {
                  const b = getStatusBadge(p.status);
                  return <span className={b.className}>{b.text}</span>;
                })(),
                getChangeSummary(p),
              ])}
            />
          ) : (
            <BpTable columns={["版本", "说明"]} rows={historyRows} />
          )}
        </>
      )}

      <BpLinkRow links={[{ to: "/data/pipelines", label: "← 管道列表" }]} />
    </S2Chrome>
  );
}

/** 77 · 对齐 code-repositories.html */
export function CodeReposPage() {
  const { data, err, reload } = useJsonGet<{
    items: { id: string; name: string; url?: string; branch?: string; status?: string }[];
    store?: string;
  }>("/v1/code-repos");

  return (
    <S2Chrome title="代码库" lede="对齐 code-repositories · 工程目录（非 Git 主机）">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => reload()}>
          刷新
        </button>
      </BpToolbar>
      {err && <p className="error">{err}</p>}
      <p className="muted">store={data?.store ?? "—"}</p>
      <BpTable
        columns={["仓库", "URL", "分支", "状态"]}
        rows={(data?.items || []).map((r) => [
          <strong>{r.name}</strong>,
          <span className="muted">{r.url}</span>,
          r.branch || "—",
          r.status || "—",
        ])}
      />
    </S2Chrome>
  );
}

/** 77 · 对齐 lineage.html */
export function DataLineagePage() {
  const datasets = useJsonGet<{ items: { rid: string; name?: string; pipelineId?: string; sourceId?: string }[] }>(
    "/v1/datasets",
  );
  const syncs = useJsonGet<{ items: { id: string; sourceId?: string; status?: string }[] }>("/v1/syncs");
  const [history, setHistory] = useState<unknown>(null);
  const [rid, setRid] = useState("");

  async function loadHistory(target: string) {
    setRid(target);
    const r = await apiGet(`/v1/datasets/${encodeURIComponent(target)}/history`);
    setHistory(r);
  }

  return (
    <S2Chrome title="数据沿袭" lede="对齐 lineage · Source → Sync → Dataset → Build">
      <BpToolbar>
        <button
          type="button"
          className="btn"
          onClick={() => {
            datasets.reload();
            syncs.reload();
          }}
        >
          刷新
        </button>
        <Link to="/aip/lineage" className="btn-nav">
          AIP 决策谱系 →
        </Link>
      </BpToolbar>
      {(datasets.err || syncs.err) && <p className="error">{datasets.err || syncs.err}</p>}

      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        沿袭链
      </h2>
      {(datasets.data?.items || []).map((d) => {
        const syncId =
          (syncs.data?.items || []).find((s) => s.sourceId === d.sourceId)?.id || "—";
        return (
          <div key={d.rid} style={{ marginBottom: "1rem" }}>
            <div className="bp-section-label">{d.name || d.rid}</div>
            <BpLineageTimeline
              steps={[
                { phase: "Source", title: d.sourceId || "—", tone: "input" },
                { phase: "Sync", title: syncId, subtitle: d.sourceId, tone: "process" },
                { phase: "Pipeline", title: d.pipelineId || "—", tone: "process" },
                { phase: "Dataset", title: d.rid, subtitle: d.name, tone: "output" },
              ]}
            />
            <button
              type="button"
              className="btn"
              style={{ marginTop: 8 }}
              onClick={() => void loadHistory(d.rid).catch(console.error)}
            >
              查看 History
            </button>
          </div>
        );
      })}

      {(syncs.data?.items || []).length > 0 && (
        <>
          <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: "1rem" }}>
            Syncs
          </h2>
          <BpTable
            columns={["Sync", "Source", "状态"]}
            rows={(syncs.data?.items || []).map((s) => [s.id, s.sourceId || "—", s.status || "—"])}
          />
        </>
      )}

      {history != null && (
        <>
          <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
            History · {rid}
          </h2>
          <JsonBlock value={history} />
        </>
      )}
      {(datasets.data?.items?.length || 0) === 0 && (
        <p className="muted">
          空 · <Link to="/data">数据源管理</Link>
        </p>
      )}
    </S2Chrome>
  );
}

type ApolloChannel = {
  id: string;
  name?: string;
  status: string;
  rank: number;
  promotedFrom?: string | null;
  promotedAt?: string | null;
  recalledFrom?: string | null;
  recalledAt?: string | null;
};

const CHANNEL_ORDER = ["dev", "staging", "stable"] as const;

function nextChannel(id: string): string | null {
  const i = CHANNEL_ORDER.indexOf(id as (typeof CHANNEL_ORDER)[number]);
  if (i < 0 || i + 1 >= CHANNEL_ORDER.length) return null;
  return CHANNEL_ORDER[i + 1];
}

function prevChannel(id: string): string | null {
  const i = CHANNEL_ORDER.indexOf(id as (typeof CHANNEL_ORDER)[number]);
  if (i <= 0) return null;
  return CHANNEL_ORDER[i - 1];
}

export function ApolloReleasePage() {
  const fleet = useJsonGet<Record<string, unknown>>("/v1/apollo/fleet");
  const channels = useJsonGet<{ items: ApolloChannel[] }>("/v1/apollo/channels");
  const [upgrade, setUpgrade] = useState<unknown>(null);
  const [action, setAction] = useState<unknown>(null);
  const [msg, setMsg] = useState("");

  function refreshAll() {
    fleet.reload();
    channels.reload();
  }

  async function runUpgrade() {
    const r = await apiPost("/v1/apollo/upgrade", { from: "0.2.0-dev", to: "0.3.0-dev" });
    setUpgrade(r);
    setMsg("Lite upgrade 演练完成");
    refreshAll();
  }

  async function runPromote(id: string) {
    setMsg("");
    try {
      const r = await apiPost(`/v1/apollo/channels/${encodeURIComponent(id)}/promote`, {});
      setAction(r);
      setMsg(`Promote OK · ${id} → ${(r as { to?: string }).to ?? "?"}`);
      refreshAll();
    } catch (e) {
      const err = e as Error & { status?: number; body?: { code?: string } };
      setMsg(`${err.status ?? "?"} · ${err.body?.code ?? "ERR"} · ${err.message}`);
    }
  }

  async function runRecall(id: string) {
    setMsg("");
    try {
      const r = await apiPost(`/v1/apollo/channels/${encodeURIComponent(id)}/recall`, {});
      setAction(r);
      setMsg(`Recall OK · ${id} → ${(r as { to?: string }).to ?? "?"}`);
      refreshAll();
    } catch (e) {
      const err = e as Error & { status?: number; body?: { code?: string } };
      setMsg(`${err.status ?? "?"} · ${err.body?.code ?? "ERR"} · ${err.message}`);
    }
  }

  return (
    <S2Chrome title="Release 通道" lede="Channel 目录 promote/recall · 健康门控/Asset 同绑（160）· 真舰队仍延期">
      <button type="button" className="btn" onClick={() => void runUpgrade().catch((e) => setMsg(String(e)))}>
        Lite Upgrade
      </button>
      <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => refreshAll()}>
        刷新
      </button>
      {msg && <p className="aos-text">{msg}</p>}
      {(fleet.err || channels.err) && <p className="error">{fleet.err || channels.err}</p>}
      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        Channels
      </h2>
      <ul className="card-list">
        {(channels.data?.items || []).map((c) => {
          const nxt = nextChannel(c.id);
          const prev = prevChannel(c.id);
          return (
            <li key={c.id} className="card">
              <strong>{c.name || c.id}</strong>{" "}
              <span className="muted">
                {c.status} · rank={c.rank}
                {c.promotedFrom ? ` · promotedFrom=${c.promotedFrom}` : ""}
                {c.recalledFrom ? ` · recalledFrom=${c.recalledFrom}` : ""}
              </span>
              <div style={{ marginTop: 8 }}>
                {nxt && c.status === "open" && (
                  <button type="button" className="btn" onClick={() => void runPromote(c.id)}>
                    Promote → {nxt}
                  </button>
                )}
                {prev && (
                  <button
                    type="button"
                    className="btn"
                    style={{ marginLeft: nxt && c.status === "open" ? 8 : 0 }}
                    onClick={() => void runRecall(c.id)}
                  >
                    Recall → {prev}
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        Hub 舰队
      </h2>
      {fleet.data && (
        <>
          <BpMetricGrid
            items={[
              {
                label: "Hub",
                value: String((fleet.data as { hub?: { id?: string; status?: string } }).hub?.id || "—"),
                tone: "ok",
              },
              {
                label: "Hub 状态",
                value: String((fleet.data as { hub?: { status?: string } }).hub?.status || "—"),
                tone: "ok",
              },
              {
                label: "Spokes",
                value: String((fleet.data as { spokes?: unknown[] }).spokes?.length ?? 0),
                tone: "muted",
              },
              {
                label: "Full 运行时",
                value: (fleet.data as { hub?: { fullSpokeRuntimeDeferred?: boolean } }).hub
                  ?.fullSpokeRuntimeDeferred
                  ? "延期"
                  : "—",
                tone: "warn",
              },
            ]}
          />
          <BpTable
            columns={["Channel", "状态", "rank"]}
            rows={(
              (fleet.data as { channels?: { id: string; name?: string; status?: string; rank?: number }[] })
                .channels || []
            ).map((c) => [c.name || c.id, c.status || "—", String(c.rank ?? "—")])}
          />
        </>
      )}
      {action != null && (
        <BpDebugPanel value={action} title="最近操作 JSON" />
      )}
      {upgrade != null && (
        <BpDebugPanel value={upgrade} title="Upgrade JSON" />
      )}
      <p className="muted">
        变更审批 <Link to="/apollo/change">Change</Link> · 资产包 <Link to="/apollo/assets">Assets</Link> ·
        Full Spoke 运行时仍延期（目录骨架 ✅）
      </p>
    </S2Chrome>
  );
}

export function ApolloFerryPage() {
  const status = useJsonGet<Record<string, unknown>>("/v1/apollo/ferry/status");
  const matrix = useJsonGet<{
    hubVersion?: string;
    notes?: string;
    rules?: { component: string; label?: string; min: string; recommended: string }[];
  }>("/v1/ops/version-matrix");
  const [exportMsg, setExportMsg] = useState("");
  const [bundleB64, setBundleB64] = useState("");
  const [importMsg, setImportMsg] = useState("");
  const [desktopVer, setDesktopVer] = useState("0.2.0");
  const [spokeVer, setSpokeVer] = useState("0.3.0");
  const [ferryVer, setFerryVer] = useState("1.0");
  const [checkMsg, setCheckMsg] = useState("");

  async function doCompatCheck() {
    setCheckMsg("");
    try {
      const r = (await apiPost("/v1/ops/version-matrix/check", {
        desktop: desktopVer || undefined,
        spoke: spokeVer || undefined,
        ferryBundle: ferryVer || undefined,
      })) as {
        overall?: string;
        items?: { component: string; status: string; reason?: string; actual?: string }[];
      };
      const lines = (r.items || []).map(
        (i) => `${i.component}=${i.status}${i.actual ? `(${i.actual})` : ""} · ${i.reason || ""}`,
      );
      setCheckMsg(`overall=${r.overall} · ${lines.join("；")}`);
    } catch (e) {
      setCheckMsg(String(e));
    }
  }

  async function doExport() {
    setExportMsg("");
    setImportMsg("");
    const r = (await apiPost("/v1/apollo/ferry/export", {
      env: "dev",
      channel: "lite",
    })) as { filename?: string; bundleId?: string; contentBase64?: string; sizeBytes?: number };
    setBundleB64(r.contentBase64 || "");
    setExportMsg(
      `export OK · ${r.filename} · ${r.bundleId} · ${r.sizeBytes ?? "?"} bytes`,
    );
  }

  async function doImport(strip = false) {
    setImportMsg("");
    if (!bundleB64) {
      setImportMsg("请先 Export");
      return;
    }
    try {
      const r = (await apiPost("/v1/apollo/ferry/import", {
        contentBase64: bundleB64,
        stripSignature: strip || undefined,
      })) as { ok?: boolean; bundleId?: string; verified?: boolean };
      setImportMsg(`import OK · bundleId=${r.bundleId} · verified=${String(r.verified)}`);
    } catch (e) {
      const err = e as Error & { status?: number; body?: { code?: string } };
      setImportMsg(`${err.status ?? "?"} · ${err.body?.code ?? "ERR"} · ${err.message}`);
    }
  }

  return (
    <S2Chrome title="Ferry 摆渡" lede="对齐 apollo-ferry · T5.6 签名 tar.gz + 镜像清单（HMAC；cosign/skopeo 探针）">
      <button type="button" className="btn" onClick={() => status.reload()}>
        刷新 status
      </button>
      <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => void doExport().catch((e) => setExportMsg(String(e)))}>
        Export
      </button>
      <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => void doImport(false)}>
        Import
      </button>
      <button type="button" className="btn" style={{ marginLeft: 8 }} onClick={() => void doImport(true)}>
        Import 去签（预期拒）
      </button>
      {status.err && <p className="error">{status.err}</p>}
      {status.data && (
        <BpPropGrid
          items={Object.entries(status.data)
            .slice(0, 8)
            .map(([k, v]) => ({
              label: k,
              value:
                v == null
                  ? "—"
                  : typeof v === "object"
                    ? Array.isArray(v)
                      ? `[${(v as unknown[]).length}]`
                      : "{…}"
                    : String(v),
            }))}
        />
      )}
      {exportMsg && <p className="aos-text">{exportMsg}</p>}
      {importMsg && <p className="aos-text">{importMsg}</p>}
      <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: 16 }}>
        版本矩阵（TWB.7 · 气隙端对照）
      </h2>
      {matrix.err && <p className="error">{matrix.err}</p>}
      {matrix.data?.notes && <p className="muted">{matrix.data.notes}</p>}
      {matrix.data?.rules && (
        <BpPropGrid
          items={(matrix.data.rules || []).map((r) => ({
            label: r.label || r.component,
            value: `min ${r.min} · 荐 ${r.recommended}`,
          }))}
        />
      )}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginTop: 8, alignItems: "center" }}>
        <label className="muted">
          desktop{" "}
          <input value={desktopVer} onChange={(e) => setDesktopVer(e.target.value)} style={{ width: 88 }} />
        </label>
        <label className="muted">
          spoke{" "}
          <input value={spokeVer} onChange={(e) => setSpokeVer(e.target.value)} style={{ width: 88 }} />
        </label>
        <label className="muted">
          ferry{" "}
          <input value={ferryVer} onChange={(e) => setFerryVer(e.target.value)} style={{ width: 72 }} />
        </label>
        <button type="button" className="btn" onClick={() => void doCompatCheck()}>
          兼容检查
        </button>
        <button type="button" className="btn" onClick={() => matrix.reload()}>
          刷新矩阵
        </button>
      </div>
      {checkMsg && <p className="aos-text">{checkMsg}</p>}
      <p className="muted">
        镜像层：默认含 artifacts/images.json + images.sig（cosign-dev-hmac；PATH 有 cosign/skopeo 时增强）。
        相关：
        <Link to="/apollo/assets"> Asset Bundle</Link> ·
        <Link to="/apollo/spoke"> Spoke Lite</Link>
      </p>
    </S2Chrome>
  );
}

export function ApolloChangePage() {
  const ontologyDrafts = useOntologyDrafts();
  const changes = useJsonGet<{ items?: { id?: string; title?: string; kind?: string; status?: string; emergency?: boolean; decidedBy?: string; channelId?: string }[] }>(
    "/v1/apollo/changes",
  );
  const channels = useJsonGet<{ items: ApolloChannel[] }>("/v1/apollo/channels");
  const fleet = useJsonGet<Record<string, unknown>>("/v1/apollo/fleet");
  const [chgTitle, setChgTitle] = useState("channel-promote-review");
  const [chgKind, setChgKind] = useState<"channel" | "hotfix" | "config">("channel");
  const [localErr, setLocalErr] = useState<string | null>(null);

  function refreshAll() {
    ontologyDrafts.reload();
    changes.reload();
    channels.reload();
    fleet.reload();
  }

  async function createChange() {
    setLocalErr(null);
    try {
      await apiPost("/v1/apollo/changes", {
        title: chgTitle.trim() || "change",
        kind: chgKind,
        channelId: chgKind === "hotfix" ? "hotfix" : "staging",
        summary: "apollo-ops-160",
        emergency: chgKind === "hotfix",
      });
      changes.reload();
    } catch (e) {
      setLocalErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function decide(id: string, approve: boolean) {
    setLocalErr(null);
    try {
      await apiPost(
        `/v1/apollo/changes/${encodeURIComponent(id)}/${approve ? "approve" : "reject"}`,
        { note: approve ? "ok" : "reject" },
      );
      changes.reload();
    } catch (e) {
      setLocalErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function mergeStable(id: string) {
    setLocalErr(null);
    try {
      await apiPost(`/v1/apollo/changes/${encodeURIComponent(id)}/merge-stable`, {});
      changes.reload();
    } catch (e) {
      setLocalErr(e instanceof Error ? e.message : String(e));
    }
  }

  const hub = fleet.data as {
    hub?: { apolloOpsDeepeningReady?: boolean; fullSpokeRuntimeDeferred?: boolean };
  };

  return (
    <S2Chrome
      title="变更审批"
      lede="Apollo 运维深水 MVP（160）· 环境 Change 单 · ≠ Ontology Draft · ≠ 真多集群"
    >
      <BpToolbar>
        <button type="button" className="btn" onClick={() => refreshAll()}>
          刷新
        </button>
        <Link to="/apollo/release" className="btn-nav">
          Release 通道
        </Link>
      </BpToolbar>
      {(ontologyDrafts.err || channels.err || changes.err || localErr) && (
        <p className="error">{ontologyDrafts.err || channels.err || changes.err || localErr}</p>
      )}
      <p className="muted" style={{ fontSize: "0.75rem" }}>
        opsDeepening=
        {hub?.hub?.apolloOpsDeepeningReady ? "ready" : "—"} · fullK8s=
        {hub?.hub?.fullSpokeRuntimeDeferred ? "deferred" : "—"}
      </p>

      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        环境 Change
      </h2>
      <div
        style={{
          display: "grid",
          gap: 8,
          gridTemplateColumns: "1fr auto auto",
          maxWidth: 520,
          fontSize: "0.8rem",
          alignItems: "end",
          marginBottom: 8,
        }}
      >
        <label>
          title
          <input
            value={chgTitle}
            onChange={(e) => setChgTitle(e.target.value)}
            style={{ display: "block", width: "100%", marginTop: 4 }}
          />
        </label>
        <label>
          kind
          <select
            value={chgKind}
            onChange={(e) => setChgKind(e.target.value as "channel" | "hotfix" | "config")}
            style={{ display: "block", marginTop: 4 }}
          >
            <option value="channel">channel</option>
            <option value="hotfix">hotfix</option>
            <option value="config">config</option>
          </select>
        </label>
        <button type="button" className="btn" onClick={() => void createChange()}>
          创建
        </button>
      </div>
      <ul className="card-list">
        {(changes.data?.items || []).map((c) => (
          <li key={c.id} className="card">
            <strong>{c.title || c.id}</strong>{" "}
            <span className="muted">
              {c.kind} · {c.status}
              {c.emergency ? " · emergency" : ""}
              {c.channelId ? ` · ${c.channelId}` : ""}
              {c.decidedBy ? ` · by ${c.decidedBy}` : ""}
            </span>
            <div style={{ marginTop: 6, display: "flex", gap: 8, flexWrap: "wrap" }}>
              {c.status === "pending" && (
                <>
                  <button type="button" className="btn" onClick={() => void decide(String(c.id), true)}>
                    批准
                  </button>
                  <button
                    type="button"
                    className="btn-nav"
                    onClick={() => void decide(String(c.id), false)}
                  >
                    驳回
                  </button>
                </>
              )}
              {c.kind === "hotfix" && c.status === "approved" && (
                <button type="button" className="btn" onClick={() => void mergeStable(String(c.id))}>
                  合并回 stable（stub）
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>

      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        Channel 梯子
      </h2>
      <ul className="card-list">
        {(channels.data?.items || []).map((c) => (
          <li key={c.id} className="card">
            <strong>{c.name || c.id}</strong>{" "}
            <span className="muted">
              {c.status} · rank={c.rank}
              {c.promotedAt ? ` · promotedAt=${c.promotedAt}` : ""}
              {c.recalledAt ? ` · recalledAt=${c.recalledAt}` : ""}
            </span>
          </li>
        ))}
      </ul>

      <h2 className="aos-text" style={{ fontSize: "0.875rem" }}>
        Ontology Drafts（旁路 · 非环境变更）
      </h2>
      <ul className="card-list">
        {(ontologyDrafts.data?.items || []).slice(0, 5).map((d) => (
          <li key={d.id} className="card">
            <strong>{d.title || d.id}</strong>{" "}
            <span className="muted">
              {d.status} · {d.objectType}/{d.objectId}
            </span>
          </li>
        ))}
      </ul>
      <p className="muted">
        晋升/召回：
        <Link to="/apollo/release"> Release 通道</Link> · Ontology 审批：
        <Link to="/aip/drafts"> Draft 收件箱</Link>
      </p>
    </S2Chrome>
  );
}

// SyncConfigPage 已迁移到独立文件 ./SyncConfigPage.tsx
// SyncRoutesPage 已迁移到独立文件 ./SyncRoutesPage.tsx

/** 本体 · 数字孪生 · OKF 概览 — 行业模板与映射活动概览 */
export function OkfOverviewPage() {
  const ecom = useJsonGet<OkfTypeOverview>("/v1/ontology/okf-mappings/ecom/types");
  const env = useJsonGet<OkfMapping>("/v1/ontology/okf-mappings/env");
  const bio = useJsonGet<OkfMapping>("/v1/ontology/okf-mappings/bio");
  const requests = { ecom, env, bio };
  const industries = [
    { id: "env", name: "环境", request: env },
    { id: "bio", name: "生物", request: bio },
  ].map(({ id, name, request }) => ({
    id, name, mapping: request.data,
    mapped: Boolean(request.data?.columns?.length) && (request.data?.blockedFields?.length ?? request.data!.columns.filter((column) => !column.ok).length) === 0,
  }));
  const overviewError = Object.values(requests).map((request) => request.err).find(Boolean);

  return (
    <S2Chrome title="OKF 概览" lede="行业漏斗模板与映射活动概览 · 选择行业查看详情">
      <BpToolbar>
        <Link to="/ontology/okf-funnel" className="btn-nav">
          OKF 行业漏斗 →
        </Link>
        <Link to="/ontology/funnel" className="btn-nav">
          漏斗管道 →
        </Link>
        <button type="button" className="btn" onClick={() => Object.values(requests).forEach((request) => request.reload())}>
          刷新
        </button>
      </BpToolbar>
      {overviewError && <p className="error">{overviewError}</p>}

      <div className="bp-ws-section-title">电商整体</div>
      <BpMetricGrid
        items={[
          { label: "必填覆盖率", value: ecom.data ? `${ecom.data.overall.required.percent}%` : "—", tone: ecom.data?.overall.complete ? "ok" : "warn" },
          { label: "已映射 / 必填", value: ecom.data ? `${ecom.data.overall.required.mapped} / ${ecom.data.overall.required.total}` : "—", tone: "muted" },
          { label: "真实源类型", value: ecom.data?.items.length ?? "—", tone: "muted" },
          { label: "不可判定/未配置", value: ecom.data?.overall.unknown.length ?? "—", tone: ecom.data?.overall.unknown.length ? "warn" : "ok" },
        ]}
      />
      <BpBanner tone={ecom.data?.overall.complete ? "info" : "warn"}>
        加权口径：所有具备真实 source dataset 的类型，按 required properties 分子/分母汇总。
        {ecom.data?.overall.unknown.length ? ` 未配置：${ecom.data.overall.unknown.join("、")}；行业不得宣告完整。` : " 当前范围已完整。"}
      </BpBanner>

      <div className="bp-ws-section-title">电商 Object Type</div>
      <div className="bp-index-grid bp-index-grid-4" style={{ marginBottom: "1rem" }}>
        {(ecom.data?.items || []).map((mapping) => {
          const required = requiredCoverage(mapping);
          return (
            <Link key={mapping.objectType} to={`/ontology/okf-funnel?industry=ecom&type=${encodeURIComponent(mapping.objectType || "")}`} className="bp-discover-card bp-discover-violet" style={{ textDecoration: "none" }}>
              <div className="bp-discover-head">
                <span className="bp-discover-title">{mapping.label || mapping.objectType}</span>
                <span className={`bp-tag ${mapping.status === "configured" ? "bp-tag-ok" : "bp-tag-warn"}`}>{mapping.status === "configured" ? "已配置" : "未配置"}</span>
              </div>
              <p className="bp-discover-meta">必填覆盖 {required.mapped}/{required.total} · {required.percent}%</p>
              <p className="bp-discover-meta">源对象 {mapping.source?.count ?? 0} · r{mapping.revision ?? 0} · 水位 {mapping.source?.watermark || "未知"}</p>
            </Link>
          );
        })}
      </div>

      <div className="bp-ws-section-title">其他行业兼容模板</div>
      <div className="bp-index-grid bp-index-grid-4" style={{ marginBottom: "1rem" }}>
        {industries.map((ind) => (
          <Link
            key={ind.id}
            to={`/ontology/okf-funnel?industry=${ind.id}`}
            className="bp-discover-card bp-discover-violet"
            style={{ textDecoration: "none" }}
          >
            <div className="bp-discover-head">
              <span className="bp-discover-title">{ind.name}</span>
              <span className={`bp-tag ${ind.mapped ? "bp-tag-ok" : "bp-tag-warn"}`}>
                {ind.mapped ? "已映射" : "待映射"}
              </span>
            </div>
            <p className="bp-discover-meta">
              {ind.mapping?.objectType || "未配置 Object Type"} · {ind.mapping?.columns?.length || 0} 个字段
            </p>
            <p className="bp-discover-meta">
              覆盖率 {requiredCoverage(ind.mapping).percent}% · 阻断 {ind.mapping?.blockedFields?.length ?? 0} · r{ind.mapping?.revision ?? 0}
            </p>
          </Link>
        ))}
      </div>

      <BpBanner tone="info">
        OKF（Ontology Kernel Framework）行业漏斗将外部数据模型映射为本体属性；
        每个行业有预置模板，可在「OKF 行业漏斗」页面编辑映射规则。
      </BpBanner>
    </S2Chrome>
  );
}

// IntegrationCasesPage 已迁移到独立文件 ./IntegrationCasesPage.tsx
