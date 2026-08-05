import { describe, expect, it } from "vitest";
import {
  filterLowStockSkus,
  filterLowQualityProducts,
  buildCategoryTree,
  mergeProductSkuView,
  type ProductObject,
  type ProductSkuObject,
  type CategoryObject,
} from "./ProductInventoryPage";

function makeProduct(overrides: Partial<ProductObject> = {}): ProductObject {
  return { id: "p-default", ...overrides };
}

function makeSku(overrides: Partial<ProductSkuObject> = {}): ProductSkuObject {
  return { id: "s-default", ...overrides };
}

function makeCategory(overrides: Partial<CategoryObject> = {}): CategoryObject {
  return { id: "c-default", ...overrides };
}

describe("ProductInventoryPage · filterLowStockSkus", () => {
  it("只返回 stock_health === 'low' 的 SKU", () => {
    const skus: ProductSkuObject[] = [
      makeSku({ id: "1", stock_health: "low" }),
      makeSku({ id: "2", stock_health: "normal" }),
      makeSku({ id: "3", stock_health: "low" }),
      makeSku({ id: "4", stock_health: "high" }),
    ];
    const low = filterLowStockSkus(skus);
    expect(low).toHaveLength(2);
    expect(low.map((s) => s.id).sort()).toEqual(["1", "3"]);
  });

  it("stock_health 缺失不返回", () => {
    const skus: ProductSkuObject[] = [
      makeSku({ id: "1" }),
      makeSku({ id: "2", stock_health: "low" }),
    ];
    const low = filterLowStockSkus(skus);
    expect(low).toHaveLength(1);
    expect(low[0].id).toBe("2");
  });

  it("stock_health 大小写敏感（LOW 不匹配）", () => {
    const skus: ProductSkuObject[] = [
      makeSku({ id: "1", stock_health: "LOW" }),
      makeSku({ id: "2", stock_health: "low" }),
    ];
    const low = filterLowStockSkus(skus);
    expect(low).toHaveLength(1);
    expect(low[0].id).toBe("2");
  });

  it("不修改原数组", () => {
    const skus: ProductSkuObject[] = [
      makeSku({ id: "1", stock_health: "low" }),
      makeSku({ id: "2", stock_health: "normal" }),
    ];
    const snapshot = JSON.parse(JSON.stringify(skus));
    filterLowStockSkus(skus);
    expect(JSON.parse(JSON.stringify(skus))).toEqual(snapshot);
  });

  it("空数组返回空", () => {
    expect(filterLowStockSkus([])).toEqual([]);
  });
});

describe("ProductInventoryPage · filterLowQualityProducts", () => {
  it("只返回 quality_score < 0.8 的商品", () => {
    const products: ProductObject[] = [
      makeProduct({ id: "1", quality_score: 0.5 }),
      makeProduct({ id: "2", quality_score: 0.9 }),
      makeProduct({ id: "3", quality_score: 0.79 }),
    ];
    const lowQ = filterLowQualityProducts(products);
    expect(lowQ).toHaveLength(2);
    expect(lowQ.map((p) => p.id).sort()).toEqual(["1", "3"]);
  });

  it("quality_score === 0.8 不返回（严格小于）", () => {
    const products: ProductObject[] = [
      makeProduct({ id: "1", quality_score: 0.8 }),
      makeProduct({ id: "2", quality_score: 0.79 }),
    ];
    const lowQ = filterLowQualityProducts(products);
    expect(lowQ).toHaveLength(1);
    expect(lowQ[0].id).toBe("2");
  });

  it("quality_score === null 不返回（null 安全降级）", () => {
    const products: ProductObject[] = [
      makeProduct({ id: "1", quality_score: null }),
      makeProduct({ id: "2", quality_score: 0.3 }),
    ];
    const lowQ = filterLowQualityProducts(products);
    expect(lowQ).toHaveLength(1);
    expect(lowQ[0].id).toBe("2");
  });

  it("quality_score 缺失不返回", () => {
    const products: ProductObject[] = [
      makeProduct({ id: "1" }),
      makeProduct({ id: "2", quality_score: 0.5 }),
    ];
    const lowQ = filterLowQualityProducts(products);
    expect(lowQ).toHaveLength(1);
    expect(lowQ[0].id).toBe("2");
  });

  it("空数组返回空", () => {
    expect(filterLowQualityProducts([])).toEqual([]);
  });
});

describe("ProductInventoryPage · buildCategoryTree", () => {
  it("按 parent_id 构造嵌套树（根→子→孙）", () => {
    const categories: CategoryObject[] = [
      makeCategory({ id: "cat-root", name: "根", parent_id: undefined }),
      makeCategory({ id: "cat-child", name: "子", parent_id: "cat-root" }),
      makeCategory({ id: "cat-grand", name: "孙", parent_id: "cat-child" }),
    ];
    const tree = buildCategoryTree(categories);
    expect(tree).toHaveLength(1);
    expect(tree[0].id).toBe("cat-root");
    expect(tree[0].children).toHaveLength(1);
    expect(tree[0].children[0].id).toBe("cat-child");
    expect(tree[0].children[0].children).toHaveLength(1);
    expect(tree[0].children[0].children[0].id).toBe("cat-grand");
  });

  it("多个根节点各自挂载子节点", () => {
    const categories: CategoryObject[] = [
      makeCategory({ id: "r1", parent_id: undefined }),
      makeCategory({ id: "r2", parent_id: undefined }),
      makeCategory({ id: "c1", parent_id: "r1" }),
      makeCategory({ id: "c2", parent_id: "r2" }),
    ];
    const tree = buildCategoryTree(categories);
    expect(tree).toHaveLength(2);
    const r1 = tree.find((n) => n.id === "r1");
    const r2 = tree.find((n) => n.id === "r2");
    expect(r1?.children).toHaveLength(1);
    expect(r1?.children[0].id).toBe("c1");
    expect(r2?.children).toHaveLength(1);
    expect(r2?.children[0].id).toBe("c2");
  });

  it("parent_id 为空字符串视为根节点", () => {
    const categories: CategoryObject[] = [
      makeCategory({ id: "root", parent_id: "" }),
      makeCategory({ id: "child", parent_id: "root" }),
    ];
    const tree = buildCategoryTree(categories);
    expect(tree).toHaveLength(1);
    expect(tree[0].id).toBe("root");
  });

  it("空数组返回空", () => {
    expect(buildCategoryTree([])).toEqual([]);
  });
});

describe("ProductInventoryPage · mergeProductSkuView", () => {
  it("聚合每个商品的 SKU 数", () => {
    const products: ProductObject[] = [
      makeProduct({ id: "A", title: "商品A" }),
      makeProduct({ id: "B", title: "商品B" }),
    ];
    const skus: ProductSkuObject[] = [
      makeSku({ id: "s1", product_id: "A" }),
      makeSku({ id: "s2", product_id: "A" }),
      makeSku({ id: "s3", product_id: "B" }),
    ];
    const view = mergeProductSkuView(products, skus);
    expect(view).toHaveLength(2);
    const a = view.find((v) => v.product.id === "A");
    const b = view.find((v) => v.product.id === "B");
    expect(a?.skuCount).toBe(2);
    expect(b?.skuCount).toBe(1);
  });

  it("无 SKU 的商品 skuCount=0", () => {
    const products: ProductObject[] = [makeProduct({ id: "A" })];
    const view = mergeProductSkuView(products, []);
    expect(view).toHaveLength(1);
    expect(view[0].skuCount).toBe(0);
  });

  it("空商品数组返回空", () => {
    expect(mergeProductSkuView([], [])).toEqual([]);
  });

  it("保留 product 原始字段", () => {
    const products: ProductObject[] = [
      makeProduct({ id: "A", title: "商品A", quality_score: 0.9 }),
    ];
    const view = mergeProductSkuView(products, []);
    expect(view[0].product.id).toBe("A");
    expect(view[0].product.title).toBe("商品A");
    expect(view[0].product.quality_score).toBe(0.9);
  });
});
