/**
 * Phase C+ — Product & Inventory Workshop (W02 最小版)
 * Aligns with FR-D1.5-9 / AC-D1.5-6
 *
 * Widgets (数据展示层 · 无决策标签):
 *   - 商品/SKU 列表  (P02 Product / P03 ProductSku)
 *   - 低库存队列     (P03 ProductSku WHERE stock_health=low)
 *   - 分类树         (P04 Category · 按 parent_id 嵌套)
 *   - 质量告警       (P02 Product WHERE quality_score < 0.8)
 *
 * 约束：W02 最小版仅做数据展示，不调用 L01 决策标签（pass/block/needs_review 不渲染）。
 */
import { useEffect, useMemo, useState } from "react";
import { PageChrome } from "../../components/PageChrome";
import { apiGet } from "../../api/client";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface ProductObject {
  id: string;
  type?: string;
  title?: string;
  product_id?: string;
  category_id?: string;
  quality_score?: number | null;
  [key: string]: unknown;
}

export interface ProductSkuObject {
  id: string;
  type?: string;
  sku_no?: string;
  product_id?: string;
  stock_health?: string;
  [key: string]: unknown;
}

export interface CategoryObject {
  id: string;
  type?: string;
  name?: string;
  parent_id?: string;
  [key: string]: unknown;
}

export interface CategoryTreeNode extends CategoryObject {
  children: CategoryTreeNode[];
}

export interface ProductSkuView {
  product: ProductObject;
  skuCount: number;
}

// ── 纯函数（导出供测试） ───────────────────────────────────────────────────────

/** FR-D1.5-9 W02 低库存队列 · 过滤 stock_health === "low"（严格相等，大小写敏感）。 */
export function filterLowStockSkus(skus: ProductSkuObject[]): ProductSkuObject[] {
  return skus.filter((s) => s.stock_health === "low");
}

/** FR-D1.5-9 W02 质量告警 · 过滤 quality_score < 0.8（null 安全降级，严格小于）。 */
export function filterLowQualityProducts(products: ProductObject[]): ProductObject[] {
  return products.filter((p) => p.quality_score != null && p.quality_score < 0.8);
}

/** FR-D1.5-9 W02 分类树 · 按 parent_id 构造嵌套树（parent_id 为空/缺失视为根）。 */
export function buildCategoryTree(categories: CategoryObject[]): CategoryTreeNode[] {
  const nodeMap = new Map<string, CategoryTreeNode>();
  for (const c of categories) {
    nodeMap.set(c.id, { ...c, children: [] });
  }
  const roots: CategoryTreeNode[] = [];
  for (const c of categories) {
    const node = nodeMap.get(c.id);
    if (!node) continue;
    const pid = c.parent_id;
    const parent = pid ? nodeMap.get(pid) : undefined;
    if (parent) {
      parent.children.push(node);
    } else {
      roots.push(node);
    }
  }
  return roots;
}

/** FR-D1.5-9 W02 商品/SKU 列表 · 聚合每个商品的 SKU 数（product_id 关联）。 */
export function mergeProductSkuView(
  products: ProductObject[],
  skus: ProductSkuObject[],
): ProductSkuView[] {
  const countMap = new Map<string, number>();
  for (const s of skus) {
    const pid = s.product_id;
    if (pid) {
      countMap.set(pid, (countMap.get(pid) ?? 0) + 1);
    }
  }
  return products.map((product) => ({
    product,
    skuCount: countMap.get(product.id) ?? 0,
  }));
}

// ── Component ─────────────────────────────────────────────────────────────────

export function ProductInventoryPage() {
  const [products, setProducts] = useState<ProductObject[]>([]);
  const [skus, setSkus] = useState<ProductSkuObject[]>([]);
  const [categories, setCategories] = useState<CategoryObject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<ProductObject | null>(null);

  useEffect(() => {
    loadAll();
  }, []);

  function loadAll() {
    setLoading(true);
    setError(null);
    Promise.all([
      apiGet<{ items?: ProductObject[]; objects?: ProductObject[] }>("/v1/objects/Product"),
      apiGet<{ items?: ProductSkuObject[]; objects?: ProductSkuObject[] }>("/v1/objects/ProductSku"),
      apiGet<{ items?: CategoryObject[]; objects?: CategoryObject[] }>("/v1/objects/Category"),
    ])
      .then(([pRes, sRes, cRes]) => {
        setProducts(pRes.items || pRes.objects || []);
        setSkus(sRes.items || sRes.objects || []);
        setCategories(cRes.items || cRes.objects || []);
      })
      .catch((e) => setError(String((e as Error).message || e)))
      .finally(() => setLoading(false));
  }

  // W02 派生视图（纯函数 · FR-D1.5-9）
  const productSkuView = useMemo(() => mergeProductSkuView(products, skus), [products, skus]);
  const lowStockSkus = useMemo(() => filterLowStockSkus(skus), [skus]);
  const lowQualityProducts = useMemo(() => filterLowQualityProducts(products), [products]);
  const categoryTree = useMemo(() => buildCategoryTree(categories), [categories]);

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <PageChrome title="商品与库存运营台" lede="商品 · SKU · 库存 · 分类 · 质量告警 — 数据展示层（W02 最小版）">
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {/* 指标卡 · W02 总览 */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
          <StatCard title="商品总数" value={String(products.length)} sublabel="P02 Product" color="#3B82F6" />
          <StatCard title="SKU 总数" value={String(skus.length)} sublabel="P03 ProductSku" color="#6366F1" />
          <StatCard
            title="低库存 SKU"
            value={String(lowStockSkus.length)}
            sublabel="stock_health=low"
            color={lowStockSkus.length > 0 ? "#F59E0B" : "#10B981"}
          />
          <StatCard
            title="质量告警"
            value={String(lowQualityProducts.length)}
            sublabel="quality_score<0.8"
            color={lowQualityProducts.length > 0 ? "#EF4444" : "#10B981"}
          />
        </div>

        {error && (
          <div style={{ background: "#FEE2E2", color: "#DC2626", padding: "8px 12px", borderRadius: 2, fontSize: 13 }}>
            加载失败: {error}
          </div>
        )}

        {/* 主体：商品/SKU 列表 + 详情侧栏 */}
        <div
          data-testid="w02-product-list"
          style={{
            background: "#fff",
            borderRadius: 2,
            border: "1px solid #E5E7EB",
            overflow: "hidden",
          }}
        >
          <div style={{ padding: "8px 12px", borderBottom: "1px solid #E5E7EB", background: "#F9FAFB" }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: "#1F2937" }}>商品 / SKU 列表</span>
            <span style={{ fontSize: 11, color: "#9CA3AF", marginLeft: 8 }}>
              {productSkuView.length} 个商品 · {skus.length} 个 SKU
            </span>
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "#F9FAFB" }}>
                <th style={{ textAlign: "left", padding: "8px 12px", color: "#374151" }}>商品</th>
                <th style={{ textAlign: "left", padding: "8px 12px", color: "#374151" }}>分类</th>
                <th style={{ textAlign: "right", padding: "8px 12px", color: "#374151" }}>SKU 数</th>
                <th style={{ textAlign: "center", padding: "8px 12px", color: "#374151" }}>质量分</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={4} style={{ textAlign: "center", padding: 24, color: "#9CA3AF" }}>加载中...</td>
                </tr>
              )}
              {!loading && productSkuView.length === 0 && (
                <tr>
                  <td colSpan={4} style={{ textAlign: "center", padding: 24, color: "#9CA3AF" }}>暂无商品 · 请到数据源管理接入</td>
                </tr>
              )}
              {productSkuView.map(({ product, skuCount }) => {
                const isSelected = selectedProduct?.id === product.id;
                const qScore = product.quality_score;
                return (
                  <tr
                    key={product.id}
                    onClick={() => setSelectedProduct(product)}
                    style={{
                      cursor: "pointer",
                      background: isSelected ? "#EFF6FF" : undefined,
                      borderBottom: "1px solid #F3F4F6",
                    }}
                  >
                    <td style={{ padding: "8px 12px", color: "#1F2937" }}>{product.title || product.id}</td>
                    <td style={{ padding: "8px 12px", color: "#6B7280", fontSize: 12 }}>
                      {String(product.category_id || "—")}
                    </td>
                    <td style={{ padding: "8px 12px", textAlign: "right", fontWeight: 600, color: "#6366F1" }}>
                      {skuCount}
                    </td>
                    <td style={{ padding: "8px 12px", textAlign: "center" }}>
                      <QualityBadge score={qScore} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* 低库存队列 + 质量告警 双栏 */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          {/* W02 低库存队列 Widget · FR-D1.5-9 */}
          <div
            data-testid="w02-low-stock-queue"
            style={{ background: "#fff", borderRadius: 2, border: "1px solid #E5E7EB", padding: 12 }}
          >
            <div style={{ fontSize: 13, fontWeight: 600, color: "#1F2937", marginBottom: 8 }}>
              低库存队列
              <span
                style={{
                  marginLeft: 8,
                  fontSize: 11,
                  padding: "1px 8px",
                  borderRadius: 4,
                  background: lowStockSkus.length > 0 ? "#FEF3C7" : "#F3F4F6",
                  color: lowStockSkus.length > 0 ? "#D97706" : "#6B7280",
                }}
              >
                {lowStockSkus.length} 个 SKU
              </span>
            </div>
            {lowStockSkus.length === 0 ? (
              <p style={{ fontSize: 12, color: "#9CA3AF", margin: 0 }}>库存充足 · 无低库存 SKU</p>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ background: "#F9FAFB" }}>
                    <th style={{ textAlign: "left", padding: "6px 8px", color: "#374151" }}>SKU</th>
                    <th style={{ textAlign: "left", padding: "6px 8px", color: "#374151" }}>商品</th>
                    <th style={{ textAlign: "center", padding: "6px 8px", color: "#374151" }}>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {lowStockSkus.slice(0, 20).map((s) => (
                    <tr key={String(s.id)} style={{ borderBottom: "1px solid #F3F4F6" }}>
                      <td style={{ padding: "6px 8px", fontFamily: "monospace", color: "#1F2937" }}>
                        {String(s.sku_no || s.id)}
                      </td>
                      <td style={{ padding: "6px 8px", color: "#6B7280" }}>{String(s.product_id || "—")}</td>
                      <td style={{ padding: "6px 8px", textAlign: "center" }}>
                        <span style={{ background: "#FEF3C7", color: "#D97706", padding: "1px 6px", borderRadius: 3, fontSize: 11 }}>
                          {String(s.stock_health)}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* W02 质量告警 Widget · FR-D1.5-9 */}
          <div
            data-testid="w02-quality-alerts"
            style={{ background: "#fff", borderRadius: 2, border: "1px solid #E5E7EB", padding: 12 }}
          >
            <div style={{ fontSize: 13, fontWeight: 600, color: "#1F2937", marginBottom: 8 }}>
              质量告警
              <span
                style={{
                  marginLeft: 8,
                  fontSize: 11,
                  padding: "1px 8px",
                  borderRadius: 4,
                  background: lowQualityProducts.length > 0 ? "#FEE2E2" : "#F3F4F6",
                  color: lowQualityProducts.length > 0 ? "#DC2626" : "#6B7280",
                }}
              >
                {lowQualityProducts.length} 个商品
              </span>
            </div>
            {lowQualityProducts.length === 0 ? (
              <p style={{ fontSize: 12, color: "#9CA3AF", margin: 0 }}>质量良好 · 无低分商品</p>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ background: "#F9FAFB" }}>
                    <th style={{ textAlign: "left", padding: "6px 8px", color: "#374151" }}>商品</th>
                    <th style={{ textAlign: "right", padding: "6px 8px", color: "#374151" }}>质量分</th>
                  </tr>
                </thead>
                <tbody>
                  {lowQualityProducts.slice(0, 20).map((p) => (
                    <tr key={String(p.id)} style={{ borderBottom: "1px solid #F3F4F6" }}>
                      <td style={{ padding: "6px 8px", color: "#1F2937" }}>{p.title || p.id}</td>
                      <td style={{ padding: "6px 8px", textAlign: "right", fontWeight: 600, color: "#DC2626" }}>
                        {String(p.quality_score)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>

        {/* W02 分类树 Widget · FR-D1.5-9 · P04 Category 嵌套展示 */}
        <div
          data-testid="w02-category-tree"
          style={{ background: "#fff", borderRadius: 2, border: "1px solid #E5E7EB", padding: 16 }}
        >
          <div style={{ fontSize: 13, fontWeight: 600, color: "#1F2937", marginBottom: 12 }}>分类树</div>
          {categoryTree.length === 0 ? (
            <p style={{ fontSize: 12, color: "#9CA3AF", margin: 0 }}>暂无分类 · 请到数据源管理接入</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {categoryTree.map((node) => (
                <CategoryTreeView key={node.id} node={node} depth={0} />
              ))}
            </div>
          )}
        </div>
      </div>
    </PageChrome>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({ title, value, sublabel, color }: { title: string; value: string; sublabel: string; color: string }) {
  return (
    <div
      style={{
        background: "#fff",
        borderRadius: 2,
        border: "1px solid #E5E7EB",
        padding: 16,
        display: "flex",
        flexDirection: "column",
        gap: 4,
      }}
    >
      <div style={{ fontSize: 11, color: "#9CA3AF", fontWeight: 500 }}>{title}</div>
      <div style={{ fontSize: 28, fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: 11, color: "#9CA3AF" }}>{sublabel}</div>
    </div>
  );
}

function QualityBadge({ score }: { score: number | null | undefined }) {
  if (score == null) {
    return <span style={{ fontSize: 11, color: "#9CA3AF" }}>—</span>;
  }
  const isLow = score < 0.8;
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: 4,
        fontSize: 11,
        fontWeight: 500,
        background: isLow ? "#FEE2E2" : "#D1FAE5",
        color: isLow ? "#DC2626" : "#059669",
      }}
    >
      {score.toFixed(2)}
    </span>
  );
}

function CategoryTreeView({ node, depth }: { node: CategoryTreeNode; depth: number }) {
  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <div
        style={{
          padding: "4px 8px",
          paddingLeft: 8 + depth * 20,
          fontSize: 13,
          color: "#374151",
          borderRadius: 2,
        }}
      >
        <span style={{ color: "#6366F1", marginRight: 6 }}>{depth === 0 ? "▸" : "└"}</span>
        {node.name || node.id}
        {node.children.length > 0 && (
          <span style={{ fontSize: 10, color: "#9CA3AF", marginLeft: 6 }}>({node.children.length})</span>
        )}
      </div>
      {node.children.map((child) => (
        <CategoryTreeView key={child.id} node={child} depth={depth + 1} />
      ))}
    </div>
  );
}
