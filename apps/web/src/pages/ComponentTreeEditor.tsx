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

// ── Types & Consts ─────────────────────────────────────────────────────────

const CONTAINER_TYPES = new Set<string>(["page-layout", "horizontal-grid"]);

function isContainerNode(node: ComponentNode): boolean {
  return CONTAINER_TYPES.has(node.type);
}

type PaletteItem = {
  type: string;
  name: string;
  icon: string;
  defaultConfig: Record<string, any>;
};

const WIDGET_PALETTE: PaletteItem[] = [
  // ── Layout 容器 ──
  { type: "page-layout", name: "页面布局", icon: "📐", defaultConfig: { padding: 24, gap: 16 } },
  { type: "horizontal-grid", name: "水平网格", icon: "⊞", defaultConfig: { cols: 4, gap: 16 } },
  // ── 页面组件 ──
  { type: "page-header", name: "页头", icon: "🏷", defaultConfig: { title: "新页面", subtitle: "页面副标题" } },
  { type: "stat-card", name: "统计卡片", icon: "�", defaultConfig: { title: "统计项", objectType: "", color: "blue" } },
  { type: "filter-bar", name: "筛选栏", icon: "�", defaultConfig: { objectType: "" } },
  { type: "object-table", name: "对象表格", icon: "�", defaultConfig: { objectType: "" } },
  { type: "detail-drawer", name: "详情抽屉", icon: "�", defaultConfig: { objectType: "" } },
  { type: "trend-chart", name: "趋势图", icon: "📉", defaultConfig: { objectType: "" } },
  // ── 原有 Canvas Widget ──
  { type: "filter", name: "Filter List", icon: "�", defaultConfig: { site: "", objectType: "" } },
  { type: "table", name: "Object Table", icon: "📊", defaultConfig: { objectType: "" } },
  { type: "buddy", name: "Buddy Chip", icon: "💬", defaultConfig: {} },
  { type: "overlay", name: "Object View · Wiki", icon: "🗺", defaultConfig: { objectType: "" } },
  { type: "action", name: "Action 表单", icon: "📝", defaultConfig: { actionTypeId: "" } },
  { type: "graph", name: "关系图", icon: "📈", defaultConfig: { objectType: "" } },
  { type: "metric", name: "指标卡", icon: "📄", defaultConfig: { metric: "", title: "" } },
  { type: "stub", name: "Stub 插件", icon: "🔘", defaultConfig: {} },
];

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

function PaletteItem({ item }: { item: PaletteItem }) {
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
        borderRadius: 6,
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

  return (
    <div style={{ padding: 12, display: "flex", flexDirection: "column", gap: 12 }}>
      <div
        style={{
          fontSize: 12,
          fontWeight: 600,
          color: "var(--aos-text)",
          paddingBottom: 8,
          borderBottom: "1px solid var(--aos-border)",
        }}
      >
        {node.type} · {nodeId}
      </div>

      {node.type === "page-header" && (
        <>
          <PropField label="标题">
            <input
              type="text"
              value={node.config?.title || ""}
              onChange={(e) => onUpdate({ title: e.target.value })}
              style={inputStyle}
            />
          </PropField>
          <PropField label="副标题">
            <input
              type="text"
              value={node.config?.subtitle || ""}
              onChange={(e) => onUpdate({ subtitle: e.target.value })}
              style={inputStyle}
            />
          </PropField>
        </>
      )}

      {node.type === "stat-card" && (
        <>
          <PropField label="标题">
            <input
              type="text"
              value={node.config?.title || ""}
              onChange={(e) => onUpdate({ title: e.target.value })}
              style={inputStyle}
            />
          </PropField>
          <PropField label="对象类型">
            <input
              type="text"
              value={node.config?.objectType || ""}
              onChange={(e) => onUpdate({ objectType: e.target.value })}
              style={inputStyle}
            />
          </PropField>
          <PropField label="颜色">
            <select
              value={node.config?.color || "blue"}
              onChange={(e) => onUpdate({ color: e.target.value })}
              style={inputStyle}
            >
              <option value="blue">蓝色</option>
              <option value="amber">琥珀</option>
              <option value="green">绿色</option>
              <option value="indigo">靛蓝</option>
              <option value="violet">紫色</option>
            </select>
          </PropField>
        </>
      )}

      {node.type === "horizontal-grid" && (
        <>
          <PropField label="列数">
            <input
              type="number"
              value={node.config?.cols ?? 4}
              onChange={(e) => onUpdate({ cols: Number(e.target.value) })}
              style={inputStyle}
              min={1}
              max={12}
            />
          </PropField>
          <PropField label="间距">
            <input
              type="number"
              value={node.config?.gap ?? 16}
              onChange={(e) => onUpdate({ gap: Number(e.target.value) })}
              style={inputStyle}
              min={0}
            />
          </PropField>
        </>
      )}

      {node.type === "page-layout" && (
        <>
          <PropField label="内边距">
            <input
              type="number"
              value={node.config?.padding ?? 24}
              onChange={(e) => onUpdate({ padding: Number(e.target.value) })}
              style={inputStyle}
              min={0}
            />
          </PropField>
          <PropField label="间距">
            <input
              type="number"
              value={node.config?.gap ?? 16}
              onChange={(e) => onUpdate({ gap: Number(e.target.value) })}
              style={inputStyle}
              min={0}
            />
          </PropField>
        </>
      )}

      {(node.type === "filter-bar" ||
        node.type === "object-table" ||
        node.type === "detail-drawer" ||
        node.type === "trend-chart" ||
        node.type === "filter" ||
        node.type === "table" ||
        node.type === "overlay" ||
        node.type === "graph") && (
        <PropField label="对象类型">
          <input
            type="text"
            value={node.config?.objectType || ""}
            onChange={(e) => onUpdate({ objectType: e.target.value })}
            style={inputStyle}
          />
        </PropField>
      )}

      {node.type === "filter" && (
        <PropField label="站点">
          <input
            type="text"
            value={node.config?.site || ""}
            onChange={(e) => onUpdate({ site: e.target.value })}
            style={inputStyle}
          />
        </PropField>
      )}

      {node.type === "action" && (
        <PropField label="操作类型 ID">
          <input
            type="text"
            value={node.config?.actionTypeId || ""}
            onChange={(e) => onUpdate({ actionTypeId: e.target.value })}
            style={inputStyle}
          />
        </PropField>
      )}

      {node.type === "metric" && (
        <>
          <PropField label="指标">
            <input
              type="text"
              value={node.config?.metric || ""}
              onChange={(e) => onUpdate({ metric: e.target.value })}
              style={inputStyle}
            />
          </PropField>
          <PropField label="标题">
            <input
              type="text"
              value={node.config?.title || ""}
              onChange={(e) => onUpdate({ title: e.target.value })}
              style={inputStyle}
            />
          </PropField>
        </>
      )}

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

  // persist leftCollapsed
  useEffect(() => {
    window.localStorage.setItem("canvas.editor.leftCollapsed", leftCollapsed ? "1" : "0");
  }, [leftCollapsed]);

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
        const paletteItem = WIDGET_PALETTE.find((w) => w.type === widgetType);
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
        {/* 左侧调色板 */}
        <div
          style={{
            width: leftCollapsed ? 0 : 200,
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
            aria-label={leftCollapsed ? "展开组件库" : "收起组件库"}
          >
            {leftCollapsed ? ">" : "<"}
          </button>
          <div style={{ width: 200, height: "100%", overflow: "hidden" }}>
            {!leftCollapsed && (
            <div
              style={{
                width: 200,
                height: "100%",
                padding: 12,
                overflowY: "auto",
                display: "flex",
                flexDirection: "column",
                gap: 8,
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
              <div
                style={{
                  fontSize: 10,
                  fontWeight: 600,
                  color: "var(--aos-text-muted)",
                  marginTop: 4,
                  marginBottom: 2,
                }}
              >
                Layout
              </div>
              {WIDGET_PALETTE.filter((w) => w.type === "page-layout" || w.type === "horizontal-grid").map((item) => (
                <PaletteItem key={item.type} item={item} />
              ))}
              <div
                style={{
                  fontSize: 10,
                  fontWeight: 600,
                  color: "var(--aos-text-muted)",
                  marginTop: 4,
                  marginBottom: 2,
                }}
              >
                页面组件
              </div>
              {WIDGET_PALETTE.filter((w) => ["page-header","stat-card","filter-bar","object-table","detail-drawer","trend-chart"].includes(w.type)).map((item) => (
                <PaletteItem key={item.type} item={item} />
              ))}
              <div
                style={{
                  fontSize: 10,
                  fontWeight: 600,
                  color: "var(--aos-text-muted)",
                  marginTop: 4,
                  marginBottom: 2,
                }}
              >
                Widget 组件
              </div>
              {WIDGET_PALETTE.filter((w) => ["filter","table","buddy","overlay","action","graph","metric","stub"].includes(w.type)).map((item) => (
                <PaletteItem key={item.type} item={item} />
              ))}
              <a
                href="/workshop/widget-registry"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                  padding: "6px 10px",
                  marginTop: 6,
                  borderRadius: 6,
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
              borderRadius: 6,
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
            const item = WIDGET_PALETTE.find((w) => w.type === activePaletteType);
            if (!item) return null;
            return (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "8px 12px",
                  borderRadius: 6,
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
