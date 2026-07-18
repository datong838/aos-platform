import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";
import { BpHeroLink, BpLinkRow, BpToolbar } from "./s2/blueprintUi";

type ModuleItem = {
  id: string;
  name: string;
  status: string;
  description?: string;
  entryPath?: string;
  objectType?: string;
  buddyBound?: boolean;
};

/** 85 · 对齐 workshop.html · Module 卡片 grid */
export function WorkshopListPage() {
  const [items, setItems] = useState<ModuleItem[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [filter, setFilter] = useState("全部");

  useEffect(() => {
    apiGet<{ items: ModuleItem[] }>("/v1/modules")
      .then((j) => setItems(j.items))
      .catch((e) => setErr(String(e.message || e)));
  }, []);

  async function createDemo() {
    setErr(null);
    try {
      await apiPost("/v1/modules", {
        name: `场景模块 ${items.length + 1}`,
        description: "从应用列表创建",
        objectType: "WorkOrder",
        entryPath: "/workshop/inbox",
        widgets: ["table", "filters"],
        buddyBound: true,
      });
      const j = await apiGet<{ items: ModuleItem[] }>("/v1/modules");
      setItems(j.items);
    } catch (e) {
      setErr(String((e as Error).message || e));
    }
  }

  const filtered = items.filter((m) => {
    if (filter === "全部") return true;
    if (filter === "知识图谱") return (m.entryPath || "").includes("graph");
    if (filter === "电商") return m.objectType === "WorkOrder";
    return true;
  });

  return (
    <PageChrome title="工作台 · 应用列表" lede="业务人员从这里打开 Module · 运营台/图谱都是列表条目">
      <BpToolbar>
        <button type="button" className="btn" onClick={() => void createDemo()}>
          + 新建 Module
        </button>
        <Link to="/workshop/canvas" className="muted">
          画布编辑 →
        </Link>
        <Link to="/workshop/inbox" className="muted">
          运营台 →
        </Link>
      </BpToolbar>

      <BpHeroLink
        to="/workshop/inbox"
        eyebrow="推荐打开"
        title="运营 Inbox Module"
        desc="Filter · Table · Object View · 变量条 · 从 Inbox 可带 Selection 进 Buddy"
        cta="进入运营台 →"
        accent="sky"
      />

      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: "1rem" }}>
        {["全部", "电商", "知识图谱", "供应链"].map((f) => (
          <button
            key={f}
            type="button"
            className={filter === f ? "bp-tag bp-tag-ok" : "bp-tag"}
            onClick={() => setFilter(f)}
          >
            {f}
          </button>
        ))}
      </div>

      {err && <p className="error">{err}</p>}

      <div className="bp-discover-grid">
        {filtered.map((m, i) => {
          const path = m.entryPath || "/workshop/inbox";
          const isGraph = path.includes("graph");
          return (
            <Link
              key={m.id}
              to={path}
              className={`bp-discover-card bp-discover-${isGraph ? "violet" : i % 2 === 0 ? "violet" : "muted"}`}
              style={{ textDecoration: "none" }}
            >
              <div className="bp-discover-head">
                <span className="bp-discover-title">{m.name}</span>
                <span className={`bp-tag ${m.status === "published" ? "bp-tag-ok" : "bp-tag-warn"}`}>
                  {m.status === "published" ? "已发布" : m.status || "草稿"}
                </span>
              </div>
              <p className="bp-discover-meta">
                {m.objectType || "Module"} · {m.description || "—"}
              </p>
              <p className="muted" style={{ fontSize: "0.7rem" }}>
                entry={path}
                {m.buddyBound ? " · Buddy" : ""}
              </p>
              <span className="bp-discover-cta">打开 Module →</span>
            </Link>
          );
        })}
        {filtered.length === 0 && <p className="muted">暂无 Module · 点「新建 Module」</p>}
      </div>

      <BpLinkRow
        links={[
          { to: "/workshop/module-interface", label: "模块接口" },
          { to: "/workshop/buddy", label: "Buddy" },
          { to: "/workshop/graph", label: "知识图谱" },
        ]}
      />
    </PageChrome>
  );
}
