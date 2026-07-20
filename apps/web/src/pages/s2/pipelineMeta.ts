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
  const out = table ? TABLE_LABELS[table]?.zh || p.datasetRid || "dataset" : p.datasetRid || "dataset";
  const src = p.sourceId || "source";
  return `${src} → Ingest → ${out}`;
}

export function buildStatusBadge(status?: string): { label: string; tone: "ok" | "draft" | "run" | "muted" } {
  const s = (status || "").toUpperCase();
  if (s === "SUCCEEDED" || s === "SUCCESS") return { label: "已部署", tone: "ok" };
  if (s === "RUNNING" || s === "IN_PROGRESS") return { label: "运行中", tone: "run" };
  if (s === "FAILED" || s === "ERROR") return { label: "失败", tone: "muted" };
  if (!s) return { label: "草稿", tone: "draft" };
  return { label: s, tone: "muted" };
}
