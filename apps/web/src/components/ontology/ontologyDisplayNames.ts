const OBJECT_TYPE_DISPLAY_NAMES: Record<string, string> = {
  Order: "订单",
  OrderLine: "订单明细",
  Payment: "支付记录",
  Shipment: "发货记录",
  Product: "商品",
  ProductSku: "商品 SKU",
  Category: "商品类目",
  CustomerLite: "会员",
  Shop: "店铺",
  Weapp: "小程序",
  ProductReview: "商品评价",
  SystemConfig: "系统配置",
};

const RELATION_TYPE_DISPLAY_NAMES: Record<string, string> = {
  "Order.lines": "订单包含明细",
  "OrderLine.ofSku": "订单明细对应 SKU",
  "OrderLine.ofProduct": "订单明细对应商品",
  "ProductSku.ofProduct": "SKU 属于商品",
  "Product.inCategory": "商品属于类目",
  "Shop.sellsProduct": "店铺销售商品",
  "Order.fulfilledBy": "订单由店铺履约",
  "Order.placedByLite": "订单由会员下单",
  "Shop.hasWeapp": "店铺拥有小程序",
  "Product.hasReview": "商品包含评价",
  "ProductReview.ofSku": "评价对应 SKU",
  "ProductReview.byMember": "评价来自会员",
  "Order.hasPayment": "订单对应支付记录",
  "Order.fromWeapp": "订单来源于小程序",
};

type ObjectProjection = Record<string, unknown>;

function text(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  return normalized || null;
}

function objectId(value: ObjectProjection | string): string {
  return typeof value === "string" ? value : String(value.id || "");
}

function sourceParts(value: string): { site: string; record: string } | null {
  const parts = value.split(":");
  if (parts.length < 3 || parts[0].toLowerCase() !== "niushop") return null;
  return { site: parts[1], record: parts.slice(2).join(":") };
}

export function getObjectTypeDisplayName(objectType: string): string {
  return OBJECT_TYPE_DISPLAY_NAMES[objectType] || objectType;
}

export function getRelationTypeDisplayName(relationType: string): string {
  return RELATION_TYPE_DISPLAY_NAMES[relationType] || relationType;
}

export function getSourceRecordLabel(value: ObjectProjection | string): string {
  if (typeof value !== "string") {
    const projected = text(value._sourceRecordLabel);
    if (projected) return projected;
  }
  const id = objectId(value);
  const parts = sourceParts(id);
  return parts ? `源记录 #${parts.record}` : `系统记录 ${id}`;
}

export function getSourceIdentityLabel(value: ObjectProjection | string): string {
  if (typeof value !== "string") {
    const projected = text(value._sourceIdentityLabel);
    if (projected) return projected;
  }
  const id = objectId(value);
  const parts = sourceParts(id);
  return parts
    ? `Niushop 微商城 · 站点 ${parts.site} · 源记录 #${parts.record}`
    : `系统记录 ${id}`;
}

export function getObjectDisplayLabel(
  objectType: string,
  value: ObjectProjection,
): string {
  const projected = text(value._displayLabel);
  if (projected) return projected;
  return `${getObjectTypeDisplayName(objectType)} · ${getSourceRecordLabel(value)}`;
}
