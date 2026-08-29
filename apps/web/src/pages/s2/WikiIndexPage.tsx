/**
 * Phase E-13 · Wiki 索引页
 * 左侧知识空间 + 右侧页面卡片 + 搜索。知识发布走 Draft；不把旧 meta_branch 当作组织定制真源。
 */
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { apiGet } from "../../api/client";
import { S2Chrome, useJsonGet } from "./shared";

type ObjectTypeItem = { id: string; name: string; kind: string; snippet?: string; instances?: { id: string; kind?: string }[] };
type OntologyRail = {
  objectTypes?: ObjectTypeItem[];
};

export function summarizeWikiCoverage(cards: { covered: boolean }[]): { covered: number; gaps: number; total: number } {
  const covered = cards.filter((card) => card.covered).length;
  return { covered, gaps: cards.length - covered, total: cards.length };
}

export function WikiIndexPage() {
  const rail = useJsonGet<OntologyRail>("/v1/analytics/ontology-rail");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [wikiCards, setWikiCards] = useState<{ type: string; id: string; displayLabel: string; sourceRecordLabel: string; summary: string; covered: boolean; versionCount: number; lastUpdatedAt?: string | null }[]>([]);
  const [loadingCards, setLoadingCards] = useState(false);
  const [cardErr, setCardErr] = useState<string | null>(null);

  const types = rail.data?.objectTypes ?? [];

  // 根据选中的 ObjectType 加载 Wiki 卡片
  async function loadWikiCards(typeId: string) {
    setLoadingCards(true);
    setSelectedType(typeId);
    setCardErr(null);
    try {
      const coverage = await apiGet<{
        items: { objectType: string; objectId: string; displayLabel?: string; sourceRecordLabel?: string; summary: string; covered: boolean; versionCount: number; lastUpdatedAt?: string | null }[];
      }>(`/v1/wiki/${encodeURIComponent(typeId)}/coverage-index?limit=200`);
      setWikiCards((coverage.items || []).map((item) => ({
        type: item.objectType,
        id: item.objectId,
        displayLabel: item.displayLabel || item.objectId,
        sourceRecordLabel: item.sourceRecordLabel || item.objectId,
        summary: item.summary,
        covered: item.covered,
        versionCount: item.versionCount,
        lastUpdatedAt: item.lastUpdatedAt,
      })));
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
      (c) => c.id.toLowerCase().includes(q) || c.type.toLowerCase().includes(q) || c.displayLabel.toLowerCase().includes(q) || c.summary.toLowerCase().includes(q),
    );
  }, [wikiCards, searchQuery]);

  const filteredTypes = useMemo(() => {
    if (!searchQuery.trim()) return types;
    const q = searchQuery.toLowerCase();
    return types.filter((t) => t.id.toLowerCase().includes(q) || (t.name && t.name.toLowerCase().includes(q)));
  }, [types, searchQuery]);
  const coverage = summarizeWikiCoverage(wikiCards);
  const selectedTypeName = types.find((item) => item.id === selectedType)?.name || "业务对象";

  return (
    <S2Chrome title="知识索引" lede="组织知识空间 · 业务对象知识卡 · 覆盖与缺口搜索">
      <div className="wiki-index-layout">
        {/* 左侧知识空间 */}
        <aside
          style={{
            border: "1px solid var(--aos-border)",
            padding: "0.75rem",
            minHeight: 400,
          }}
        >
          <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: 0 }}>
            知识空间
          </h2>
          <div className="bp-banner bp-banner-info" style={{ fontSize: "0.75rem" }}>
            栖月汇商贸有限公司 · 默认工作区<br />生产知识空间<br />编辑统一提交草稿审批，审批通过后才进入生产知识。
          </div>

          <h2 className="aos-text" style={{ fontSize: "0.875rem", marginTop: 16 }}>
            业务对象类型
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
              placeholder="搜索业务对象、摘要或审计标识…"
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
              onClick={() => { rail.reload(); if (selectedType) void loadWikiCards(selectedType); }}
            >
              刷新
            </button>
          </div>

          {cardErr && <p className="error">{cardErr}</p>}
          {loadingCards && <p className="muted">加载知识卡片中…</p>}

          {!loadingCards && !cardErr && filteredCards.length === 0 && (
            <p className="muted">
              请从左侧选择一个业务对象类型，加载其下全部知识卡片。
            </p>
          )}

          {filteredCards.length > 0 && (
            <>
              <p className="muted" style={{ fontSize: "0.75rem", marginBottom: 8 }}>
                主体 {filteredCards.length} · 已覆盖 {coverage.covered} · 知识缺口 {coverage.gaps}
                · 生产知识空间
              </p>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))",
                  gap: 12,
                }}
              >
                {filteredCards.map((card) => (
                  <article
                    key={`${card.type}/${card.id}`}
                    style={{
                      display: "block",
                      padding: "0.75rem",
                      border: "1px solid var(--aos-border)",
                      borderRadius: 2,
                      background: "var(--aos-surface)",
                    }}
                    className="bp-wiki-card"
                  >
                    <Link
                      to={`/ontology/wiki?type=${encodeURIComponent(card.type)}&id=${encodeURIComponent(card.id)}`}
                      style={{ display: "block", textDecoration: "none", color: "inherit" }}
                    >
                      <div style={{ fontSize: "0.7rem", opacity: 0.6, marginBottom: 4 }}>
                        {selectedTypeName} · {card.covered ? `已有知识 · ${card.versionCount} 个历史版本` : "知识缺口"}
                      </div>
                      <div style={{ fontSize: "0.9rem", fontWeight: 600, marginBottom: 4 }}>
                        {card.displayLabel}
                      </div>
                      {card.summary && (
                        <div style={{ fontSize: "0.75rem", opacity: 0.7, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {card.summary}
                        </div>
                      )}
                      <div style={{ fontSize: "0.7rem", marginTop: 8, color: "var(--aos-indigo-600)" }}>
                        {card.covered ? "查看知识卡片 →" : "为该业务对象补充知识 →"}
                      </div>
                      {card.lastUpdatedAt && <div style={{ fontSize: "0.68rem", marginTop: 4, opacity: 0.55 }}>最近更新 {card.lastUpdatedAt}</div>}
                    </Link>
                    <details className="bp-audit-details" style={{ marginTop: 6 }}>
                      <summary>来源审计</summary>
                      <div style={{ fontSize: "0.7rem", opacity: 0.65 }}>对象类型：{card.type} · 对象标识：{card.id}</div>
                      <div style={{ fontSize: "0.7rem", opacity: 0.65 }}>{card.sourceRecordLabel}</div>
                    </details>
                  </article>
                ))}
              </div>
            </>
          )}
        </main>
      </div>
    </S2Chrome>
  );
}
