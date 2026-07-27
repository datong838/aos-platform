/**
 * Phase E-13 · Wiki 索引页
 * 左侧分支树 + 右侧页面卡片 + 搜索 · 对接 /v1/ontology/branches + /v1/analytics/ontology-rail
 */
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet } from "../../api/client";
import { S2Chrome, useJsonGet } from "./shared";

type Branch = { id: string; name: string; baseRef: string; readonly: boolean; changeCount?: number };
type ObjectTypeItem = { id: string; name: string; kind: string; snippet?: string; instances?: { id: string; kind?: string }[] };
type OntologyRail = {
  objectTypes?: ObjectTypeItem[];
};

export function WikiIndexPage() {
  const branches = useJsonGet<{ items: Branch[] }>("/v1/ontology/branches");
  const rail = useJsonGet<OntologyRail>("/v1/analytics/ontology-rail");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedBranch, setSelectedBranch] = useState<string | null>(null);
  const [wikiCards, setWikiCards] = useState<{ type: string; id: string; summary: string }[]>([]);
  const [loadingCards, setLoadingCards] = useState(false);
  const [cardErr, setCardErr] = useState<string | null>(null);

  const types = rail.data?.objectTypes ?? [];
  const branchItems = branches.data?.items ?? [];

  // 根据选中的 ObjectType 加载 Wiki 卡片
  async function loadWikiCards(typeId: string) {
    setLoadingCards(true);
    setCardErr(null);
    try {
      // 尝试获取该类型下所有对象的 Wiki 卡片
      const res = await apiGet<{ items: { id: string; summary?: string }[] }>(
        `/v1/analytics/objects/list?objectType=${encodeURIComponent(typeId)}&limit=50`,
      );
      const cards = (res.items || []).map((item) => ({
        type: typeId,
        id: item.id,
        summary: item.summary || "",
      }));
      setWikiCards(cards);
    } catch (e) {
      setCardErr(e instanceof Error ? e.message : String(e));
      setWikiCards([]);
    } finally {
      setLoadingCards(false);
    }
  }

  // 搜索过滤
  const filteredCards = useMemo(() => {
    if (!searchQuery.trim()) return wikiCards;
    const q = searchQuery.toLowerCase();
    return wikiCards.filter(
      (c) => c.id.toLowerCase().includes(q) || c.type.toLowerCase().includes(q) || c.summary.toLowerCase().includes(q),
    );
  }, [wikiCards, searchQuery]);

  const filteredTypes = useMemo(() => {
    if (!searchQuery.trim()) return types;
    const q = searchQuery.toLowerCase();
    return types.filter((t) => t.id.toLowerCase().includes(q) || (t.name && t.name.toLowerCase().includes(q)));
  }, [types, searchQuery]);

  return (
    <S2Chrome title="Wiki 索引" lede="活知识 Wiki 索引 · 分支树 + 类型卡片 + 搜索">
      <div style={{ display: "grid", gridTemplateColumns: "minmax(200px, 260px) 1fr", gap: "1rem", marginTop: 12 }}>
        {/* 左侧分支树 */}
        <aside
          style={{
            border: "1px solid var(--aos-border)",
            padding: "0.75rem",
            minHeight: 400,
          }}
        >
          <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: 0 }}>
            分支
          </h2>
          {branches.err && <p className="error">{branches.err}</p>}
          <ul style={{ listStyle: "none", padding: 0, margin: "0.5rem 0 0" }}>
            {branchItems.map((b) => (
              <li key={b.id} style={{ marginBottom: 6 }}>
                <button
                  type="button"
                  className={`btn-nav${selectedBranch === b.id ? " is-active" : ""}`}
                  style={{
                    fontSize: "0.75rem",
                    width: "100%",
                    textAlign: "left",
                    background: selectedBranch === b.id ? "var(--aos-accent)" : undefined,
                    color: selectedBranch === b.id ? "var(--text-on-brand)" : undefined,
                  }}
                  onClick={() => setSelectedBranch(b.id)}
                >
                  {b.readonly ? "🔒 " : "🌿 "}
                  {b.id}
                  {b.changeCount ? ` (${b.changeCount})` : ""}
                </button>
              </li>
            ))}
            {branchItems.length === 0 && (
              <li className="muted" style={{ fontSize: "0.75rem" }}>暂无分支</li>
            )}
          </ul>

          <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: 16 }}>
            Object 类型
          </h2>
          <ul style={{ listStyle: "none", padding: 0, margin: "0.5rem 0 0" }}>
            {filteredTypes.map((t) => (
              <li key={t.id} style={{ marginBottom: 4 }}>
                <button
                  type="button"
                  className="btn-nav"
                  style={{ fontSize: "0.75rem", width: "100%", textAlign: "left" }}
                  onClick={() => void loadWikiCards(t.id)}
                >
                  {t.name || t.id}
                </button>
              </li>
            ))}
            {filteredTypes.length === 0 && (
              <li className="muted" style={{ fontSize: "0.75rem" }}>无匹配类型</li>
            )}
          </ul>
        </aside>

        {/* 右侧卡片区域 */}
        <main>
          <div style={{ display: "flex", gap: 8, marginBottom: 12, alignItems: "center" }}>
            <input
              type="search"
              placeholder="搜索 objectType / objectId / 摘要…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                flex: 1,
                padding: "6px 12px",
                fontSize: "0.85rem",
                background: "var(--aos-surface)",
                color: "inherit",
                border: "1px solid var(--aos-border)",
                borderRadius: 4,
              }}
            />
            <button
              type="button"
              className="btn"
              onClick={() => { branches.reload(); rail.reload(); }}
            >
              刷新
            </button>
          </div>

          {cardErr && <p className="error">{cardErr}</p>}
          {loadingCards && <p className="muted">加载 Wiki 卡片中…</p>}

          {!loadingCards && !cardErr && filteredCards.length === 0 && (
            <p className="muted">
              请从左侧选择一个 Object 类型，加载其下所有 Wiki 知识卡片。
            </p>
          )}

          {filteredCards.length > 0 && (
            <>
              <p className="muted" style={{ fontSize: "0.75rem", marginBottom: 8 }}>
                共 {filteredCards.length} 张 Wiki 卡片
                {selectedBranch ? ` · 分支: ${selectedBranch}` : " · 默认分支"}
              </p>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
                  gap: 12,
                }}
              >
                {filteredCards.map((card) => (
                  <Link
                    key={`${card.type}/${card.id}`}
                    to={`/ontology/wiki?type=${encodeURIComponent(card.type)}&id=${encodeURIComponent(card.id)}`}
                    style={{
                      display: "block",
                      padding: "0.75rem",
                      border: "1px solid var(--aos-border)",
                      borderRadius: 2,
                      textDecoration: "none",
                      background: "var(--aos-surface)",
                    }}
                    className="bp-wiki-card"
                  >
                    <div style={{ fontSize: "0.7rem", opacity: 0.6, marginBottom: 4 }}>
                      {card.type}
                    </div>
                    <div style={{ fontSize: "0.9rem", fontWeight: 600, marginBottom: 4 }}>
                      {card.id}
                    </div>
                    {card.summary && (
                      <div style={{ fontSize: "0.75rem", opacity: 0.7, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {card.summary}
                      </div>
                    )}
                    <div style={{ fontSize: "0.7rem", marginTop: 8, color: "var(--aos-accent)" }}>
                      查看知识卡片 →
                    </div>
                  </Link>
                ))}
              </div>
            </>
          )}
        </main>
      </div>
    </S2Chrome>
  );
}
