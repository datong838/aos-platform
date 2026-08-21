/** W-T1: encode Tools panel prefs into AgentInstance Overlay tool items. */

export type ToolsPanelHitl = "auto" | "form" | "draft";

export type ToolsPanelOverlayItem = {
  id: string;
  name: string;
  category: string;
  enabled: boolean;
};

export type ToolsPanelDecoded = {
  toolItems: ToolsPanelOverlayItem[];
  mode: string;
  hitl: ToolsPanelHitl;
  categories: Set<string>;
};

const MODE_ID = "panel.cfg.mode";
const HITL_ID = "panel.cfg.hitl";

export function isPanelMetaToolId(id: string): boolean {
  return id === MODE_ID || id === HITL_ID || id.startsWith("panel.cfg.");
}

export function encodeToolsPanelOverlay(input: {
  tools: Array<{ id: string; name?: string; kind?: string; category?: string }>;
  mode: string;
  hitl: ToolsPanelHitl;
}): ToolsPanelOverlayItem[] {
  const items: ToolsPanelOverlayItem[] = input.tools
    .filter((t) => t.id && !isPanelMetaToolId(t.id))
    .map((t) => ({
      id: t.id,
      name: t.name || t.id,
      category: t.category || t.kind || "tool",
      enabled: true,
    }));
  items.push({
    id: MODE_ID,
    name: input.mode || "native",
    category: "panel",
    enabled: true,
  });
  items.push({
    id: HITL_ID,
    name: input.hitl || "form",
    category: "panel",
    enabled: true,
  });
  return items;
}

export function decodeToolsPanelOverlay(
  items: ToolsPanelOverlayItem[] | undefined | null,
  opts: {
    defaultCategories: string[];
    defaultMode?: string;
    defaultHitl?: ToolsPanelHitl;
  },
): ToolsPanelDecoded {
  const defaultMode = opts.defaultMode ?? "native";
  const defaultHitl = opts.defaultHitl ?? "form";
  const list = Array.isArray(items) ? items : [];
  let mode = defaultMode;
  let hitl: ToolsPanelHitl = defaultHitl;
  const toolItems: ToolsPanelOverlayItem[] = [];
  const categories = new Set<string>();

  for (const raw of list) {
    const id = String(raw?.id || "").trim();
    if (!id) continue;
    if (id === MODE_ID) {
      mode = String(raw.name || defaultMode);
      continue;
    }
    if (id === HITL_ID) {
      const v = String(raw.name || defaultHitl);
      if (v === "auto" || v === "form" || v === "draft") hitl = v;
      continue;
    }
    if (isPanelMetaToolId(id)) continue;
    if (raw.enabled === false) continue;
    const category = String(raw.category || "tool");
    toolItems.push({
      id,
      name: String(raw.name || id),
      category,
      enabled: true,
    });
    if (category && category !== "panel") categories.add(category);
  }

  if (toolItems.length === 0 && categories.size === 0) {
    for (const c of opts.defaultCategories) categories.add(c);
  }

  return { toolItems, mode, hitl, categories };
}
