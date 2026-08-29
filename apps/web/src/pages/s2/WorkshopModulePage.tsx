import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { PageChrome } from "../../components/PageChrome";
import { apiGet, apiPost, apiDelete } from "../../api/client";

interface Module {
  id: string;
  name: string;
  description?: string;
  category?: string;
  status: string;
  createdAt?: string;
  updatedAt?: string;
  widgets?: unknown[];
}

export function WorkshopModulePage() {
  const navigate = useNavigate();
  const [modules, setModules] = useState<Module[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState("all");
  const [publishConfirm, setPublishConfirm] = useState<string | null>(null);

  useEffect(() => {
    loadModules();
  }, []);

  async function loadModules() {
    setLoading(true);
    setError(null);
    try {
      const data = await apiGet<{ items: Module[] }>("/v1/modules");
      setModules(data.items || []);
    } catch (e) {
      setError(String((e as Error).message || e));
    } finally {
      setLoading(false);
    }
  }

  async function deleteModule(id: string) {
    if (!confirm("确定要删除此模块吗？")) return;
    try {
      await apiDelete(`/v1/modules/${encodeURIComponent(id)}`);
      loadModules();
    } catch (e) {
      setError(String((e as Error).message || e));
    }
  }

  async function publishModule(id: string) {
    try {
      await apiPost(`/v1/modules/${encodeURIComponent(id)}/publish`, {});
      setPublishConfirm(null);
      await loadModules();
    } catch (e) {
      setError(String((e as Error).message || e));
    }
  }

  const filteredModules = modules.filter((m) => {
    if (filterType !== "all" && m.category !== filterType) return false;
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return m.name.toLowerCase().includes(q) || (m.description && m.description.toLowerCase().includes(q));
  });
  const categories = Array.from(new Set(modules.map((item) => item.category).filter(Boolean))) as string[];

  return (
    <PageChrome title="应用管理" lede="管理当前工作区的自建应用、编辑状态与发布流程">
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 16, flexWrap: "wrap" }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--aos-text)" }}>
          应用列表（{filteredModules.length}）
        </span>
        <button
          onClick={() => navigate("/workshop/create")}
          style={{ padding: "6px 14px", fontSize: 12, fontWeight: 600, border: "none", borderRadius: 2, background: "var(--aos-accent)", color: "var(--text-on-brand)", cursor: "pointer" }}
        >
          + 新建应用
        </button>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <div style={{ position: "relative" }}>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜索应用…"
              aria-label="搜索应用"
              style={{ padding: "6px 32px 6px 10px", fontSize: 12, border: "1px solid var(--aos-border-strong)", borderRadius: 4, width: 200 }}
            />
            <svg style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", width: 14, height: 14, color: "var(--aos-faint)" }} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <path d="m21 21-4.3-4.3" />
            </svg>
          </div>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            style={{ padding: "6px 8px", fontSize: 12, border: "1px solid var(--aos-border-strong)", borderRadius: 4 }}
          >
            <option value="all">全部类型</option>
            {categories.map((category) => <option key={category} value={category}>{category}</option>)}
          </select>
        </div>
      </div>

      {error && (
        <div style={{ background: "var(--aos-red-bg)", color: "var(--aos-red)", padding: "8px 12px", borderRadius: 2, marginBottom: 12, fontSize: 13 }}>
          {error}
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: "center", padding: 24, color: "var(--aos-faint)" }}>加载中...</div>
      ) : filteredModules.length === 0 ? (
        <div style={{ textAlign: "center", padding: 24, color: "var(--aos-faint)" }}>当前工作区暂无自建应用，可从“新建应用”开始创建。</div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 12 }}>
          {filteredModules.map((m) => (
            <div
              key={m.id}
              style={{ background: "var(--aos-surface)", borderRadius: 2, border: "1px solid var(--aos-border)", padding: 16, transition: "box-shadow 0.15s" }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start", marginBottom: 8 }}>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 600, color: "var(--aos-text)" }}>{m.name}</div>
                  <span style={{ fontSize: 10, padding: "1px 6px", borderRadius: 3, background: "var(--aos-accent-light)", color: "var(--aos-accent)" }}>
                    {m.category || "未分类"}
                  </span>
                </div>
                <span style={{
                  fontSize: 10, fontWeight: 500, padding: "2px 6px", borderRadius: 3,
                  background: m.status === "published" ? "var(--aos-green-bg)" : m.status === "draft" ? "var(--aos-amber-bg)" : "var(--aos-red-bg)",
                  color: m.status === "published" ? "var(--aos-green-600)" : m.status === "draft" ? "var(--aos-amber-600)" : "var(--aos-red)",
                }}>
                  {m.status === "published" ? "已发布" : m.status === "draft" ? "草稿" : "已禁用"}
                </span>
              </div>
              {m.description && (
                <p style={{ fontSize: 12, color: "var(--aos-text-secondary)", margin: "0 0 12px" }}>{m.description}</p>
              )}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, fontSize: 11, marginBottom: 12 }}>
                <div>
                  <div style={{ color: "var(--aos-faint)" }}>组件数</div>
                  <div style={{ fontWeight: 600, color: "var(--aos-text)" }}>{Array.isArray(m.widgets) ? m.widgets.length : "未读取"}</div>
                </div>
                <div>
                  <div style={{ color: "var(--aos-faint)" }}>事件数</div>
                  <div style={{ fontWeight: 600, color: "var(--aos-text)" }}>未读取</div>
                </div>
                <div>
                  <div style={{ color: "var(--aos-faint)" }}>更新时间</div>
                  <div style={{ fontWeight: 600, color: "var(--aos-text)", fontSize: 10 }}>{m.updatedAt?.slice(0, 10) || "未读取"}</div>
                </div>
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <button
                  onClick={() => navigate(`/workshop/canvas?module=${m.id}`)}
                  style={{ flex: 1, padding: "5px 8px", fontSize: 11, borderRadius: 4, border: "1px solid var(--aos-accent)", background: "var(--aos-surface)", color: "var(--aos-accent)", cursor: "pointer" }}
                >
                  编辑
                </button>
                {m.status !== "published" && publishConfirm !== m.id && (
                  <button
                    onClick={() => setPublishConfirm(m.id)}
                    style={{ flex: 1, padding: "5px 8px", fontSize: 11, borderRadius: 4, border: "none", background: "var(--aos-green)", color: "var(--text-on-brand)", cursor: "pointer" }}
                  >
                    发布
                  </button>
                )}
                {m.status !== "published" && publishConfirm === m.id && (<>
                  <button className="btn-primary" onClick={() => void publishModule(m.id)}>确认发布</button>
                  <button className="btn" onClick={() => setPublishConfirm(null)}>取消</button>
                </>)}
                <button
                  onClick={() => deleteModule(m.id)}
                  style={{ flex: 1, padding: "5px 8px", fontSize: 11, borderRadius: 4, border: "1px solid var(--aos-red)", background: "var(--aos-surface)", color: "var(--aos-red)", cursor: "pointer" }}
                >
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </PageChrome>
  );
}
