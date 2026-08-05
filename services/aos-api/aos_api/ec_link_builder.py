"""D1-W3: Link 行构造 — 根据源表行流构造核心 Link 行。

骨架阶段：透传 rows，不追加 Link 行（与原 ec_live_executor 行为等价）。
Worker W3 实现：按 pipeline.target_ot 分发，构造 6 条核心 Link 行追加到 rows。

FR-D1-8 核心 Link 汇总（与 frozen/02 一致）：
| Link         | From → To                | 来源字段      | 完整性门禁                       |
|--------------|--------------------------|---------------|----------------------------------|
| hasSku       | Product → ProductSku     | goods_id      | SKU 不得指向不存在 Product        |
| inCategory   | Product → Category       | category_id  | 多分类字符串需先定义拆分契约       |
| contains     | Order → OrderLine        | order_id      | 行必须有订单头                     |
| forProduct   | OrderLine → Product      | goods_id      | 缺失进 DLQ，不自动造对象          |
| forSku       | OrderLine → ProductSku   | sku_id        | sku_id=0 规则需样本核验           |
| ships        | Shipment → Order         | order_id      | 包裹必须有订单头                   |

> placedByLite（Order → CustomerLite）在 D1 P05 侧保留 member_id 关联键，D1.5 才落地 Link。

约定（与 ec_ot_writer._normalize_rows 对齐）：
- Link 行含 ``link_type`` 字段 → ec_ot_writer 识别为 Link 行
- Link 行字段：link_type / source_type / source_pk / source_external_id /
  target_type / target_source_pk / target_external_id / source_updated_at /
  cursor_external_id / is_deleted / properties
- Object 行不含 ``link_type`` 字段
"""

from __future__ import annotations

from typing import Any


def build_link_rows(
    rows: list[dict[str, Any]],
    pipeline: Any,
) -> list[dict[str, Any]]:
    """根据 rows 构造 Link 行并追加到 rows 末尾。

    骨架阶段：透传 rows（不追加 Link 行），与原 ec_live_executor 行为等价。
    Worker W3 实现：按 pipeline.target_ot 分发到 _build_hasSku / _build_inCategory /
    _build_contains / _build_forProduct / _build_forSku / _build_ships，
    构造对应 Link 行追加到 rows。

    约束：
    - Link 行的 source_pk / target_source_pk 必须是源表真实主键
    - Link 行的 source_updated_at 取 source 行的 source_updated_at
    - 悬挂 Link（target 不存在）由 ec_ot_writer / ecom_consistency_store 拒绝
    """
    # 骨架：透传，不追加 Link 行
    return rows
