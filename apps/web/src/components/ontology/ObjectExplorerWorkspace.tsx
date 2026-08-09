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
  source: "schema" | "object-union";
  schemaIncomplete: boolean;
};

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
): ExplorerColumnResolution {
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
