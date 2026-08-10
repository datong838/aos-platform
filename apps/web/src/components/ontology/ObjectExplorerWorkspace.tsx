import { useEffect, type ReactNode } from "react";

export type ExplorerColumn = {
  key: string;
  label: string;
  type?: string;
  unit?: string;
  pii?: boolean;
};

export type ExplorerColumnResolution = {
  columns: ExplorerColumn[];
  source: "schema" | "object-union" | "domain-profile";
  schemaIncomplete: boolean;
};

export function resolveSavedExplorerColumns(
  savedColumns: unknown,
  defaults: ExplorerColumn[],
): ExplorerColumn[] {
  if (!Array.isArray(savedColumns)) return defaults;
  const seen = new Set<string>();
  const restored = savedColumns.flatMap<ExplorerColumn>((raw) => {
    if (!raw || typeof raw !== "object") return [];
    const record = raw as Record<string, unknown>;
    const key = String(record.key || "").trim();
    if (!isVisibleProperty(key) || seen.has(key)) return [];
    seen.add(key);
    return [{
      key,
      label: String(record.label || key),
      type: record.type ? String(record.type) : undefined,
      unit: record.unit ? String(record.unit) : undefined,
      pii: Boolean(record.pii),
    }];
  });
  if (restored.length === 0) return defaults;
  if (!seen.has("id")) {
    restored.unshift(defaults.find((column) => column.key === "id") || { key: "id", label: "ID" });
  }
  return restored;
}

const DOMAIN_COLUMN_PROFILES: Record<string, ExplorerColumn[]> = {
  Order: [
    { key: "id", label: "订单" },
    { key: "memberId", label: "会员 ID" },
    { key: "createdAt", label: "下单时间", type: "datetime" },
    { key: "totalAmount", label: "订单金额", type: "money", unit: "CNY" },
    { key: "orderStatus", label: "订单状态" },
    { key: "payStatus", label: "支付状态" },
    { key: "deliveryStatus", label: "发货状态" },
  ],
  Product: [
    { key: "id", label: "商品" },
    { key: "title", label: "商品名称" },
    { key: "price", label: "销售价", type: "money", unit: "CNY" },
    { key: "stock", label: "库存" },
    { key: "saleNum", label: "销量" },
    { key: "categoryId", label: "类目" },
    { key: "state", label: "上架状态" },
    { key: "updatedAt", label: "更新时间", type: "datetime" },
  ],
};

const STATUS_LABELS: Record<string, Record<string, string>> = {
  orderStatus: {
    "-1": "已关闭",
    "0": "待付款",
    "1": "待发货",
    "2": "待收货",
    "10": "已完成",
  },
  payStatus: { "0": "未支付", "1": "已支付", "2": "已退款" },
  deliveryStatus: { "0": "未发货", "1": "已发货", "2": "已收货" },
  state: { "0": "已下架", "1": "已上架" },
};

export function formatExplorerValue(
  objectType: string,
  key: string,
  value: unknown,
): string {
  if (value === null || value === undefined || value === "") return "—";
  const raw = String(value);
  const status = STATUS_LABELS[key]?.[raw];
  if (status) return status;
  if (key === "totalAmount" || key === "price" || key === "marketPrice" || key === "costPrice") {
    const amount = Number(raw);
    return Number.isFinite(amount) ? `¥${amount.toFixed(2)}` : raw;
  }
  if (key === "createdAt" || key === "updatedAt") {
    const instant = new Date(raw);
    if (!Number.isNaN(instant.getTime())) {
      return new Intl.DateTimeFormat("zh-CN", {
        timeZone: "Asia/Shanghai",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        hour12: false,
      }).format(instant);
    }
  }
  void objectType;
  return raw;
}

export function filterOperationalObjects(
  objectType: string,
  objects: Record<string, unknown>[],
): Record<string, unknown>[] {
  if (objectType === "Order") {
    return objects.filter(
      (object) => String(object.status) === "active" && Number(object.isDelete) === 0,
    );
  }
  if (objectType === "Product") {
    return objects.filter(
      (object) =>
        String(object.status) === "active" &&
        Number(object.isDelete) === 0 &&
        Number(object.state) === 1,
    );
  }
  return objects;
}

type SchemaProperty = {
  name?: unknown;
  id?: unknown;
  key?: unknown;
  displayName?: unknown;
  display_name?: unknown;
  label?: unknown;
  type?: unknown;
  datatype?: unknown;
  unit?: unknown;
  pii?: unknown;
  isPii?: unknown;
  is_pii?: unknown;
};

function schemaPropertyList(value: unknown): SchemaProperty[] {
  if (Array.isArray(value)) return value.filter((item) => item && typeof item === "object");
  if (!value || typeof value !== "object") return [];
  const record = value as Record<string, unknown>;
  if (Array.isArray(record.properties)) {
    return record.properties.filter((item) => item && typeof item === "object") as SchemaProperty[];
  }
  return Object.entries(record)
    .filter(([, item]) => item && typeof item === "object" && !Array.isArray(item))
    .map(([key, item]) => ({ key, ...(item as SchemaProperty) }));
}

function propertyKey(property: SchemaProperty): string {
  return String(property.name || property.id || property.key || "").trim();
}

function isVisibleProperty(key: string): boolean {
  return Boolean(key) && !key.startsWith("_");
}

export function resolveExplorerColumns(
  schemaProperties: unknown,
  objects: Record<string, unknown>[],
  objectType?: string,
): ExplorerColumnResolution {
  const profile = objectType ? DOMAIN_COLUMN_PROFILES[objectType] : undefined;
  if (profile) {
    const observed = new Set(objects.flatMap((object) => Object.keys(object)));
    const columns = profile.filter((column) => column.key === "id" || observed.has(column.key));
    if (columns.length > 1) {
      return { columns, source: "domain-profile", schemaIncomplete: false };
    }
  }
  const schemaColumns = schemaPropertyList(schemaProperties).flatMap<ExplorerColumn>((property) => {
      const key = propertyKey(property);
      if (!isVisibleProperty(key) || key === "id") return [];
      return [{
        key,
        label: String(
          property.displayName || property.display_name || property.label || property.name || key,
        ),
        type: property.type || property.datatype ? String(property.type || property.datatype) : undefined,
        unit: property.unit ? String(property.unit) : undefined,
        pii: Boolean(property.pii || property.isPii || property.is_pii),
      }];
    });

  if (schemaColumns.length > 0) {
    return {
      columns: [{ key: "id", label: "ID" }, ...schemaColumns],
      source: "schema",
      schemaIncomplete: false,
    };
  }

  const union = new Set<string>();
  for (const object of objects) {
    for (const key of Object.keys(object)) {
      if (isVisibleProperty(key)) union.add(key);
    }
  }
  const preferred = ["id", "title"].filter((key) => union.delete(key));
  const stableRest = [...union].sort((left, right) => left.localeCompare(right));
  const keys = [...preferred, ...stableRest];
  if (keys.length === 0) keys.push("id", "title");
  return {
    columns: keys.map((key) => ({ key, label: key === "id" ? "ID" : key })),
    source: "object-union",
    schemaIncomplete: true,
  };
}

export function toggleObjectSelection(selected: string[], key: string): string[] {
  return selected.includes(key) ? selected.filter((item) => item !== key) : [...selected, key];
}

export function getExplorerWorkspaceClasses({
  detailOpen,
  focusMode,
}: {
  detailOpen: boolean;
  focusMode: boolean;
}): string {
  return [
    "p-objx-workspace",
    detailOpen && !focusMode ? "has-detail" : "",
    focusMode ? "is-focus" : "",
  ]
    .filter(Boolean)
    .join(" ");
}

function safeReturnTo(raw: string | null): string | null {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || raw.includes("\\")) return null;
  let url: URL;
  try {
    url = new URL(raw, "https://aos.local");
  } catch {
    return null;
  }
  if (url.origin !== "https://aos.local" || url.pathname.split("/").includes("..")) return null;
  const allowed = ["/ontology", "/workshop/", "/aip/"];
  return allowed.some((prefix) => url.pathname === prefix || url.pathname.startsWith(prefix))
    ? `${url.pathname}${url.search}${url.hash}`
    : null;
}

function safeOpaqueRef(raw: string | null): string | null {
  if (!raw || raw.length > 200) return null;
  return /^[A-Za-z0-9._:-]+$/.test(raw) ? raw : null;
}

export function buildExplorerSearchParams(
  objectType: string,
  objectId: string,
  current: URLSearchParams,
): URLSearchParams {
  const next = new URLSearchParams({ type: objectType, id: objectId });
  const returnTo = safeReturnTo(current.get("returnTo"));
  const taskRef = safeOpaqueRef(current.get("taskRef"));
  const viewRef = safeOpaqueRef(current.get("viewRef"));
  if (returnTo) next.set("returnTo", returnTo);
  if (taskRef) next.set("taskRef", taskRef);
  if (viewRef) next.set("viewRef", viewRef);
  return next;
}

export function ObjectExplorerWorkspace({
  canvas,
  detail,
  detailOpen,
  focusMode,
  onCloseDetail,
  onToggleFocus,
}: {
  canvas: ReactNode;
  detail: ReactNode;
  detailOpen: boolean;
  focusMode: boolean;
  onCloseDetail: () => void;
  onToggleFocus: () => void;
}) {
  useEffect(() => {
    if (!focusMode) return;
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") onToggleFocus();
    };
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [focusMode, onToggleFocus]);

  return (
    <section
      className={getExplorerWorkspaceClasses({ detailOpen, focusMode })}
      data-testid="object-explorer-workspace"
    >
      <div className="p-objx-canvas-shell">
        <button
          type="button"
          className="p-objx-focus-toggle"
          aria-pressed={focusMode}
          onClick={onToggleFocus}
        >
          {focusMode ? "退出全屏" : "全屏画布"}
        </button>
        {canvas}
      </div>
      {detailOpen && !focusMode && (
        <aside className="p-objx-detail-drawer" aria-label="对象详情">
          <button
            type="button"
            className="p-objx-detail-close"
            aria-label="关闭对象详情"
            onClick={onCloseDetail}
          >
            ×
          </button>
          {detail}
        </aside>
      )}
    </section>
  );
}
