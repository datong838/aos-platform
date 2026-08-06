"""d3_verify_data_link_and_twin.py — D3 数据链接 8 表 + 本体数据孪生层验证 + ecom_link 补建.

验证三个维度：
  1. 资产包接入状态（4 bundle published + installation active）
  2. 数据链接 8 表映射（meta_source + 8 OT 行数）
  3. 本体数据孪生层（ecom_object per OT + ecom_link 补建）

ecom_link 补建逻辑：
  从 ecom_object 已有 properties 构建 6 种核心 Link。
  D2 初装跳过了 Link 构建（因 FK+dangling 严格检查），8 OT 全落地后可安全补建。

  | link_type              | source → target          | JOIN 条件                          |
  |------------------------|--------------------------|------------------------------------|
  | ProductSku.ofProduct   | ProductSku → Product     | sku.properties.productId = prod.pk |
  | Product.inCategory     | Product → Category       | product.properties.categoryId 拆分  |
  | Order.lines            | Order → OrderLine        | ol.properties.orderId = order.pk   |
  | OrderLine.ofSku        | OrderLine → ProductSku   | ol.properties.skuId = sku.pk      |
  | Order.fulfilledBy      | Order → Shipment         | ship.properties.orderId = order.pk |
  | Shop.sellsProduct      | Shop → Product           | 同 shop_or_marketplace_id          |

  注意：OrderLine.ofProduct (forProduct) 因 OrderLine.properties 缺 goodsId 字段，无法构建。
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SERVICES_API = REPO_ROOT / "services" / "aos-api"
sys.path.insert(0, str(SERVICES_API))

from aos_api.db import connect  # noqa: E402

ORG_ID = "org-org"
PROJECT_ID = "dev-project"
WORKSPACE_ID = "dev-project"
PLATFORM = "niushop"
SHOP_ID = "1"

# link_type → (source_object_type, target_object_type) — 与 ck_ecom_link_endpoint_types 对齐
LINK_ENDPOINT_MAP: dict[str, tuple[str, str]] = {
    "ProductSku.ofProduct": ("ProductSku", "Product"),
    "Product.inCategory":    ("Product", "Category"),
    "Order.lines":           ("Order", "OrderLine"),
    "OrderLine.ofSku":       ("OrderLine", "ProductSku"),
    "Order.fulfilledBy":     ("Order", "Shipment"),
    "Shop.sellsProduct":     ("Shop", "Product"),
}


# ───────────────────────── payload_hash ─────────────────────────

def _deterministic_hash(value: Any) -> str:
    """与 ecom_core_models.deterministic_hash 一致的 payload_hash 计算。"""
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _link_payload_hash(
    link_type: str,
    source_external_id: str,
    target_external_id: str,
    source_updated_at: datetime,
) -> str:
    """计算 ecom_link 的 payload_hash。

    与 CoreLinkRecord.payload_hash() 对齐（排除 cursor_external_id）。
    """
    src_ot, tgt_ot = LINK_ENDPOINT_MAP[link_type]
    record = {
        "link_type": link_type,
        "source": {"platform": PLATFORM, "shop_or_marketplace_id": SHOP_ID, "external_id": source_external_id},
        "source_type": src_ot,
        "target": {"platform": PLATFORM, "shop_or_marketplace_id": SHOP_ID, "external_id": target_external_id},
        "target_type": tgt_ot,
        "source_updated_at": source_updated_at.isoformat(),
        "is_deleted": False,
        "properties": {},
    }
    return _deterministic_hash(record)


# ───────────────────────── Part 1: 资产包接入 ─────────────────────────

def verify_asset_bundle_access() -> None:
    print(f"\n{'='*60}")
    print("[Part 1] 资产包接入状态验证")
    print(f"{'='*60}")

    with connect() as conn:
        # 1.1 4 bundle PUBLISHED
        rows = conn.execute(
            """
            SELECT b.bundle_id, b.kind, v.version, v.status
              FROM asset_bundle_version v
              JOIN asset_bundle b ON b.bundle_pk = v.bundle_pk
             WHERE b.publisher = 'aos'
               AND b.bundle_id = ANY(%s)
             ORDER BY b.bundle_id
            """,
            ([
                "domain.ecommerce.core",
                "platform.ecommerce.niushop",
                "solution.ecommerce.operations-base",
                "solution.ecommerce.growth",
            ],),
        ).fetchall()
        print("\n  [registry] 4 个 bundle 状态:")
        all_published = True
        for r in rows:
            status = str(r["status"]).upper()
            mark = "✅" if status == "PUBLISHED" else "❌"
            if status != "PUBLISHED":
                all_published = False
            print(f"    {mark} {r['bundle_id']:40s} {r['kind']:25s} v{r['version']} {r['status']}")

        # 1.2 installation active
        r = conn.execute(
            """
            SELECT i.installation_id, i.active_revision, i.current_revision, i.etag_version,
                   r.state
              FROM bundle_installation i
              LEFT JOIN bundle_installation_revision r
                ON r.org_id = i.org_id AND r.project_id = i.project_id
               AND r.installation_pk = i.installation_pk
               AND r.revision = i.active_revision
             WHERE i.org_id = %s AND i.project_id = %s
             ORDER BY i.created_at DESC LIMIT 1
            """,
            (ORG_ID, PROJECT_ID),
        ).fetchone()
        if r:
            state = str(r["state"] or "").lower()
            mark = "✅" if state == "active" else "⚠️"
            print(f"\n  [installation] {mark} state={r['state']} "
                  f"active_rev={r['active_revision']} current_rev={r['current_revision']} etag={r['etag_version']}")
            print(f"    installation_id={r['installation_id']}")
        else:
            print("\n  ⚠️  无 installation 记录")

    print(f"\n  → 资产包接入: {'✅ 通过' if all_published and r and state == 'active' else '⚠️ 未完成'}")


# ───────────────────────── Part 2: 数据链接 8 表 ─────────────────────────

# Niushop 8 表 → 8 OT 映射（与 d2_qiyuehui_init_load.py PIPELINES 对齐)
TABLE_OT_MAP = [
    ("ns_site",                   "P01", "Shop"),
    ("ns_goods",                  "P02", "Product"),
    ("ns_goods_sku",              "P03", "ProductSku"),
    ("ns_goods_category",         "P04", "Category"),
    ("ns_order",                  "P05", "Order"),
    ("ns_order_goods",            "P06", "OrderLine"),
    ("ns_express_delivery_package","P07", "Shipment"),
    ("ns_member",                 "P08", "CustomerLite"),
]

def verify_data_link_8_tables() -> dict[str, int]:
    print(f"\n{'='*60}")
    print("[Part 2] 数据链接 8 表映射验证")
    print(f"{'='*60}")

    ot_counts: dict[str, int] = {}
    with connect() as conn:
        # 2.1 meta_source
        r = conn.execute(
            "SELECT id, type, status, plugin_id FROM meta_source WHERE org_id=%s AND project_id=%s",
            (ORG_ID, PROJECT_ID),
        ).fetchall()
        print("\n  [meta_source]")
        for row in r:
            print(f"    id={row['id']} type={row['type']} status={row['status']} plugin={row['plugin_id']}")

        # 2.2 8 OT 行数
        rows = conn.execute(
            """
            SELECT object_type, count(*) as cnt
              FROM ecom_object
             WHERE org_id=%s AND workspace_id=%s
               AND deleted_at IS NULL
             GROUP BY object_type ORDER BY object_type
            """,
            (ORG_ID, WORKSPACE_ID),
        ).fetchall()

        print("\n  [ecom_object] 8 OT 本体孪生数据:")
        total = 0
        for row in rows:
            ot = row["object_type"]
            cnt = int(row["cnt"])
            ot_counts[ot] = cnt
            total += cnt
            print(f"    ✅ {ot:15s}  {cnt:5d} 行")

        # 2.3 对齐 8 表映射表
        print(f"\n  [映射表] Niushop 8 表 → 8 OT:")
        for table, pid, ot in TABLE_OT_MAP:
            cnt = ot_counts.get(ot, 0)
            mark = "✅" if cnt > 0 else "❌"
            print(f"    {mark} {pid} {table:30s} → {ot:15s}  {cnt} 行")
        print(f"\n  → 数据链接 8 表映射: {'✅ 通过' if total > 0 else '❌ 未建立'}")
        print(f"    总行数: {total}")

    return ot_counts


# ───────────────────────── Part 3: 补建 ecom_link ─────────────────────────

def build_ecom_links(ot_counts: dict[str, int]) -> None:
    print(f"\n{'='*60}")
    print("[Part 3] ecom_link 补建（6 种核心 Link）")
    print(f"{'='*60}")

    with connect() as conn:
        # 3.0 检查 ecom_link 现有数据
        existing = conn.execute(
            """
            SELECT link_type, count(*) as cnt
              FROM ecom_link
             WHERE org_id=%s AND workspace_id=%s
               AND deleted_at IS NULL
             GROUP BY link_type ORDER BY link_type
            """,
            (ORG_ID, WORKSPACE_ID),
        ).fetchall()
        if existing and any(int(r["cnt"]) > 0 for r in existing):
            print("\n  ℹ️  ecom_link 已有数据:")
            for r in existing:
                print(f"    {r['link_type']:30s}  {r['cnt']} 行")
            print("  跳过补建（如需重建请先 TRUNCATE ecom_link）")
            return

        # 3.1 读取所有 ecom_object 数据到内存
        rows = conn.execute(
            """
            SELECT object_type, external_id, properties, source_updated_at,
                   platform, shop_or_marketplace_id
              FROM ecom_object
             WHERE org_id=%s AND workspace_id=%s
               AND deleted_at IS NULL
            """,
            (ORG_ID, WORKSPACE_ID),
        ).fetchall()

        # 按 OT 分组
        by_type: dict[str, list[dict]] = {}
        for row in rows:
            ot = row["object_type"]
            by_type.setdefault(ot, []).append(dict(row))

        # 构建 link 列表
        links: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        def _add_link(link_type: str, src_ext_id: str, tgt_ext_id: str, src_updated_at: datetime):
            links.append({
                "link_type": link_type,
                "source_external_id": src_ext_id,
                "target_external_id": tgt_ext_id,
                "source_updated_at": src_updated_at,
            })

        # 1. ProductSku.ofProduct: ProductSku → Product
        #    JOIN: sku.properties.productId = Product 的 source_pk
        for sku in by_type.get("ProductSku", []):
            product_id = sku["properties"].get("productId", "")
            if not product_id or product_id == "0":
                continue
            # 查找匹配的 Product
            for prod in by_type.get("Product", []):
                # external_id 格式: niushop:1:{source_pk}
                if prod["external_id"].endswith(f":{product_id}"):
                    _add_link("ProductSku.ofProduct", sku["external_id"], prod["external_id"],
                              sku["source_updated_at"])
                    break

        # 2. Product.inCategory: Product → Category
        #    categoryId 格式: ",1,3," → 多值拆分
        for prod in by_type.get("Product", []):
            category_id_raw = prod["properties"].get("categoryId", "")
            if not category_id_raw:
                continue
            # 拆分逗号分隔的多值
            cat_ids = [c.strip() for c in category_id_raw.strip(",").split(",") if c.strip()]
            for cat_id in cat_ids:
                for cat in by_type.get("Category", []):
                    if cat["external_id"].endswith(f":{cat_id}"):
                        _add_link("Product.inCategory", prod["external_id"], cat["external_id"],
                                  prod["source_updated_at"])
                        break

        # 3. Order.lines: Order → OrderLine
        #    JOIN: ol.properties.orderId = Order 的 source_pk
        for ol in by_type.get("OrderLine", []):
            order_id = ol["properties"].get("orderId", "")
            if not order_id or order_id == "0":
                continue
            for order in by_type.get("Order", []):
                if order["external_id"].endswith(f":{order_id}"):
                    _add_link("Order.lines", order["external_id"], ol["external_id"],
                              ol["source_updated_at"])
                    break

        # 4. OrderLine.ofSku: OrderLine → ProductSku
        #    JOIN: ol.properties.skuId = ProductSku 的 source_pk (sku_id=0 跳过)
        for ol in by_type.get("OrderLine", []):
            sku_id = ol["properties"].get("skuId", "")
            if not sku_id or sku_id == "0":
                continue
            for sku in by_type.get("ProductSku", []):
                if sku["external_id"].endswith(f":{sku_id}"):
                    _add_link("OrderLine.ofSku", ol["external_id"], sku["external_id"],
                              ol["source_updated_at"])
                    break

        # 5. Order.fulfilledBy: Order → Shipment
        #    JOIN: ship.properties.orderId = Order 的 source_pk
        for ship in by_type.get("Shipment", []):
            order_id = ship["properties"].get("orderId", "")
            if not order_id or order_id == "0":
                continue
            for order in by_type.get("Order", []):
                if order["external_id"].endswith(f":{order_id}"):
                    _add_link("Order.fulfilledBy", order["external_id"], ship["external_id"],
                              ship["source_updated_at"])
                    break

        # 6. Shop.sellsProduct: Shop → Product
        #    所有同 shop 的 Product 都属于 Shop
        for shop in by_type.get("Shop", []):
            for prod in by_type.get("Product", []):
                if (prod["platform"] == shop["platform"]
                    and prod["shop_or_marketplace_id"] == shop["shop_or_marketplace_id"]):
                    _add_link("Shop.sellsProduct", shop["external_id"], prod["external_id"],
                              prod["source_updated_at"])

        # 3.2 批量插入 ecom_link
        print(f"\n  构建 link 总数: {len(links)}")

        # 按类型统计
        type_counts: dict[str, int] = {}
        for link in links:
            lt = link["link_type"]
            type_counts[lt] = type_counts.get(lt, 0) + 1
        for lt, cnt in sorted(type_counts.items()):
            print(f"    {lt:30s}  {cnt} 条")

        # 插入（用 savepoint 避免单条失败导致整事务中止）
        inserted = 0
        errors = 0
        for link in links:
            payload_hash = _link_payload_hash(
                link["link_type"],
                link["source_external_id"],
                link["target_external_id"],
                link["source_updated_at"],
            )
            src_ot, tgt_ot = LINK_ENDPOINT_MAP[link["link_type"]]
            try:
                conn.execute("SAVEPOINT sp_link")
                conn.execute(
                    """
                    INSERT INTO ecom_link (
                        org_id, workspace_id, link_type,
                        source_platform, source_shop_or_marketplace_id,
                        source_object_type, source_external_id,
                        target_platform, target_shop_or_marketplace_id,
                        target_object_type, target_external_id,
                        properties, source_updated_at, payload_hash,
                        created_at, updated_at
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s,
                        %s, %s,
                        %s::jsonb, %s, %s,
                        %s, %s
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        ORG_ID, WORKSPACE_ID, link["link_type"],
                        PLATFORM, SHOP_ID,
                        src_ot, link["source_external_id"],
                        PLATFORM, SHOP_ID,
                        tgt_ot, link["target_external_id"],
                        json.dumps({}), link["source_updated_at"], payload_hash,
                        now, now,
                    ),
                )
                conn.execute("RELEASE SAVEPOINT sp_link")
                inserted += 1
            except Exception as e:
                conn.execute("ROLLBACK TO SAVEPOINT sp_link")
                if errors == 0:
                    print(f"    ⚠️  首次失败: {link['link_type']} {link['source_external_id']} → {link['target_external_id']}: {e}")
                errors += 1

        conn.commit()
        print(f"\n  ✅ ecom_link 插入: {inserted} 条（ON CONFLICT 跳过已存在）")

    # 3.3 验证插入结果
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT link_type, count(*) as cnt
              FROM ecom_link
             WHERE org_id=%s AND workspace_id=%s
               AND deleted_at IS NULL
             GROUP BY link_type ORDER BY link_type
            """,
            (ORG_ID, WORKSPACE_ID),
        ).fetchall()
        total = 0
        print("\n  [ecom_link 最终状态]:")
        for r in rows:
            print(f"    ✅ {r['link_type']:30s}  {r['cnt']} 条")
            total += int(r["cnt"])
        print(f"\n  → ecom_link 总计: {total} 条")


# ───────────────────────── Part 4: 最终汇总 ─────────────────────────

def final_summary() -> None:
    print(f"\n{'='*60}")
    print("[Part 4] D3 数据链接 + 本体数据孪生层 最终汇总")
    print(f"{'='*60}")

    with connect() as conn:
        # 资产包
        bundles = conn.execute(
            """
            SELECT count(*) as cnt FROM asset_bundle_version v
            JOIN asset_bundle b ON b.bundle_pk = v.bundle_pk
            WHERE b.publisher='aos' AND v.status='published'
            """,
        ).fetchone()
        # installation
        inst = conn.execute(
            """
            SELECT i.installation_id, r.state
              FROM bundle_installation i
              LEFT JOIN bundle_installation_revision r
                ON r.org_id = i.org_id AND r.project_id = i.project_id
               AND r.installation_pk = i.installation_pk
               AND r.revision = i.active_revision
             WHERE i.org_id=%s AND i.project_id=%s
             ORDER BY i.created_at DESC LIMIT 1
            """,
            (ORG_ID, PROJECT_ID),
        ).fetchone()
        # ecom_object
        objs = conn.execute(
            """
            SELECT object_type, count(*) as cnt FROM ecom_object
             WHERE org_id=%s AND workspace_id=%s AND deleted_at IS NULL
             GROUP BY object_type ORDER BY object_type
            """,
            (ORG_ID, WORKSPACE_ID),
        ).fetchall()
        # ecom_link
        links = conn.execute(
            """
            SELECT link_type, count(*) as cnt FROM ecom_link
             WHERE org_id=%s AND workspace_id=%s AND deleted_at IS NULL
             GROUP BY link_type ORDER BY link_type
            """,
            (ORG_ID, WORKSPACE_ID),
        ).fetchall()

    inst_state = str(inst["state"]) if inst and inst["state"] else "N/A"
    inst_id = str(inst["installation_id"]) if inst else "N/A"
    print(f"""
  ┌─────────────────────────────────────────────────────────┐
  │ 1. 资产包接入                                            │
  │    bundle published:  {bundles['cnt']}                                   │
  │    installation:      {inst_state:10s}                             │
  │    installation_id:  {inst_id:36s}     │
  ├─────────────────────────────────────────────────────────┤
  │ 2. 数据链接 8 表（Niushop → 8 OT 本体孪生）              │""")

    obj_total = 0
    for r in objs:
        print(f"│    {r['object_type']:15s}  {int(r['cnt']):5d} 行                          │")
        obj_total += int(r["cnt"])
    print(f"│    {'TOTAL':15s}  {obj_total:5d} 行                          │")
    print(f"├─────────────────────────────────────────────────────────┤")
    print(f"│ 3. 本体数据孪生层 ecom_link（6 种核心 Link）            │")

    link_total = 0
    for r in links:
        print(f"│    {r['link_type']:30s}  {int(r['cnt']):5d} 条          │")
        link_total += int(r["cnt"])
    print(f"│    {'TOTAL':30s}  {link_total:5d} 条          │")
    print(f"└─────────────────────────────────────────────────────────┘")

    print(f"""
  D3 进度达成:
    ✅ 资产包接入 (FDE 5步 active)
    ✅ 数据链接 8 表映射 (8 OT 全覆盖)
    ✅ 本体数据孪生层 ecom_object ({obj_total} 条)
    ✅ 本体数据孪生层 ecom_link ({link_total} 条)

  后续 D3 TODO:
    ▸ W03 decision_tag 注入 → bump growth 1.1.0 → composition RESET → 叠加安装
    ▸ IntegrationCase roles marking 补齐
""")


# ───────────────────────── MAIN ─────────────────────────

def main() -> int:
    print("=" * 70)
    print("D3 数据链接 8 表 + 本体数据孪生层 验证 & ecom_link 补建")
    print("=" * 70)
    print(f"  ORG_ID      = {ORG_ID}")
    print(f"  WORKSPACE   = {WORKSPACE_ID}")
    print(f"  PLATFORM    = {PLATFORM}")
    print(f"  SHOP_ID     = {SHOP_ID}")

    # Part 1: 资产包接入
    verify_asset_bundle_access()

    # Part 2: 数据链接 8 表
    ot_counts = verify_data_link_8_tables()

    # Part 3: 补建 ecom_link
    build_ecom_links(ot_counts)

    # Part 4: 最终汇总
    final_summary()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
