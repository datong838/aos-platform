import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiGet, apiPut } from "../../api/client";
import { S2Chrome } from "./shared";
import { BpBanner, BpToolbar } from "./blueprintUi";


/* ────────────── Types ────────────── */

export type WikiMode = "widget" | "workflow" | "runtime";
export type WidgetKind = "container" | "text" | "table" | "chart" | "objectSet" | "image";

export interface WikiWidget {
  id: string;
  kind: WidgetKind;
  name: string;
  children: string[];
  content: string;
}

export interface WikiPage {
  id: string;
  title: string;
  branch: string;
  version: number;
  status: "draft" | "published";
  widgets: WikiWidget[];
  variables: Record<string, string>;
  updatedAt: string;
  updatedBy: string;
}

export interface WikiVersion {
  version: number;
  message: string;
  author: string;
  timestamp: string;
}

/* ────────────── Constants ────────────── */

export const WIDGET_KIND_LABELS: Record<WidgetKind, string> = {
  container: "容器",
  text: "文本",
  table: "表格",
  chart: "图表",
  objectSet: "对象集",
  image: "图片",
};

export const MOCK_WIKI_PAGE: WikiPage = {
  id: "wiki-covid-homepage",
  title: "COVID-19 Homepage Skeleton",
  branch: "main",
  version: 9,
  status: "draft",
  updatedAt: "2026-07-25T16:42:00Z",
  updatedBy: "大同",
  widgets: [
    {
      id: "w_start_container",
      kind: "container",
      name: "开始容器",
      children: ["w_nav_bar", "w_hero"],
      content: "",
    },
    {
      id: "w_nav_bar",
      kind: "container",
      name: "导航栏",
      children: ["w_widget48", "w_widget36"],
      content: "",
    },
    {
      id: "w_hero",
      kind: "text",
      name: "主标题区",
      children: [],
      content: "# COVID-19 疫情追踪\n\n平台资源，用于追踪疫情、医疗和人口统计数据。",
    },
    {
      id: "w_patient_table",
      kind: "objectSet",
      name: "已康复患者",
      children: [],
      content: "s_object_set1 WHERE 已康复 = true",
    },
  ],
  variables: {
    "$user.name": "李明",
    "$user.role": "分析师",
    "$user.team": "售后退货分析组",
    "$page.version": "v9",
  },
};

export const MOCK_VERSIONS: WikiVersion[] = [
  { version: 9, message: "新增跨境发货因子和新客首单判定", author: "大同", timestamp: "2026-07-25T16:42:00Z" },
  { version: 8, message: "调整 medium 等级阈值从 $200 到 $100", author: "风控组", timestamp: "2026-07-24T14:30:00Z" },
  { version: 7, message: "补充 critical 级别的安全团队介入流程", author: "大同", timestamp: "2026-07-22T10:00:00Z" },
  { version: 6, message: "从 feature/risk-model-v2 合并 LLM 提示词优化", author: "系统", timestamp: "2026-07-20T12:00:00Z" },
];

export const WORKFLOW_NODE_TYPES = [
  { type: "trigger", label: "页面加载", color: "#F59E0B" },
  { type: "trigger", label: "定时触发", color: "#F59E0B" },
  { type: "trigger", label: "对象变更", color: "#F59E0B" },
  { type: "condition", label: "IF / ELSE", color: "#3B82F6" },
  { type: "condition", label: "Switch 多分支", color: "#3B82F6" },
  { type: "action", label: "查询对象集", color: "#10B981" },
  { type: "action", label: "执行函数", color: "#10B981" },
  { type: "action", label: "发送通知", color: "#10B981" },
  { type: "action", label: "调用 AIP Agent", color: "#8B5CF6" },
] as const;

/* ────────────── Pure functions ────────────── */

export function emptyWikiPage(branch = "main"): WikiPage {
  return {
    id: "",
    title: "",
    branch,
    version: 1,
    status: "draft",
    widgets: [],
    variables: {},
    updatedAt: new Date().toISOString(),
    updatedBy: "",
  };
}

export function emptyWidget(kind: WidgetKind = "container"): WikiWidget {
  return {
    id: `w_${Date.now()}`,
    kind,
    name: "新组件",
    children: [],
    content: "",
  };
}

export function isValidWidgetId(id: string): boolean {
  return /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(id);
}

export function validateWikiPage(page: WikiPage): string[] {
  const errors: string[] = [];
  if (!page.id || !page.id.trim()) errors.push("id 不能为空");
  if (page.id && !/^[a-zA-Z_][a-zA-Z0-9_-]*$/.test(page.id))
    errors.push("id 必须以字母或下划线开头，只允许字母、数字、下划线、连字符");
  if (!page.title || !page.title.trim()) errors.push("title 不能为空");
  const idSet = new Set<string>();
  for (const w of page.widgets) {
    if (!w.id.trim()) errors.push("widget id 不能为空");
    if (w.id && !isValidWidgetId(w.id)) errors.push(`widget id "${w.id}" 格式不合法`);
    if (idSet.has(w.id)) errors.push(`widget id "${w.id}" 重复`);
    idSet.add(w.id);
  }
  return errors;
}

export function resolveVariable(template: string, variables: Record<string, string>): string {
  return template.replace(/\$\{([^}]+)\}/g, (_, key: string) => {
    const k = key.startsWith("$") ? key : `$${key}`;
    return variables[k] ?? variables[key] ?? `\${${key}}`;
  });
}

export function resolveAllVariables(
  content: string,
  variables: Record<string, string>,
): { resolved: string; unresolved: string[] } {
  const unresolved: string[] = [];
  const resolved = content.replace(/\$user\.\w+|\$page\.\w+|\$objectSet\.\w+|\$\w+/g, (match) => {
    if (variables[match] != null) return variables[match];
    unresolved.push(match);
    return match;
  });
  return { resolved, unresolved };
}

export function flattenWidgetTree(widgets: WikiWidget[]): WikiWidget[] {
  const map = new Map<string, WikiWidget>();
  for (const w of widgets) map.set(w.id, w);
  const visited = new Set<string>();
  const result: WikiWidget[] = [];
  function visit(id: string, depth: number) {
    if (visited.has(id)) return;
    visited.add(id);
    const w = map.get(id);
    if (!w) return;
    result.push({ ...w, children: [...w.children] });
    for (const child of w.children) visit(child, depth + 1);
  }
  const roots = widgets.filter((w) => !widgets.some((other) => other.children.includes(w.id)));
  for (const r of roots) visit(r.id, 0);
  for (const w of widgets) {
    if (!visited.has(w.id)) result.push(w);
  }
  return result;
}

export function summarizeWidgets(widgets: WikiWidget[]): Record<WidgetKind, number> {
  const summary: Record<WidgetKind, number> = {
    container: 0,
    text: 0,
    table: 0,
    chart: 0,
    objectSet: 0,
    image: 0,
  };
  for (const w of widgets) {
    summary[w.kind]++;
  }
  return summary;
}

export function modeLabel(mode: WikiMode): string {
  return { widget: "微件", workflow: "工作流", runtime: "预览" }[mode];
}

export function statusLabel(status: WikiPage["status"]): string {
  return status === "draft" ? "草稿" : "已发布";
}

/* ────────────── API mapping (W3-C1) ────────────── */

export type WikiDataSource = "live" | "demo";

export interface ApiWikiRow {
  id: string;
  title: string;
  content?: string;
  object_type_id?: string;
  tags?: string[];
  author?: string;
  version: number;
  widgets?: WikiWidget[];
  variables?: Record<string, string>;
  created_at?: number;
  updated_at?: number;
}

export interface ApiWikiVersionRow {
  id?: string;
  wiki_id?: string;
  version: number;
  content?: string;
  title?: string;
  author?: string;
  message?: string;
  created_at?: number;
}

export function tsToIso(ts: number | string | undefined): string {
  if (ts == null || ts === "") return new Date().toISOString();
  if (typeof ts === "string") {
    const n = Number(ts);
    if (!Number.isNaN(n) && n > 1e9 && n < 1e12) return new Date(n * 1000).toISOString();
    return ts.includes("T") ? ts : new Date(ts).toISOString();
  }
  // engine 存 unix 秒
  return new Date(ts > 1e12 ? ts : ts * 1000).toISOString();
}

export function mapApiWikiToPage(row: ApiWikiRow, branch = "main"): WikiPage {
  const content = row.content ?? "";
  return {
    id: row.id,
    title: row.title,
    branch,
    version: row.version ?? 1,
    status: "draft",
    widgets: row.widgets?.length ? row.widgets : [
      {
        id: "w_main_content",
        kind: "text",
        name: "主内容",
        children: [],
        content,
      },
    ],
    variables: row.variables || {
      "$page.version": `v${row.version ?? 1}`,
      "$user.name": row.author || "system",
    },
    updatedAt: tsToIso(row.updated_at),
    updatedBy: row.author || "system",
  };
}

export function mapApiVersions(items: ApiWikiVersionRow[]): WikiVersion[] {
  return [...items]
    .sort((a, b) => b.version - a.version)
    .map((v) => ({
      version: v.version,
      message: v.message || "",
      author: v.author || "system",
      timestamp: tsToIso(v.created_at),
    }));
}

/** 主内容：优先 w_main_content，否则首个 text widget */
export function extractMainContent(page: WikiPage): string {
  const main = page.widgets.find((w) => w.id === "w_main_content");
  if (main) return main.content;
  const text = page.widgets.find((w) => w.kind === "text");
  return text?.content ?? "";
}

export function applyMainContent(page: WikiPage, content: string): WikiPage {
  const hasMain = page.widgets.some((w) => w.id === "w_main_content");
  if (hasMain) {
    return {
      ...page,
      widgets: page.widgets.map((w) => (w.id === "w_main_content" ? { ...w, content } : w)),
    };
  }
  const firstText = page.widgets.find((w) => w.kind === "text");
  if (firstText) {
    return {
      ...page,
      widgets: page.widgets.map((w) => (w.id === firstText.id ? { ...w, content } : w)),
    };
  }
  return {
    ...page,
    widgets: [
      { id: "w_main_content", kind: "text", name: "主内容", children: [], content },
      ...page.widgets,
    ],
  };
}

export function buildWikiUpdateBody(
  page: WikiPage,
  title: string,
  message = "",
): { title: string; content: string; author: string; message: string; widgets: WikiWidget[]; variables: Record<string, string>; expected_version: number } {
  return {
    title,
    content: extractMainContent(page),
    author: page.updatedBy || "大同",
    message: message || `Update v${page.version + 1}`,
    widgets: page.widgets,
    variables: page.variables,
    expected_version: page.version,
  };
}

/** API 失败时本地落盘：升版本并写入版本列表头 */
export function localSavePage(
  page: WikiPage,
  title: string,
  versions: WikiVersion[],
): { page: WikiPage; versions: WikiVersion[] } {
  const nextVersion = page.version + 1;
  const now = new Date().toISOString();
  const nextPage: WikiPage = {
    ...page,
    title,
    version: nextVersion,
    updatedAt: now,
    variables: { ...page.variables, "$page.version": `v${nextVersion}` },
  };
  const entry: WikiVersion = {
    version: nextVersion,
    message: `本地保存 v${nextVersion}`,
    author: page.updatedBy || "本地",
    timestamp: now,
  };
  return { page: nextPage, versions: [entry, ...versions.filter((v) => v.version !== nextVersion)] };
}

/* ────────────── Component ────────────── */

export function WikiDetailPage() {
  const { wikiId = "wiki-covid-homepage" } = useParams();
  const [page, setPage] = useState<WikiPage>(() => MOCK_WIKI_PAGE);
  const [mode, setMode] = useState<WikiMode>("widget");
  const [selectedWidgetId, setSelectedWidgetId] = useState<string>("");
  const [titleDraft, setTitleDraft] = useState(page.title);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [versions, setVersions] = useState<WikiVersion[]>(MOCK_VERSIONS);
  const [dataSource, setDataSource] = useState<WikiDataSource>("demo");

  useEffect(() => {
    if (wikiId === "new") {
      const base = emptyWikiPage();
      setPage(base);
      setTitleDraft(base.title);
      setSelectedWidgetId(base.widgets[0]?.id ?? "");
      setVersions([]);
      setDataSource("demo");
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const row = await apiGet<ApiWikiRow>(`/v1/ontology/wikis/${encodeURIComponent(wikiId)}`);
        if (cancelled) return;
        const mapped = mapApiWikiToPage(row);
        setPage(mapped);
        setTitleDraft(mapped.title);
        setSelectedWidgetId(mapped.widgets[0]?.id ?? "");
        setDataSource("live");
        setErr("");
        try {
          const ver = await apiGet<{ items: ApiWikiVersionRow[] }>(
            `/v1/ontology/wikis/${encodeURIComponent(wikiId)}/versions`,
          );
          if (!cancelled && ver.items?.length) setVersions(mapApiVersions(ver.items));
        } catch {
          if (!cancelled) setVersions(MOCK_VERSIONS);
        }
      } catch (e) {
        if (cancelled) return;
        const base = wikiId === "wiki-covid-homepage" ? MOCK_WIKI_PAGE : { ...MOCK_WIKI_PAGE, id: wikiId, title: wikiId };
        setPage(base);
        setTitleDraft(base.title);
        setSelectedWidgetId(base.widgets[0]?.id ?? "");
        setVersions(MOCK_VERSIONS);
        setDataSource("demo");
        setErr("");
        setMsg(`演示路径 · API 不可用（${String((e as Error).message || e)}），已加载本地数据`);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [wikiId]);

  const flatWidgets = useMemo(() => flattenWidgetTree(page.widgets), [page.widgets]);
  const selectedWidget = useMemo(
    () => page.widgets.find((w) => w.id === selectedWidgetId) ?? null,
    [page.widgets, selectedWidgetId],
  );
  const summary = useMemo(() => summarizeWidgets(page.widgets), [page.widgets]);
  const runtimeResolved = useMemo(() => {
    if (mode !== "runtime") return null;
    const heroContent = page.widgets.find((w) => w.kind === "text");
    if (!heroContent) return { resolved: "", unresolved: [] as string[] };
    return resolveAllVariables(heroContent.content, page.variables);
  }, [mode, page.widgets, page.variables]);

  function patchWidget(id: string, updates: Partial<WikiWidget>) {
    setPage((p) => ({
      ...p,
      widgets: p.widgets.map((w) => (w.id === id ? { ...w, ...updates } : w)),
    }));
  }

  function addWidget(kind: WidgetKind) {
    const w = emptyWidget(kind);
    setPage((p) => ({ ...p, widgets: [...p.widgets, w] }));
    setSelectedWidgetId(w.id);
  }

  function deleteWidget(id: string) {
    setPage((p) => ({
      ...p,
      widgets: p.widgets.filter((w) => w.id !== id).map((w) => ({
        ...w,
        children: w.children.filter((c) => c !== id),
      })),
    }));
    if (selectedWidgetId === id) setSelectedWidgetId("");
  }

  async function save() {
    setBusy(true);
    setMsg("");
    setErr("");
    try {
      const errors = validateWikiPage({ ...page, title: titleDraft });
      if (wikiId === "new") {
        throw new Error("新建 Wiki API 未提供，无法保存");
      }
      if (errors.filter((e) => !e.includes("widget")).length > 0 && !titleDraft.trim()) {
        throw new Error("title 不能为空");
      }
      if (!titleDraft.trim()) throw new Error("title 不能为空");
      const body = buildWikiUpdateBody(page, titleDraft);
      try {
        const saved = await apiPut<ApiWikiRow>(
          `/v1/ontology/wikis/${encodeURIComponent(wikiId)}`,
          body,
        );
        if (saved.id !== wikiId || saved.version !== page.version + 1) throw new Error("写入回包与目标 Wiki 不一致");
        const verified = await apiGet<ApiWikiRow>(`/v1/ontology/wikis/${encodeURIComponent(wikiId)}`);
        const mapped = mapApiWikiToPage(verified, page.branch);
        if (verified.id !== wikiId || JSON.stringify(verified.widgets || []) !== JSON.stringify(body.widgets) || JSON.stringify(verified.variables || {}) !== JSON.stringify(body.variables)) {
          throw new Error("写入已提交但重读核验失败");
        }
        setPage(mapped);
        setTitleDraft(mapped.title);
        setDataSource("live");
        setMsg(`已保存并重读 · v${verified.version}`);
        try {
          const ver = await apiGet<{ items: ApiWikiVersionRow[] }>(
            `/v1/ontology/wikis/${encodeURIComponent(wikiId)}/versions`,
          );
          if (ver.items?.length) setVersions(mapApiVersions(ver.items));
        } catch {
          /* 版本刷新失败不影响保存成功 */
        }
      } catch (apiErr) {
        setErr(String((apiErr as Error).message || apiErr));
      }
    } catch (e) {
      setErr(String((e as Error).message || e));
    } finally {
      setBusy(false);
    }
  }

  function onMainContentChange(content: string) {
    setPage((p) => applyMainContent(p, content));
  }

  const mainContent = extractMainContent(page);

  return (
    <S2Chrome title={`活知识 Wiki · ${titleDraft || "未命名"}`} lede={`v${page.version} · ${page.branch} 分支 · ${statusLabel(page.status)}`}>
      <div className="ont-page w3-c1c5-wiki">
        <BpToolbar>
          <Link to="/ontology/wiki-index" className="btn-nav">
            ← Wiki 索引
          </Link>
          <Link to={`/ontology/wiki/${encodeURIComponent(wikiId)}/diff`} className="btn-nav">
            版本对比 →
          </Link>
          <button type="button" className="btn-primary" disabled={busy || dataSource !== "live" || wikiId === "new"} onClick={() => void save()}>
            {busy ? "保存中…" : "保存"}
          </button>
          <span
            className={
              dataSource === "live" ? "w3-c1c5-source-badge w3-c1c5-source-badge--live" : "w3-c1c5-source-badge w3-c1c5-source-badge--demo"
            }
          >
            {dataSource === "live" ? "真 API" : "演示路径"}
          </span>
        </BpToolbar>

        {dataSource === "demo" && (
          <BpBanner tone="warn">
            演示路径 · Wiki API 不可用或保存已降级；主内容可继续编辑，版本列表为本地数据。
          </BpBanner>
        )}
        {msg && <p className="bp-prop-ok">{msg}</p>}
        {err && <p className="error">{err}</p>}

        {/* 主内容编辑区（C1 验收核心） */}
        <div className="w3-c1c5-main-block">
          <div className="w3-c1c5-main-head">
            <h3 style={styles.sectionTitle}>主内容</h3>
            <span style={styles.mutedText}>Markdown · 保存写入 /v1/ontology/wikis</span>
          </div>
          <textarea
            className="w3-c1c5-main-editor"
            value={mainContent}
            onChange={(e) => onMainContentChange(e.target.value)}
            placeholder="编辑 Wiki 主内容…"
            rows={8}
          />
        </div>

        {/* 顶部栏：标题 + 模式切换 */}
        <div style={styles.topbar}>
          <div style={styles.topbarLeft}>
            <input
              className="aos-input"
              style={{ fontWeight: 600, fontSize: "1rem", minWidth: 240 }}
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              placeholder="Wiki 页面标题"
            />
            <span style={styles.versionBadge}>v{page.version}</span>
          </div>
          <div style={styles.modeSwitcher}>
            {(["widget", "workflow", "runtime"] as WikiMode[]).map((m) => (
              <button
                key={m}
                type="button"
                style={mode === m ? styles.modeBtnActive : styles.modeBtn}
                onClick={() => setMode(m)}
              >
                {modeLabel(m)}
              </button>
            ))}
          </div>
        </div>

        {mode === "widget" && (
          <div style={styles.slateBody}>
            {/* 左：Widget 树 */}
            <aside style={styles.treePanel}>
              <input type="search" placeholder="搜索组件…" style={styles.treeSearch} />
              <div style={styles.treeSectionTitle}>布局</div>
              {flatWidgets.map((w) => (
                <div
                  key={w.id}
                  style={selectedWidgetId === w.id ? styles.treeItemActive : styles.treeItem}
                  onClick={() => setSelectedWidgetId(w.id)}
                >
                  <span style={styles.kindDot} title={WIDGET_KIND_LABELS[w.kind]} />
                  <span style={styles.treeItemName}>{w.name || w.id}</span>
                  <span style={styles.treeItemId}>{w.id}</span>
                </div>
              ))}
              <div style={styles.addWidgetRow}>
                {(["text", "table", "chart", "objectSet"] as WidgetKind[]).map((k) => (
                  <button
                    key={k}
                    type="button"
                    style={styles.addWidgetBtn}
                    onClick={() => addWidget(k)}
                  >
                    + {WIDGET_KIND_LABELS[k]}
                  </button>
                ))}
              </div>
              {selectedWidgetId && (
                <button type="button" style={styles.deleteBtn} onClick={() => deleteWidget(selectedWidgetId)}>
                  删除选中组件
                </button>
              )}
            </aside>

            {/* 中：画布 */}
            <div style={styles.canvas}>
              {selectedWidget ? (
                <div style={styles.widgetCard}>
                  <div style={styles.widgetHeader}>
                    <span style={styles.kindBadge}>{WIDGET_KIND_LABELS[selectedWidget.kind]}</span>
                    <span style={styles.widgetName}>{selectedWidget.name}</span>
                  </div>
                  <div style={styles.widgetBody}>
                    {selectedWidget.kind === "text" && (
                      <textarea
                        style={styles.textArea}
                        value={selectedWidget.content}
                        onChange={(e) => patchWidget(selectedWidget.id, { content: e.target.value })}
                      />
                    )}
                    {selectedWidget.kind === "objectSet" && (
                      <input
                        className="aos-input"
                        style={styles.objectSetInput}
                        value={selectedWidget.content}
                        onChange={(e) => patchWidget(selectedWidget.id, { content: e.target.value })}
                        placeholder="s_object_set WHERE ..."
                      />
                    )}
                    {selectedWidget.kind === "container" && (
                      <p style={styles.mutedText}>
                        容器组件 · {selectedWidget.children.length} 个子组件
                      </p>
                    )}
                    {(selectedWidget.kind === "table" || selectedWidget.kind === "chart") && (
                      <p style={styles.mutedText}>{WIDGET_KIND_LABELS[selectedWidget.kind]} 占位</p>
                    )}
                  </div>
                </div>
              ) : (
                <div style={styles.emptyCanvas}>
                  <p style={styles.mutedText}>从左侧选择一个组件，或添加新组件</p>
                </div>
              )}
            </div>

            {/* 右：属性面板 */}
            <aside style={styles.propsPanel}>
              <div style={styles.propsHeader}>
                <span>属性面板</span>
              </div>
              {selectedWidget ? (
                <div style={{ padding: "0.75rem" }}>
                  <label style={styles.propLabel}>组件名称</label>
                  <input
                    className="aos-input"
                    style={styles.propInput}
                    value={selectedWidget.name}
                    onChange={(e) => patchWidget(selectedWidget.id, { name: e.target.value })}
                  />
                  <label style={styles.propLabel}>组件 ID</label>
                  <input
                    className="aos-input"
                    style={styles.propInput}
                    value={selectedWidget.id}
                    disabled
                  />
                  <label style={styles.propLabel}>类型</label>
                  <select
                    className="aos-input"
                    style={styles.propInput}
                    value={selectedWidget.kind}
                    onChange={(e) => patchWidget(selectedWidget.id, { kind: e.target.value as WidgetKind })}
                  >
                    {Object.entries(WIDGET_KIND_LABELS).map(([k, label]) => (
                      <option key={k} value={k}>
                        {label}
                      </option>
                    ))}
                  </select>
                  <label style={styles.propLabel}>内容（HTML / Markdown）</label>
                  <div style={styles.contentToggle}>
                    <button type="button" style={styles.contentToggleActive}>Markdown</button>
                    <button type="button" style={styles.contentToggleBtn}>HTML</button>
                  </div>
                  <textarea
                    style={styles.codeBlock}
                    value={selectedWidget.content}
                    onChange={(e) => patchWidget(selectedWidget.id, { content: e.target.value })}
                  />
                </div>
              ) : (
                <p style={{ ...styles.mutedText, padding: "0.75rem" }}>未选中组件</p>
              )}
              <div style={styles.summaryBox}>
                <div style={styles.summaryTitle}>组件统计</div>
                {Object.entries(summary).map(([k, v]) => (
                  <div key={k} style={styles.summaryRow}>
                    <span>{WIDGET_KIND_LABELS[k as WidgetKind]}</span>
                    <span style={{ fontWeight: 600 }}>{v}</span>
                  </div>
                ))}
              </div>
            </aside>
          </div>
        )}

        {mode === "workflow" && (
          <div style={styles.workflowPanel}>
            <BpBanner tone="info">
              工作流模式：事件流编排视图（事件 → 条件 → 动作的连线式编排）
            </BpBanner>
            <div style={styles.workflowBody}>
              <div style={styles.wfLeftPanel}>
                <div style={styles.wfSectionTitle}>触发器</div>
                {WORKFLOW_NODE_TYPES.filter((n) => n.type === "trigger").map((n, i) => (
                  <div key={i} style={{ ...styles.wfNodeTemplate, borderColor: n.color }}>
                    <span style={{ ...styles.wfNodeDot, background: n.color }} />
                    {n.label}
                  </div>
                ))}
                <div style={styles.wfSectionTitle}>条件判断</div>
                {WORKFLOW_NODE_TYPES.filter((n) => n.type === "condition").map((n, i) => (
                  <div key={i} style={{ ...styles.wfNodeTemplate, borderColor: n.color }}>
                    <span style={{ ...styles.wfNodeDot, background: n.color }} />
                    {n.label}
                  </div>
                ))}
                <div style={styles.wfSectionTitle}>执行动作</div>
                {WORKFLOW_NODE_TYPES.filter((n) => n.type === "action").map((n, i) => (
                  <div key={i} style={{ ...styles.wfNodeTemplate, borderColor: n.color }}>
                    <span style={{ ...styles.wfNodeDot, background: n.color }} />
                    {n.label}
                  </div>
                ))}
              </div>
              <div style={styles.wfCanvas}>
                <p style={styles.mutedText}>
                  从左侧拖拽节点到画布，或点击节点配置属性
                </p>
              </div>
              <div style={styles.wfRightPanel}>
                <div style={styles.wfSectionTitle}>节点属性</div>
                <p style={styles.mutedText}>选中节点后在此配置属性</p>
              </div>
            </div>
          </div>
        )}

        {mode === "runtime" && (
          <div style={styles.runtimePanel}>
            <BpBanner tone="info">
              运行时预览：$user 等变量已替换为实际用户数据
            </BpBanner>
            {runtimeResolved && (
              <div style={styles.resolvedBox}>
                <pre style={styles.resolvedContent}>{runtimeResolved.resolved}</pre>
                {runtimeResolved.unresolved.length > 0 && (
                  <p style={{ fontSize: "0.75rem", color: "var(--aos-text-secondary)" }}>
                    未解析变量：{runtimeResolved.unresolved.join(", ")}
                  </p>
                )}
              </div>
            )}
            <div style={styles.varTable}>
              <div style={styles.varTableTitle}>变量解析说明</div>
              {Object.entries(page.variables).map(([k, v]) => (
                <div key={k} style={styles.varRow}>
                  <code style={styles.varKey}>{k}</code>
                  <span style={styles.varArrow}>→</span>
                  <strong>{v}</strong>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 版本历史 */}
        <div style={{ marginTop: "1rem" }}>
          <h3 style={styles.sectionTitle}>版本历史</h3>
          <div style={styles.versionTimeline}>
            {versions.map((v) => (
              <div key={v.version} style={styles.versionRow}>
                <span
                  style={
                    v.version === page.version
                      ? styles.versionBadgeCurrent
                      : styles.versionBadgeOld
                  }
                >
                  v{v.version}
                </span>
                <span style={{ flex: 1, fontSize: "0.75rem" }}>{v.message}</span>
                <span style={styles.versionMeta}>{v.author} · {v.timestamp.slice(0, 10)}</span>
                {v.version === page.version && (
                  <span style={styles.currentTag}>当前</span>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </S2Chrome>
  );
}

/* ────────────── Styles ────────────── */

const styles: Record<string, React.CSSProperties> = {
  topbar: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0.5rem 0",
    borderBottom: "1px solid var(--aos-border)",
    marginBottom: "0.5rem",
  },
  topbarLeft: { display: "flex", alignItems: "center", gap: "0.5rem" },
  versionBadge: {
    padding: "2px 8px",
    borderRadius: "4px",
    background: "var(--aos-accent-light)",
    color: "var(--aos-accent)",
    fontSize: "0.7rem",
    fontWeight: 600,
  },
  modeSwitcher: { display: "flex", gap: "2px", borderRadius: "2px", overflow: "hidden", border: "1px solid var(--aos-border)" },
  modeBtn: {
    padding: "4px 12px",
    fontSize: "0.75rem",
    border: "none",
    background: "var(--aos-surface)",
    color: "var(--aos-text-secondary)",
    cursor: "pointer",
  },
  modeBtnActive: {
    padding: "4px 12px",
    fontSize: "0.75rem",
    border: "none",
    background: "var(--aos-accent)",
    color: "var(--text-on-brand)",
    fontWeight: 600,
    cursor: "pointer",
  },
  slateBody: { display: "flex", gap: "0.5rem", height: "70vh", minHeight: 400 },
  treePanel: {
    width: 200,
    borderRight: "1px solid var(--aos-border)",
    padding: "0.5rem",
    overflowY: "auto",
    background: "var(--aos-surface)",
  },
  treeSearch: {
    width: "100%",
    padding: "4px 8px",
    borderRadius: "4px",
    border: "1px solid var(--aos-border)",
    fontSize: "0.75rem",
    marginBottom: "0.5rem",
    background: "var(--aos-surface)",
    color: "var(--aos-text)",
  },
  treeSectionTitle: { fontSize: "0.65rem", fontWeight: 600, color: "var(--aos-text-tertiary)", textTransform: "uppercase", letterSpacing: "0.5px", margin: "0.5rem 0 0.25rem" },
  treeItem: { display: "flex", alignItems: "center", gap: "4px", padding: "3px 6px", borderRadius: "3px", cursor: "pointer", fontSize: "0.72rem" },
  treeItemActive: { display: "flex", alignItems: "center", gap: "4px", padding: "3px 6px", borderRadius: "3px", cursor: "pointer", fontSize: "0.72rem", background: "var(--aos-accent-light)" },
  kindDot: { width: 8, height: 8, borderRadius: "50%", background: "var(--aos-accent)", flexShrink: 0 },
  treeItemName: { flex: 1, color: "var(--aos-text)" },
  treeItemId: { fontSize: "0.6rem", color: "var(--aos-text-tertiary)" },
  addWidgetRow: { display: "flex", flexWrap: "wrap", gap: "2px", marginTop: "0.5rem" },
  addWidgetBtn: { padding: "2px 6px", fontSize: "0.65rem", border: "1px solid var(--aos-border)", borderRadius: "3px", background: "var(--aos-surface)", color: "var(--aos-text-secondary)", cursor: "pointer" },
  deleteBtn: { marginTop: "0.5rem", padding: "4px 8px", fontSize: "0.7rem", border: "1px solid var(--aos-red-border)", borderRadius: "4px", background: "var(--aos-red-bg)", color: "var(--aos-red)", cursor: "pointer", width: "100%" },
  canvas: { flex: 1, overflowY: "auto", padding: "0.75rem" },
  emptyCanvas: { display: "flex", alignItems: "center", justifyContent: "center", height: "100%" },
  widgetCard: { border: "1px solid var(--aos-border)", borderRadius: "2px", overflow: "hidden", background: "var(--aos-surface)" },
  widgetHeader: { display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.5rem 0.75rem", borderBottom: "1px solid var(--aos-border)", background: "var(--aos-surface-hover)" },
  kindBadge: { padding: "2px 6px", borderRadius: "3px", background: "var(--aos-accent-light)", color: "var(--aos-accent)", fontSize: "0.65rem", fontWeight: 600 },
  widgetName: { fontWeight: 600, fontSize: "0.8rem", color: "var(--aos-text)" },
  widgetBody: { padding: "0.75rem" },
  textArea: { width: "100%", minHeight: 150, padding: "0.5rem", border: "1px solid var(--aos-border)", borderRadius: "4px", fontFamily: "ui-monospace, monospace", fontSize: "0.75rem", background: "var(--aos-surface)", color: "var(--aos-text)" },
  objectSetInput: { width: "100%", fontFamily: "ui-monospace, monospace", fontSize: "0.75rem" },
  mutedText: { fontSize: "0.75rem", color: "var(--aos-text-tertiary)" },
  propsPanel: { width: 260, borderLeft: "1px solid var(--aos-border)", overflowY: "auto", background: "var(--aos-surface)" },
  propsHeader: { padding: "0.5rem 0.75rem", borderBottom: "1px solid var(--aos-border)", fontWeight: 600, fontSize: "0.8rem", color: "var(--aos-text)" },
  propLabel: { display: "block", fontSize: "0.65rem", fontWeight: 500, color: "var(--aos-text-secondary)", marginBottom: "2px", marginTop: "0.5rem" },
  propInput: { width: "100%", fontSize: "0.75rem" },
  contentToggle: { display: "flex", gap: "2px", marginBottom: "4px" },
  contentToggleActive: { padding: "2px 8px", fontSize: "0.65rem", border: "1px solid var(--aos-accent)", borderRadius: "3px", background: "var(--aos-accent)", color: "var(--text-on-brand)" },
  contentToggleBtn: { padding: "2px 8px", fontSize: "0.65rem", border: "1px solid var(--aos-border)", borderRadius: "3px", background: "var(--aos-surface)", color: "var(--aos-text-secondary)" },
  codeBlock: { width: "100%", minHeight: 80, padding: "4px 6px", border: "1px solid var(--aos-border)", borderRadius: "4px", fontFamily: "ui-monospace, monospace", fontSize: "0.65rem", background: "var(--aos-surface-hover)", color: "var(--aos-text-secondary)" },
  summaryBox: { margin: "0.75rem", padding: "0.5rem", border: "1px solid var(--aos-border)", borderRadius: "4px" },
  summaryTitle: { fontSize: "0.65rem", fontWeight: 600, color: "var(--aos-text-tertiary)", textTransform: "uppercase", marginBottom: "4px" },
  summaryRow: { display: "flex", justifyContent: "space-between", fontSize: "0.7rem", padding: "1px 0", color: "var(--aos-text-secondary)" },
  workflowPanel: { padding: "0.5rem" },
  workflowBody: { display: "flex", height: "60vh", minHeight: 360, gap: "0.5rem", marginTop: "0.5rem" },
  wfLeftPanel: { width: 200, borderRight: "1px solid var(--aos-border)", padding: "0.5rem", overflowY: "auto", background: "var(--aos-surface)" },
  wfSectionTitle: { fontSize: "0.65rem", fontWeight: 600, color: "var(--aos-text-secondary)", textTransform: "uppercase", letterSpacing: "0.5px", margin: "0.5rem 0 0.25rem" },
  wfNodeTemplate: { display: "flex", alignItems: "center", gap: "4px", padding: "4px 8px", borderRadius: "4px", marginBottom: "3px", cursor: "grab", fontSize: "0.7rem", border: "1px solid", background: "var(--aos-surface)" },
  wfNodeDot: { width: 8, height: 8, borderRadius: "50%", flexShrink: 0 },
  wfCanvas: { flex: 1, background: "var(--aos-surface-hover)", backgroundImage: "radial-gradient(var(--aos-border) 1px, transparent 1px)", backgroundSize: "20px 20px", padding: "1rem" },
  wfRightPanel: { width: 260, borderLeft: "1px solid var(--aos-border)", padding: "0.5rem", background: "var(--aos-surface)" },
  runtimePanel: { padding: "0.5rem" },
  resolvedBox: { padding: "1rem", border: "1px solid var(--aos-border)", borderRadius: "2px", background: "var(--aos-surface)", marginBottom: "0.75rem" },
  resolvedContent: { fontFamily: "ui-monospace, monospace", fontSize: "0.75rem", lineHeight: 1.6, color: "var(--aos-text)" },
  varTable: { padding: "0.75rem", border: "1px solid var(--aos-accent-border)", borderRadius: "2px", background: "var(--aos-accent-light)" },
  varTableTitle: { fontSize: "0.75rem", fontWeight: 600, color: "var(--aos-accent-hover)", marginBottom: "0.5rem" },
  varRow: { display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.7rem", padding: "2px 0" },
  varKey: { color: "var(--aos-purple-600)", fontWeight: 600 },
  varArrow: { color: "var(--aos-text-secondary)" },
  sectionTitle: { fontSize: "0.85rem", fontWeight: 600, color: "var(--aos-text)", marginBottom: "0.5rem" },
  versionTimeline: { border: "1px solid var(--aos-border)", borderRadius: "2px", background: "var(--aos-surface)" },
  versionRow: { display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.4rem 0.75rem", borderBottom: "1px solid var(--aos-border)" },
  versionBadgeCurrent: { padding: "1px 6px", borderRadius: "3px", background: "var(--aos-accent-light)", color: "var(--aos-accent)", fontSize: "0.6rem", fontWeight: 600, width: 28, textAlign: "center" as const },
  versionBadgeOld: { padding: "1px 6px", borderRadius: "3px", background: "var(--aos-gray-100)", color: "var(--aos-text-secondary)", fontSize: "0.6rem", fontWeight: 600, width: 28, textAlign: "center" as const },
  versionMeta: { fontSize: "0.6rem", color: "var(--aos-text-tertiary)" },
  currentTag: { fontSize: "0.6rem", color: "var(--aos-accent)", fontWeight: 600 },
};
