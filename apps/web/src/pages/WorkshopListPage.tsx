import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
import { PageChrome } from "../components/PageChrome";

type ModuleItem = {
  id: string;
  name: string;
  status: string;
  description?: string;
  entryPath?: string;
  objectType?: string;
  buddyBound?: boolean;
};

export function WorkshopListPage() {
  const [items, setItems] = useState<ModuleItem[]>([]);
  const [err, setErr] = useState<string | null>(null);

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

  return (
    <PageChrome title="应用列表" lede="工作台唯一入口 · Module.entryPath 绑定 · 对齐 workshop.html">
      <button type="button" className="btn" onClick={() => void createDemo()}>
        新建 Module
      </button>
      <p className="muted">
        接口详情 · <Link to="/workshop/module-interface">模块接口</Link>
      </p>
      {err && <p className="error">{err}</p>}
      <ul className="card-list">
        {items.map((m) => {
          const path = m.entryPath || "/workshop/inbox";
          return (
            <li key={m.id} className="card">
              <strong className="aos-text">{m.name}</strong>
              <span className="muted">
                {" "}
                · {m.status} · {m.objectType || "—"}
              </span>
              <p className="muted" style={{ margin: "0.35rem 0" }}>
                {m.description || ""} · entry=<code>{path}</code>
                {m.buddyBound ? " · Buddy" : ""}
              </p>
              <div>
                <Link to={path}>打开 Module</Link>
                {" · "}
                <Link to="/workshop/buddy">Buddy</Link>
                {" · "}
                <Link to="/workshop/graph">知识图谱</Link>
              </div>
            </li>
          );
        })}
      </ul>
    </PageChrome>
  );
}
