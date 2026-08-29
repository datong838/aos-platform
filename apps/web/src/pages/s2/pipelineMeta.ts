/** Shared pipeline / dataset display labels (栖月汇表映射 · 非 Host 行业包). */

export const TABLE_LABELS: Record<string, { ot: string; zh: string }> = {
  ns_site: { ot: "Site", zh: "站点" },
  ns_weapp: { ot: "Weapp", zh: "小程序端" },
  ns_member: { ot: "Member", zh: "会员" },
  ns_member_level: { ot: "MemberLevel", zh: "会员等级" },
  ns_member_address: { ot: "MemberAddress", zh: "会员地址" },
  ns_goods: { ot: "Goods", zh: "商品" },
  ns_goods_sku: { ot: "GoodsSku", zh: "商品 SKU" },
  ns_goods_weapp: { ot: "GoodsWeapp", zh: "商品端可见" },
  ns_goods_category: { ot: "GoodsCategory", zh: "商品分类" },
  ns_order: { ot: "Order", zh: "订单" },
  ns_order_goods: { ot: "OrderLine", zh: "订单行" },
  ns_pay: { ot: "Payment", zh: "支付" },
  ns_store: { ot: "Store", zh: "门店" },
  ns_express_delivery_package: { ot: "ExpressPackage", zh: "快递包裹" },
};

/** 数据源 ID → 中文名称映射 */
export const SOURCE_LABELS: Record<string, { zh: string }> = {
  "niushop-qyh": { zh: "栖月汇微商城" },
  "src-qyh-jdbc": { zh: "栖月汇微商城" },
  "demo-file-wo": { zh: "演示工单文件" },
};

/** 管道 ID / 数据集 RID → 中文业务名称映射 */
export const PIPELINE_ZH_NAMES: Record<string, string> = {
  "P01-shop": "店铺",
  "P02-product": "商品",
  "P03-product-sku": "商品SKU",
  "P04-category": "类目",
  "P05-order": "订单",
  "P06-order-line": "订单明细",
  "P07-shipment": "发货",
  "P08-customer-lite": "会员",
  "P09-weapp": "小程序",
  "P10-system-config": "系统配置",
  "P11-product-review": "商品评价",
  "P12-payment": "支付",
  "P09-member": "会员详细信息",
  "P10-stock": "库存台账",
};

/** 获取数据源中文显示名 */
export function getSourceDisplayName(sourceId?: string): string {
  if (!sourceId) return "未指定数据源";
  if (SOURCE_LABELS[sourceId]) return SOURCE_LABELS[sourceId].zh;
  // 尝试从 ID 中提取
  if (sourceId.includes("qyh")) return "栖月汇微商城";
  return sourceId;
}

/** 获取管道/数据集中文显示名 */
export function getPipelineDisplayName(id?: string, fallbackName?: string): string {
  if (!id) return fallbackName || "管道";
  // 尝试从完整 ID（如 P02-product-qyh）提取基础 ID
  const baseId = id.replace(/-qyh$/, "");
  if (PIPELINE_ZH_NAMES[baseId]) return PIPELINE_ZH_NAMES[baseId];
  // 尝试从 dataset RID 中提取
  const ridMatch = id.match(/P\d{2}-[a-z0-9-]+/i);
  if (ridMatch) {
    const key = ridMatch[0].replace(/-qyh$/i, "");
    if (PIPELINE_ZH_NAMES[key]) return PIPELINE_ZH_NAMES[key];
  }
  return fallbackName || id;
}

/** 获取变换节点中文描述 */
export const TRANSFORM_LABELS = {
  title: "数据抽取",
  subtitle: "表 → 对象实例",
};

/** 获取输出节点中文描述 */
export function getOutputSubtitle(datasetRid?: string): string {
  if (!datasetRid) return "输出数据集";
  return datasetRid;
}

export type PipelineMeta = {
  id: string;
  sourceId?: string;
  target?: string;
  datasetRid?: string;
  name?: string;
  displayName?: string;
  objectTypeHint?: string;
  lastBuild?: { id?: string; status?: string };
};

export function tableKeyFromBlob(...parts: (string | undefined)[]): string | null {
  const blob = parts.filter(Boolean).join(" ");
  const m = blob.match(/\b(ns_[a-z0-9_]+)\b/);
  return m ? m[1] : null;
}

export function pipelineDisplayTitle(p: PipelineMeta): string {
  const table = tableKeyFromBlob(p.id, p.datasetRid, p.name, p.displayName);
  const mapped = table ? TABLE_LABELS[table] : undefined;
  if ((p.displayName || "").trim()) return String(p.displayName).trim();
  if ((p.name || "").trim() && !String(p.name).startsWith("pipe-")) return String(p.name).trim();
  if (mapped?.zh) return `${mapped.zh}管道`;
  return p.id;
}

export function pipelineFlowLine(p: PipelineMeta): string {
  const table = tableKeyFromBlob(p.id, p.datasetRid);
  const out = table ? TABLE_LABELS[table]?.zh || pipelineDisplayTitle(p) : pipelineDisplayTitle(p);
  return `${getSourceDisplayName(p.sourceId)} → 数据抽取 → ${out}`;
}

export function pipelineStatusKey(status?: string): "success" | "failed" | "running" | "unknown" {
  const normalized = (status || "").trim().toUpperCase();
  if (normalized === "SUCCEEDED" || normalized === "SUCCESS") return "success";
  if (normalized === "FAILED" || normalized === "ERROR") return "failed";
  if (normalized === "RUNNING" || normalized === "IN_PROGRESS") return "running";
  return "unknown";
}

export function buildStatusBadge(status?: string): { label: string; tone: "ok" | "draft" | "run" | "muted" } {
  const s = (status || "").toUpperCase();
  if (s === "SUCCEEDED" || s === "SUCCESS") return { label: "已部署", tone: "ok" };
  if (s === "RUNNING" || s === "IN_PROGRESS") return { label: "运行中", tone: "run" };
  if (s === "FAILED" || s === "ERROR") return { label: "失败", tone: "muted" };
  if (!s) return { label: "草稿", tone: "draft" };
  return { label: s, tone: "muted" };
}
