import { useState, useCallback, useEffect, type ReactNode } from "react";
import {
  DndContext,
  DragOverlay,
  pointerWithin,
  PointerSensor,
  useSensor,
  useSensors,
  useDraggable,
  useDroppable,
  type DragStartEvent,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  verticalListSortingStrategy,
  rectSortingStrategy,
  useSortable,
  arrayMove,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { ComponentRenderer, type ComponentNode, type ComponentTree } from "./ComponentRenderer";
import "./widgets";
import {
  getWidgetsByCategory,
  getWidgetPlugin,
  CATEGORY_LABEL,
  PROP_GROUP_LABEL,
  PROP_GROUP_ORDER,
  type WidgetPlugin,
  type WidgetCategory,
  type PropFieldDef,
} from "./widgets";

// ── Types & Consts ─────────────────────────────────────────────────────────

function isContainerNode(node: ComponentNode): boolean {
  return !!getWidgetPlugin(node.type)?.isContainer;
}



// ── Tree helpers ───────────────────────────────────────────────────────────
function updateNodeConfig(
  tree: ComponentTree,
  nodeId: string,
  patch: Record<string, any>,
): ComponentTree {
  return {
    ...tree,
    [nodeId]: {
      ...tree[nodeId],
      config: { ...(tree[nodeId]?.config || {}), ...patch },
    },
  };
}

function deleteNode(tree: ComponentTree, nodeId: string): ComponentTree {
  if (nodeId === "root") return tree;
  const next: ComponentTree = { ...tree };
  delete next[nodeId];
  for (const [id, node] of Object.entries(next)) {
    if (node.children?.includes(nodeId)) {
      next[id] = {
        ...node,
        children: node.children.filter((c) => c !== nodeId),
      };
    }
  }
  return next;
}

function findParentId(tree: ComponentTree, nodeId: string): string | null {
  for (const [id, node] of Object.entries(tree)) {
    if (node.children?.includes(nodeId)) return id;
  }
  return null;
}

function insertNodeBefore(
  tree: ComponentTree,
  beforeId: string,
  newNodeId: string,
  newNode: ComponentNode,
): ComponentTree {
  const parentId = findParentId(tree, beforeId);
  if (!parentId) return tree;
  const parent = tree[parentId];
  const children = [...(parent.children || [])];
  const index = children.indexOf(beforeId);
  children.splice(index, 0, newNodeId);
  return {
    ...tree,
    [newNodeId]: newNode,
    [parentId]: { ...parent, children },
  };
}

function appendNode(
  tree: ComponentTree,
  parentId: string,
  newNodeId: string,
  newNode: ComponentNode,
): ComponentTree {
  const parent = tree[parentId];
  if (!parent) return tree;
  const children = [...(parent.children || [])];
  children.push(newNodeId);
  return {
    ...tree,
    [newNodeId]: newNode,
    [parentId]: { ...parent, children },
  };
}

function reorderChildren(
  tree: ComponentTree,
  parentId: string,
  activeId: string,
  overId: string,
): ComponentTree {
  const parent = tree[parentId];
  if (!parent || !parent.children) return tree;
  const children = [...parent.children];
  const oldIndex = children.indexOf(activeId);
  const newIndex = children.indexOf(overId);
  if (oldIndex < 0 || newIndex < 0) return tree;
  return {
    ...tree,
    [parentId]: {
      ...parent,
      children: arrayMove(children, oldIndex, newIndex),
    },
  };
}

// ── Sortable Item (每个子节点) ──────────────────────────────────────────────

function SortableItem({
  nodeId,
  node,
  components,
  selectedId,
  onSelect,
  depth,
}: {
  nodeId: string;
  node: ComponentNode;
  components: ComponentTree;
  selectedId: string | null;
  onSelect: (id: string) => void;
  depth: number;
}) {
  const [isHovered, setIsHovered] = useState(false);
  const isSelected = selectedId === nodeId;
  const container = isContainerNode(node);

  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: nodeId,
    data: { nodeId, node },
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.3 : 1,
    position: "relative" as const,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      onClick={(e) => {
        e.stopPropagation();
        onSelect(nodeId);
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {(isHovered || isSelected) && (
        <div
          style={{
            position: "absolute",
            top: -18,
            left: 0,
            background: "var(--aos-accent, #4f46e5)",
            color: "#fff",
            fontSize: 10,
            padding: "2px 6px",
            borderRadius: "3px 3px 0 0",
            zIndex: 20,
            display: "flex",
            alignItems: "center",
            gap: 4,
            cursor: "grab",
            userSelect: "none",
          }}
          {...attributes}
          {...listeners}
        >
          <span>⋮⋮</span>
          {node.type} · {nodeId}
        </div>
      )}
      <div
        style={{
          outline: isSelected
            ? "2px solid var(--aos-accent, #4f46e5)"
            : isHovered
              ? "1px dashed var(--aos-accent, #4f46e5)"
              : "none",
          outlineOffset: isSelected ? "2px" : "0px",
          borderRadius: 4,
          minHeight: container ? undefined : undefined,
        }}
      >
        {container ? (
          <ContainerRenderer
            nodeId={nodeId}
            node={node}
            components={components}
            selectedId={selectedId}
            onSelect={onSelect}
            depth={depth}
          />
        ) : (
          <ComponentRenderer components={components} rootId={nodeId} />
        )}
      </div>
    </div>
  );
}

// ── Container Renderer ─────────────────────────────────────────────────────

function ContainerRenderer({
  nodeId,
  node,
  components,
  selectedId,
  onSelect,
  depth,
}: {
  nodeId: string;
  node: ComponentNode;
  components: ComponentTree;
  selectedId: string | null;
  onSelect: (id: string) => void;
  depth: number;
}) {
  const childIds = node.children || [];
  const strategy = node.type === "horizontal-grid" ? rectSortingStrategy : verticalListSortingStrategy;
  const droppableId = `container:${nodeId}`;

  const { setNodeRef, isOver } = useDroppable({
    id: droppableId,
    data: { type: "container", nodeId },
  });

  const gridStyle: React.CSSProperties =
    node.type === "horizontal-grid"
      ? {
          display: "grid",
          gridTemplateColumns: `repeat(${node.config?.cols ?? 4}, 1fr)`,
          gap: node.config?.gap ?? 16,
        }
      : {
          padding: node.config?.padding ?? 24,
          display: "flex",
          flexDirection: "column",
          gap: node.config?.gap ?? 16,
        };

  return (
    <div
      ref={setNodeRef}
      style={{
        ...gridStyle,
        minHeight: childIds.length === 0 ? 60 : undefined,
        background: isOver ? "rgba(79, 70, 229, 0.08)" : "transparent",
        borderRadius: 4,
        transition: "background 0.15s",
      }}
    >
      <SortableContext items={childIds} strategy={strategy}>
        {childIds.map((cid) => {
          const child = components[cid];
          if (!child) return null;
          return (
            <SortableItem
              key={cid}
              nodeId={cid}
              node={child}
              components={components}
              selectedId={selectedId}
              onSelect={onSelect}
              depth={depth + 1}
            />
          );
        })}
      </SortableContext>
      {childIds.length === 0 && isOver && (
        <div
          style={{
            border: "2px dashed var(--aos-accent, #4f46e5)",
            borderRadius: 4,
            padding: 16,
            textAlign: "center",
            fontSize: 12,
            color: "var(--aos-accent, #4f46e5)",
          }}
        >
          拖入组件到这里
        </div>
      )}
    </div>
  );
}

// ── Palette Item ───────────────────────────────────────────────────────────

function PaletteItem({ item }: { item: WidgetPlugin }) {
  const { attributes, listeners, setNodeRef, isDragging } = useDraggable({
    id: `palette:${item.type}`,
    data: { type: "palette", widgetType: item.type },
  });

  return (
    <div
      ref={setNodeRef}
      {...attributes}
      {...listeners}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "8px 10px",
        borderRadius: 2,
        background: "var(--aos-surface)",
        border: "1px solid var(--aos-border)",
        cursor: "grab",
        fontSize: 12,
        color: "var(--aos-text)",
        userSelect: "none",
        opacity: isDragging ? 0.5 : 1,
        transition: "background 0.15s, border-color 0.15s",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = "var(--aos-accent, #4f46e5)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = "var(--aos-border)";
      }}
    >
      <span style={{ fontSize: 16 }}>{item.icon}</span>
      <span>{item.name}</span>
    </div>
  );
}

// ── Palette Content（按 category 分组 + 折叠）───────────────────────────────

function useCollapsedState(key: string, defaultCollapsed = false) {
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      const v = window.localStorage.getItem(`canvas.collapsed.${key}`);
      return v === null ? defaultCollapsed : v === "1";
    } catch {
      return defaultCollapsed;
    }
  });
  const toggle = useCallback(() => {
    setCollapsed((v) => {
      const next = !v;
      try { window.localStorage.setItem(`canvas.collapsed.${key}`, next ? "1" : "0"); } catch {}
      return next;
    });
  }, [key]);
  return [collapsed, toggle] as const;
}

function CollapsibleSection({
  title,
  defaultCollapsed = false,
  storageKey,
  children,
}: {
  title: string;
  defaultCollapsed?: boolean;
  storageKey: string;
  children: ReactNode;
}) {
  const [collapsed, toggle] = useCollapsedState(storageKey, defaultCollapsed);
  return (
    <div>
      <div
        onClick={toggle}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 4,
          fontSize: 10,
          fontWeight: 600,
          color: "var(--aos-text-muted)",
          marginTop: 4,
          marginBottom: 2,
          cursor: "pointer",
          userSelect: "none",
          padding: "2px 0",
        }}
      >
        <span style={{ fontSize: 9, transition: "transform 0.15s", display: "inline-block", transform: collapsed ? "rotate(-90deg)" : "rotate(0deg)" }}>
          ▼
        </span>
        {title}
      </div>
      {!collapsed && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {children}
        </div>
      )}
    </div>
  );
}

function PaletteContent() {
  const grouped = getWidgetsByCategory();
  const order: WidgetCategory[] = ["layout", "data", "filter", "action", "chart", "ai", "time", "extra"];

  return (
    <div
      style={{
        width: 220,
        height: "100%",
        padding: 10,
        overflowY: "auto",
        display: "flex",
        flexDirection: "column",
        gap: 4,
      }}
    >
      <div
        style={{
          fontSize: 11,
          fontWeight: 600,
          color: "var(--aos-text-muted)",
          textTransform: "uppercase",
          letterSpacing: 0.5,
          marginBottom: 4,
        }}
      >
        组件库
      </div>
      {order.map((cat) => {
        const items = grouped[cat];
        if (!items || items.length === 0) return null;
        return (
          <CollapsibleSection
            key={cat}
            title={CATEGORY_LABEL[cat]}
            storageKey={`palette.${cat}`}
          >
            {items.map((item) => (
              <PaletteItem key={item.type} item={item} />
            ))}
          </CollapsibleSection>
        );
      })}
      <a
        href="/workshop/widget-registry"
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          padding: "6px 10px",
          marginTop: 6,
          borderRadius: 2,
          background: "rgba(79,70,229,0.06)",
          color: "#4f46e5",
          fontSize: 11,
          fontWeight: 500,
          textDecoration: "none",
          border: "1px dashed #c7d2fe",
        }}
      >
        + 浏览组件注册表
      </a>
    </div>
  );
}

// ── Left Tab Content（布局 / 变量 / 事件）────────────────────────────────────

function LayoutTabContent({ tree }: { tree: ComponentTree }) {
  const root = tree["root"];
  const rootConfig = root?.config || {};
  const containers = Object.entries(tree).filter(([, n]) => {
    const plugin = getWidgetPlugin(n.type);
    return plugin?.isContainer;
  });
  return (
    <div style={{ width: 220, padding: 10, overflowY: "auto", fontSize: 12, display: "flex", flexDirection: "column", gap: 6 }}>
      <CollapsibleSection title="页面级配置" storageKey="layout.page" defaultCollapsed={false}>
        <PropField label="内边距">
          <input type="number" value={rootConfig.padding ?? 24} onChange={() => {}} style={inputStyle} readOnly />
        </PropField>
        <PropField label="间距">
          <input type="number" value={rootConfig.gap ?? 16} onChange={() => {}} style={inputStyle} readOnly />
        </PropField>
      </CollapsibleSection>
      <CollapsibleSection title={`容器节点 (${containers.length})`} storageKey="layout.containers" defaultCollapsed={false}>
        {containers.map(([id, n]) => (
          <div key={id} style={{ padding: "4px 8px", fontSize: 11, background: "var(--aos-surface)", borderRadius: 4, border: "1px solid var(--aos-border)" }}>
            {n.type} · {id}
          </div>
        ))}
      </CollapsibleSection>
    </div>
  );
}

function VariablesTabContent({ tree }: { tree: ComponentTree }) {
  const objectTypes = new Set<string>();
  for (const n of Object.values(tree)) {
    if (n.config?.objectType) objectTypes.add(n.config.objectType as string);
  }
  const variables = Array.from(objectTypes).map((ot) => ({
    name: `all_${ot.toLowerCase()}s`,
    type: ot,
    source: `${ot}[]`,
  }));
  return (
    <div style={{ width: 220, padding: 10, overflowY: "auto", fontSize: 12, display: "flex", flexDirection: "column", gap: 6 }}>
      <CollapsibleSection title={`模块接口 (${variables.length})`} storageKey="var.interfaces" defaultCollapsed={false}>
        {variables.length === 0 ? (
          <div style={{ fontSize: 11, color: "var(--aos-text-muted)", padding: "4px 0" }}>暂无接口变量</div>
        ) : (
          variables.map((v) => (
            <div key={v.name} style={{ padding: "6px 8px", background: "var(--aos-surface)", borderRadius: 4, border: "1px solid var(--aos-border)" }}>
              <div style={{ fontWeight: 500, color: "var(--aos-text)" }}>{v.name}</div>
              <div style={{ fontSize: 10, color: "var(--aos-text-muted)" }}>{v.type} · {v.source}</div>
            </div>
          ))
        )}
      </CollapsibleSection>
      <CollapsibleSection title="参数" storageKey="var.params" defaultCollapsed={true}>
        <div style={{ fontSize: 11, color: "var(--aos-text-muted)", padding: "4px 0" }}>暂无参数</div>
      </CollapsibleSection>
    </div>
  );
}

function EventsTabContent({ tree }: { tree: ComponentTree }) {
  const tables = Object.entries(tree).filter(([, n]) => n.type === "object-table");
  return (
    <div style={{ width: 220, padding: 10, overflowY: "auto", fontSize: 12, display: "flex", flexDirection: "column", gap: 6 }}>
      <CollapsibleSection title={`事件处理 (${tables.length})`} storageKey="events.handlers" defaultCollapsed={false}>
        {tables.map(([id]) => (
          <div key={id} style={{ padding: "4px 8px", fontSize: 11, background: "var(--aos-surface)", borderRadius: 4, border: "1px solid var(--aos-border)" }}>
            onRowClick · {id}
          </div>
        ))}
      </CollapsibleSection>
      <CollapsibleSection title="函数" storageKey="events.functions" defaultCollapsed={true}>
        <div style={{ fontSize: 11, color: "var(--aos-text-muted)", padding: "4px 0" }}>暂无函数</div>
      </CollapsibleSection>
    </div>
  );
}

// ── Property Panel ─────────────────────────────────────────────────────────

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "5px 8px",
  fontSize: 12,
  border: "1px solid var(--aos-border)",
  borderRadius: 4,
  background: "var(--aos-surface)",
  color: "var(--aos-text)",
  boxSizing: "border-box",
};

function PropField({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <label style={{ fontSize: 11, color: "var(--aos-text-muted)" }}>{label}</label>
      {children}
    </div>
  );
}

function renderPropField(field: PropFieldDef, value: unknown, onUpdate: (patch: Record<string, any>) => void) {
  if (field.type === "select") {
    return (
      <PropField key={field.key} label={field.label}>
        <select
          value={(value as string) ?? ""}
          onChange={(e) => onUpdate({ [field.key]: e.target.value })}
          style={inputStyle}
        >
          {field.options?.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </PropField>
    );
  }
  if (field.type === "textarea") {
    return (
      <PropField key={field.key} label={field.label}>
        <textarea
          value={(value as string) ?? ""}
          onChange={(e) => onUpdate({ [field.key]: e.target.value })}
          style={{ ...inputStyle, minHeight: 60, resize: "vertical" }}
          placeholder={field.placeholder}
        />
      </PropField>
    );
  }
  if (field.type === "number") {
    return (
      <PropField key={field.key} label={field.label}>
        <input
          type="number"
          value={(value as number) ?? 0}
          onChange={(e) => onUpdate({ [field.key]: Number(e.target.value) })}
          style={inputStyle}
          min={field.min}
        />
      </PropField>
    );
  }
  if (field.type === "boolean") {
    return (
      <PropField key={field.key} label={field.label}>
        <input
          type="checkbox"
          checked={(value as boolean) ?? false}
          onChange={(e) => onUpdate({ [field.key]: e.target.checked })}
          style={{ margin: 0, cursor: "pointer" }}
        />
      </PropField>
    );
  }
  return (
    <PropField key={field.key} label={field.label}>
      <input
        type="text"
        value={(value as string) ?? ""}
        onChange={(e) => onUpdate({ [field.key]: e.target.value })}
        style={inputStyle}
        placeholder={field.placeholder}
      />
    </PropField>
  );
}

function PropertyPanel({
  nodeId,
  node,
  onUpdate,
  onDelete,
}: {
  nodeId: string | null;
  node: ComponentNode | null;
  onUpdate: (patch: Record<string, any>) => void;
  onDelete: () => void;
}) {
  if (!nodeId || !node) {
    return (
      <div style={{ padding: 16, color: "var(--aos-text-muted)", fontSize: 12 }}>
        点击画布上的组件查看属性
      </div>
    );
  }

  const plugin = getWidgetPlugin(node.type);

  return (
    <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 8 }}>
      <div
        style={{
          fontSize: 12,
          fontWeight: 600,
          color: "var(--aos-text)",
          paddingBottom: 8,
          borderBottom: "1px solid var(--aos-border)",
          display: "flex",
          alignItems: "center",
          gap: 6,
        }}
      >
        <span>{plugin?.icon || "🔹"}</span>
        {node.type} · {nodeId}
      </div>

      {(() => {
        if (!plugin || !plugin.propsSchema.length) {
          return (
            <div style={{ fontSize: 12, color: "var(--aos-text-muted)" }}>
              该组件无可配置属性
            </div>
          );
        }

        // 按 group 分组
        const grouped: Record<string, PropFieldDef[]> = {};
        for (const field of plugin.propsSchema) {
          const g: string = field.group || "basic";
          if (!grouped[g]) grouped[g] = [];
          grouped[g].push(field);
        }

        return PROP_GROUP_ORDER
          .filter((g) => grouped[g]?.length)
          .map((g) => (
            <CollapsibleSection
              key={g}
              title={PROP_GROUP_LABEL[g]}
              storageKey={`prop.${node.type}.${g}`}
              defaultCollapsed={g === "advanced"}
            >
              {grouped[g].map((field) => {
                const value = node.config?.[field.key];
                return renderPropField(field, value, onUpdate);
              })}
            </CollapsibleSection>
          ));
      })()}

      {node.type !== "page-layout" && nodeId !== "root" && (
        <button
          type="button"
          onClick={onDelete}
          style={{
            marginTop: 12,
            padding: "6px 12px",
            fontSize: 12,
            borderRadius: 4,
            border: "1px solid #ef4444",
            background: "transparent",
            color: "#ef4444",
            cursor: "pointer",
          }}
        >
          删除组件
        </button>
      )}
    </div>
  );
}

// ── Sidebar toggle button ──────────────────────────────────────────────────

const TOGGLE_BTN: React.CSSProperties = {
  width: 24,
  height: 24,
  borderRadius: "50%",
  border: "1px solid var(--aos-border)",
  background: "var(--aos-surface)",
  cursor: "pointer",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: 10,
  color: "var(--aos-text-muted)",
  flexShrink: 0,
};

// ── Main Editor ────────────────────────────────────────────────────────────

export function ComponentTreeEditor({
  tree,
  onChange,
  rightCollapsed,
  onToggleRight,
}: {
  tree: ComponentTree;
  onChange: (tree: ComponentTree) => void;
  rightCollapsed: boolean;
  onToggleRight: () => void;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [activePaletteType, setActivePaletteType] = useState<string | null>(null);
  const [leftCollapsed, setLeftCollapsed] = useState<boolean>(
    () => window.localStorage.getItem("canvas.editor.leftCollapsed") === "1",
  );
  const [leftTab, setLeftTab] = useState<"widgets" | "layout" | "variables" | "events">(
    () => (window.localStorage.getItem("canvas.editor.leftTab") as "widgets" | "layout" | "variables" | "events") || "widgets",
  );

  // persist
  useEffect(() => {
    window.localStorage.setItem("canvas.editor.leftCollapsed", leftCollapsed ? "1" : "0");
  }, [leftCollapsed]);
  useEffect(() => {
    window.localStorage.setItem("canvas.editor.leftTab", leftTab);
  }, [leftTab]);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 3 },
    }),
  );

  const handleSelect = useCallback((id: string) => {
    setSelectedId(id);
  }, []);

  const handleDragStart = useCallback((event: DragStartEvent) => {
    const id = String(event.active.id);
    if (id.startsWith("palette:")) {
      setActivePaletteType(id.slice("palette:".length));
      setActiveId(null);
    } else {
      setActiveId(id);
      setActivePaletteType(null);
    }
  }, []);

  const handleDragEnd = useCallback(
    (event: DragEndEvent) => {
      const { active, over } = event;
      setActiveId(null);
      setActivePaletteType(null);
      if (!over) return;

      const activeIdStr = String(active.id);
      const overIdStr = String(over.id);

      // ── 从调色板拖入新组件 ──
      if (activeIdStr.startsWith("palette:")) {
        const widgetType = activeIdStr.slice("palette:".length);
        const paletteItem = getWidgetPlugin(widgetType);
        if (!paletteItem) return;

        const newId = `${widgetType}-${Date.now().toString(36)}`;
        const newNode: ComponentNode = {
          type: widgetType,
          config: { ...paletteItem.defaultConfig },
          ...(isContainerNode({ type: widgetType, config: {} }) ? { children: [] } : {}),
        } as ComponentNode;

        // 放在某个子节点前
        let next: ComponentTree;

        if (overIdStr.startsWith("container:")) {
          const containerId = overIdStr.slice("container:".length);
          next = appendNode(tree, containerId, newId, newNode);
        } else {
          // 拖到某个节点上 → 插入到该节点前面
          const beforeId = overIdStr;
          if (!tree[beforeId]) return;
          next = insertNodeBefore(tree, beforeId, newId, newNode);
        }

        if (next !== tree) {
          onChange(next);
          setSelectedId(newId);
        }
        return;
      }

      // ── 同层级排序 ──
      if (active.id === over.id) return;

      const parentId = findParentId(tree, activeIdStr);
      if (!parentId) return;

      const overParentId = findParentId(tree, overIdStr);
      if (parentId !== overParentId) return;

      const next = reorderChildren(tree, parentId, activeIdStr, overIdStr);
      onChange(next);
    },
    [tree, onChange],
  );

  const handleUpdateConfig = useCallback(
    (patch: Record<string, any>) => {
      if (!selectedId) return;
      const next = updateNodeConfig(tree, selectedId, patch);
      onChange(next);
    },
    [tree, selectedId, onChange],
  );

  const handleDelete = useCallback(() => {
    if (!selectedId || selectedId === "root") return;
    const next = deleteNode(tree, selectedId);
    onChange(next);
    setSelectedId(null);
  }, [tree, selectedId, onChange]);

  const selectedNode = selectedId ? tree[selectedId] || null : null;
  const activeNode = activeId ? tree[activeId] || null : null;

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={pointerWithin}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div
        style={{
          display: "flex",
          height: "100%",
          width: "100%",
          overflow: "hidden",
        }}
      >
        {/* 左侧面板：4 Tab + 折叠 */}
        <div
          style={{
            width: leftCollapsed ? 0 : 240,
            flexShrink: 0,
            borderRight: "1px solid var(--aos-border)",
            background: "var(--aos-aside)",
            overflow: "visible",
            transition: "width 0.15s",
            position: "relative",
          }}
        >
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setLeftCollapsed((v) => !v);
            }}
            style={{
              ...TOGGLE_BTN,
              position: "absolute",
              right: -12,
              top: 16,
              zIndex: 30,
            }}
            aria-label={leftCollapsed ? "展开面板" : "收起面板"}
          >
            {leftCollapsed ? ">" : "<"}
          </button>
          <div style={{ width: 240, height: "100%", overflow: "hidden", display: "flex", flexDirection: "column" }}>
            {!leftCollapsed && (
              <>
                {/* Tab 切换栏 */}
                <div style={{ display: "flex", borderBottom: "1px solid var(--aos-border)", flexShrink: 0 }}>
                  {([
                    { id: "widgets", label: "添加微件" },
                    { id: "layout", label: "布局" },
                    { id: "variables", label: "变量" },
                    { id: "events", label: "事件" },
                  ] as const).map((tab) => (
                    <button
                      key={tab.id}
                      type="button"
                      onClick={() => setLeftTab(tab.id)}
                      style={{
                        flex: 1,
                        padding: "8px 4px",
                        fontSize: 11,
                        fontWeight: leftTab === tab.id ? 600 : 400,
                        border: "none",
                        background: leftTab === tab.id ? "var(--aos-surface)" : "transparent",
                        color: leftTab === tab.id ? "var(--aos-accent, #4f46e5)" : "var(--aos-text-muted)",
                        cursor: "pointer",
                        borderBottom: leftTab === tab.id ? "2px solid var(--aos-accent, #4f46e5)" : "2px solid transparent",
                      }}
                    >
                      {tab.label}
                    </button>
                  ))}
                </div>
                {/* Tab 内容 */}
                <div style={{ flex: 1, overflow: "hidden" }}>
                  {leftTab === "widgets" && <PaletteContent />}
                  {leftTab === "layout" && <LayoutTabContent tree={tree} />}
                  {leftTab === "variables" && <VariablesTabContent tree={tree} />}
                  {leftTab === "events" && <EventsTabContent tree={tree} />}
                </div>
              </>
            )}
          </div>
        </div>

        {/* 中间画布 */}
        <div
          style={{
            flex: 1,
            overflow: "auto",
            background: "var(--aos-bg)",
          }}
          onClick={() => setSelectedId(null)}
        >
          <EditorRoot tree={tree} selectedId={selectedId} onSelect={handleSelect} />
        </div>

        {/* 右侧属性面板 */}
        <div
          style={{
            width: rightCollapsed ? 0 : 280,
            borderLeft: "1px solid var(--aos-border)",
            background: "var(--aos-aside)",
            overflow: "visible",
            transition: "width 0.15s",
            position: "relative",
            flexShrink: 0,
          }}
        >
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onToggleRight();
            }}
            style={{
              ...TOGGLE_BTN,
              position: "absolute",
              left: -12,
              top: 16,
              zIndex: 30,
            }}
            aria-label={rightCollapsed ? "展开属性面板" : "收起属性面板"}
          >
            {rightCollapsed ? "<" : ">"}
          </button>
          <div style={{ width: 280, height: "100%", overflow: "hidden" }}>
            {!rightCollapsed && (
              <div style={{ width: 280, height: "100%", overflowY: "auto" }}>
                <PropertyPanel
                  nodeId={selectedId}
                  node={selectedNode}
                  onUpdate={handleUpdateConfig}
                  onDelete={handleDelete}
                />
              </div>
            )}
          </div>
        </div>
      </div>

      <DragOverlay>
        {activeNode ? (
          <div
            style={{
              padding: "8px 12px",
              borderRadius: 2,
              background: "var(--aos-surface)",
              border: "1px solid var(--aos-accent)",
              fontSize: 12,
              boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
              opacity: 0.9,
            }}
          >
            {activeNode.type} · {activeId}
          </div>
        ) : activePaletteType ? (
          (() => {
            const item = getWidgetPlugin(activePaletteType);
            if (!item) return null;
            return (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "8px 12px",
                  borderRadius: 2,
                  background: "var(--aos-surface)",
                  border: "1px solid var(--aos-accent)",
                  fontSize: 12,
                  boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
                  opacity: 0.9,
                }}
              >
                <span>{item.icon}</span>
                <span>{item.name}</span>
              </div>
            );
          })()
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}

function EditorRoot({
  tree,
  selectedId,
  onSelect,
}: {
  tree: ComponentTree;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const root = tree["root"];
  if (!root) {
    return (
      <div style={{ padding: 24, color: "var(--aos-text-muted)", textAlign: "center" }}>
        组件树缺少 root 节点
      </div>
    );
  }
  if (isContainerNode(root)) {
    return (
      <ContainerRenderer
        nodeId="root"
        node={root}
        components={tree}
        selectedId={selectedId}
        onSelect={onSelect}
        depth={0}
      />
    );
  }
  return (
    <SortableItem
      nodeId="root"
      node={root}
      components={tree}
      selectedId={selectedId}
      onSelect={onSelect}
      depth={0}
    />
  );
}

export { isContainerNode, findParentId, deleteNode, updateNodeConfig };
