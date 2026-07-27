import { describe, expect, it } from "vitest";
import {
  emptyWikiPage,
  emptyWidget,
  isValidWidgetId,
  validateWikiPage,
  resolveVariable,
  resolveAllVariables,
  flattenWidgetTree,
  summarizeWidgets,
  modeLabel,
  statusLabel,
  WIDGET_KIND_LABELS,
  WORKFLOW_NODE_TYPES,
  MOCK_WIKI_PAGE,
  type WikiWidget,
  type WikiPage,
} from "./WikiDetailPage";

describe("WikiDetailPage · emptyWikiPage", () => {
  it("creates a wiki page with default values", () => {
    const p = emptyWikiPage();
    expect(p.title).toBe("");
    expect(p.version).toBe(1);
    expect(p.status).toBe("draft");
    expect(p.widgets).toEqual([]);
  });

  it("accepts branch parameter", () => {
    const p = emptyWikiPage("feature");
    expect(p.branch).toBe("feature");
  });
});

describe("WikiDetailPage · emptyWidget", () => {
  it("creates a widget with id", () => {
    const w = emptyWidget("text");
    expect(w.id).toBeTruthy();
    expect(w.kind).toBe("text");
  });
});

describe("WikiDetailPage · isValidWidgetId", () => {
  it("accepts valid identifiers", () => {
    expect(isValidWidgetId("w_nav_bar")).toBe(true);
    expect(isValidWidgetId("_private")).toBe(true);
    expect(isValidWidgetId("widget123")).toBe(true);
  });

  it("rejects invalid identifiers", () => {
    expect(isValidWidgetId("")).toBe(false);
    expect(isValidWidgetId("123abc")).toBe(false);
    expect(isValidWidgetId("has space")).toBe(false);
  });
});

describe("WikiDetailPage · validateWikiPage", () => {
  it("passes for valid page", () => {
    const p: WikiPage = {
      ...emptyWikiPage(),
      id: "wiki-test",
      title: "Test Page",
      widgets: [{ id: "w1", kind: "text", name: "title", children: [], content: "hello" }],
    };
    expect(validateWikiPage(p)).toHaveLength(0);
  });

  it("catches empty id", () => {
    const p: WikiPage = { ...emptyWikiPage(), title: "T" };
    expect(validateWikiPage(p)).toContain("id 不能为空");
  });

  it("catches empty title", () => {
    const p: WikiPage = { ...emptyWikiPage(), id: "wiki-x" };
    expect(validateWikiPage(p)).toContain("title 不能为空");
  });

  it("catches invalid id format", () => {
    const p: WikiPage = { ...emptyWikiPage(), id: "wiki!bad", title: "T" };
    expect(validateWikiPage(p)).toContain("id 必须以字母或下划线开头，只允许字母、数字、下划线、连字符");
  });

  it("catches duplicate widget ids", () => {
    const p: WikiPage = {
      ...emptyWikiPage(),
      id: "wiki-x",
      title: "T",
      widgets: [
        { id: "dup", kind: "text", name: "a", children: [], content: "" },
        { id: "dup", kind: "text", name: "b", children: [], content: "" },
      ],
    };
    expect(validateWikiPage(p)).toContain('widget id "dup" 重复');
  });

  it("catches invalid widget id", () => {
    const p: WikiPage = {
      ...emptyWikiPage(),
      id: "wiki-x",
      title: "T",
      widgets: [{ id: "123bad", kind: "text", name: "a", children: [], content: "" }],
    };
    expect(validateWikiPage(p)).toContain('widget id "123bad" 格式不合法');
  });
});

describe("WikiDetailPage · resolveVariable", () => {
  it("resolves ${$user.name} patterns", () => {
    const vars = { "$user.name": "李明" };
    expect(resolveVariable("Hello ${$user.name}", vars)).toBe("Hello 李明");
  });

  it("resolves ${user.name} without leading $", () => {
    const vars = { "$user.name": "李明" };
    expect(resolveVariable("Hello ${user.name}", vars)).toBe("Hello 李明");
  });

  it("leaves unresolved as-is", () => {
    const vars = {};
    expect(resolveVariable("Hello ${$user.name}", vars)).toBe("Hello ${$user.name}");
  });
});

describe("WikiDetailPage · resolveAllVariables", () => {
  it("resolves all known variables", () => {
    const vars = { "$user.name": "李明", "$page.version": "v9" };
    const { resolved, unresolved } = resolveAllVariables("User: $user.name, Page: $page.version", vars);
    expect(resolved).toContain("李明");
    expect(resolved).toContain("v9");
    expect(unresolved).toHaveLength(0);
  });

  it("reports unresolved variables", () => {
    const { unresolved } = resolveAllVariables("$user.name and $page.version", {});
    expect(unresolved.length).toBe(2);
  });
});

describe("WikiDetailPage · flattenWidgetTree", () => {
  it("flattens a simple tree", () => {
    const widgets: WikiWidget[] = [
      { id: "root", kind: "container", name: "root", children: ["child1", "child2"], content: "" },
      { id: "child1", kind: "text", name: "c1", children: [], content: "a" },
      { id: "child2", kind: "text", name: "c2", children: [], content: "b" },
    ];
    const flat = flattenWidgetTree(widgets);
    expect(flat.length).toBe(3);
    expect(flat[0].id).toBe("root");
  });

  it("handles circular refs gracefully", () => {
    const widgets: WikiWidget[] = [
      { id: "a", kind: "container", name: "a", children: ["b"], content: "" },
      { id: "b", kind: "container", name: "b", children: ["a"], content: "" },
    ];
    const flat = flattenWidgetTree(widgets);
    expect(flat.length).toBe(2);
  });
});

describe("WikiDetailPage · summarizeWidgets", () => {
  it("counts each kind", () => {
    const widgets: WikiWidget[] = [
      { id: "1", kind: "text", name: "a", children: [], content: "" },
      { id: "2", kind: "text", name: "b", children: [], content: "" },
      { id: "3", kind: "table", name: "c", children: [], content: "" },
    ];
    const s = summarizeWidgets(widgets);
    expect(s.text).toBe(2);
    expect(s.table).toBe(1);
  });

  it("returns zeros for empty", () => {
    const s = summarizeWidgets([]);
    expect(s.container).toBe(0);
  });
});

describe("WikiDetailPage · labels", () => {
  it("modeLabel returns labels", () => {
    expect(modeLabel("widget")).toBe("微件");
    expect(modeLabel("workflow")).toBe("工作流");
    expect(modeLabel("runtime")).toBe("预览");
  });

  it("statusLabel returns labels", () => {
    expect(statusLabel("draft")).toBe("草稿");
    expect(statusLabel("published")).toBe("已发布");
  });

  it("WIDGET_KIND_LABELS has 6 kinds", () => {
    expect(Object.keys(WIDGET_KIND_LABELS)).toHaveLength(6);
  });
});

describe("WikiDetailPage · WORKFLOW_NODE_TYPES", () => {
  it("has trigger, condition, and action types", () => {
    const types = new Set(WORKFLOW_NODE_TYPES.map((n) => n.type));
    expect(types.has("trigger")).toBe(true);
    expect(types.has("condition")).toBe(true);
    expect(types.has("action")).toBe(true);
  });

  it("all nodes have label and color", () => {
    for (const n of WORKFLOW_NODE_TYPES) {
      expect(n.label).toBeTruthy();
      expect(n.color).toBeTruthy();
    }
  });
});

describe("WikiDetailPage · MOCK_WIKI_PAGE", () => {
  it("has widgets and variables", () => {
    expect(MOCK_WIKI_PAGE.widgets.length).toBeGreaterThan(0);
    expect(Object.keys(MOCK_WIKI_PAGE.variables).length).toBeGreaterThan(0);
  });
});
