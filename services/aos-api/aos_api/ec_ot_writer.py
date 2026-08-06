"""D1-W3: G5 OTWriter — executor 输出落地到 ecom_object + ecom_link。

骨架阶段：空实现（返回零计数），不落地 OT。
Worker W3 实现：调用 ecom_consistency_store.apply_batch（BatchCommand 单事务：
upsert→link→checkpoint→receipt）。

一致性语义（旧版本不覆盖/同版本同 hash 幂等/同版本异 hash 冲突/tombstone/
悬挂或跨租户 Link 拒绝/整事务回滚）由 ecom_consistency_store 内核保证，
本模块只负责按 FR-D1-2 约定构造 BatchCommand 并传播结果/异常。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from aos_api.ecom_core_models import (
    BatchCommand,
    CoreLinkRecord,
    CoreObjectRecord,
    SyncScope,
)
from aos_api.public_contracts import (
    ExternalIdentityKey,
    ForwardEnumValue,
    StableCursor,
)

# Niushop 源命名空间常量（frozen/02 §通用骨架：site_id=1）
_NIUSHOP_PLATFORM = "niushop"
_NIUSHOP_SITE_ID = "1"
_DEFAULT_SOURCE_TIMEZONE = "+00:00"
_DEFAULT_SCHEMA_VERSION = 1
# ForwardEnumValue 的最小 raw→canonical 映射；具体平台枚举由上游 Normalize 规范化
_STATUS_MAPPING = {"ACTIVE": "active", "DELETED": "deleted"}


def sink_to_ot(
    eng: Any,
    scope: Any,
    pipeline: Any,
    output_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """将输出行落地为 OT + Link。

    调用 ``ecom_consistency_store.apply_batch``（BatchCommand 单事务：
    upsert→link→checkpoint→receipt）。

    向后兼容：``eng`` 未注入 ``ecom_consistency_store`` 或 ``output_rows`` 为空时，
    返回零计数（骨架行为），等总控组装后 store 必存在。
    """
    # 空 batch 无法构造 BatchCommand（validator 拒绝空 objects+links）
    if not output_rows:
        return {"objects_written": 0, "links_written": 0}

    # 总控负责在 eng 上注入 ecom_consistency_store；缺失时退化为骨架零计数
    store = getattr(eng, "ecom_consistency_store", None)
    if store is None:
        return {"objects_written": 0, "links_written": 0}

    sync_scope = _build_sync_scope(scope, pipeline)
    objects, links = _normalize_rows(output_rows, sync_scope)

    # 全部行既不是合法 object 也不是合法 link 时，退化为零计数
    if not objects and not links:
        return {"objects_written": 0, "links_written": 0}

    command = _build_batch_command(
        sync_scope=sync_scope,
        objects=objects,
        links=links,
        pipeline_id=str(pipeline.id),
        store=store,
    )
    result = store.apply_batch(command)
    return {
        "objects_written": result.objects_written,
        "links_written": result.links_written,
    }


def _build_sync_scope(scope: Any, pipeline: Any) -> SyncScope:
    """从 TenantScope 构造 SyncScope（Niushop site_id=1，stream=pipeline.id）。

    TenantScope.project_id 即 SyncScope.workspace_id（见 tenant_scope.from_workspace）。
    """
    return SyncScope(
        org_id=scope.org_id,
        workspace_id=scope.project_id,
        platform=_NIUSHOP_PLATFORM,
        shop_or_marketplace_id=_NIUSHOP_SITE_ID,
        stream=str(pipeline.id),
    )


def _normalize_rows(
    rows: list[dict[str, Any]],
    sync_scope: SyncScope,
) -> tuple[list[CoreObjectRecord], list[CoreLinkRecord]]:
    """把 output_rows 拆分为 CoreObjectRecord 和 CoreLinkRecord。

    约定：row 含 ``link_type`` 字段 → Link 行；否则 → Object 行。
    """
    objects: list[CoreObjectRecord] = []
    links: list[CoreLinkRecord] = []
    for row in rows:
        if "link_type" in row:
            link = _build_link(row, sync_scope)
            if link is not None:
                links.append(link)
        else:
            obj = _build_object(row, sync_scope)
            if obj is not None:
                objects.append(obj)
    return objects, links


def _build_object(row: dict[str, Any], sync_scope: SyncScope) -> CoreObjectRecord | None:
    """从 row 构造 CoreObjectRecord，应用 ``niushop:1:{source_pk}`` 命名空间。

    自动补齐 必填的 *At 时间属性（按 OT schema REQUIRED_PROPERTIES 约定）：
    - updatedAt: Product/ProductSku/Category/Order/OrderLine/Shipment/CustomerLite（源缺省时用 source_updated_at）
    - createdAt: Product/Order/CustomerLite（源缺省时用 source_updated_at）
    - shippedAt: Shipment（源缺省时先取 delivery_time，再回退 source_updated_at）

    D1.5: CustomerLite 必填 createdAt/updatedAt（frozen/02 §P08），与 Product/Order 同口径补齐。
    """
    object_type = row.get("ot")
    if not object_type:
        return None

    source_dt = _parse_datetime(row["source_updated_at"])
    source_utc_iso = source_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    properties = dict(row.get("properties", {}))

    if object_type in ("Product", "ProductSku", "Category", "Order", "OrderLine", "Shipment", "CustomerLite",
                       # D4: 4 个新 OT 的 REQUIRED_PROPERTIES 都含 updatedAt
                       "Weapp", "SystemConfig", "ProductReview", "Payment"):
        properties.setdefault("updatedAt", source_utc_iso)

    if object_type in ("Product", "Order", "CustomerLite"):
        properties.setdefault("createdAt", source_utc_iso)

    if object_type == "Shipment":
        if "shippedAt" not in properties:
            delivery_time = row.get("delivery_time")
            if isinstance(delivery_time, (int, float)) and delivery_time > 0:
                properties["shippedAt"] = datetime.fromtimestamp(
                    float(delivery_time), tz=timezone.utc
                ).strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                properties["shippedAt"] = source_utc_iso

    external_id = row.get("external_id") or _format_external_id(str(row["source_pk"]))
    identity = ExternalIdentityKey(
        org_id=sync_scope.org_id,
        workspace_id=sync_scope.workspace_id,
        platform=sync_scope.platform,
        shop_or_marketplace_id=sync_scope.shop_or_marketplace_id,
        external_id=external_id,
    )
    is_deleted = bool(row.get("is_deleted", False))
    status_raw = row.get("status_raw", "DELETED" if is_deleted else "ACTIVE")
    return CoreObjectRecord(
        identity=identity,
        object_type=object_type,
        source_updated_at=source_dt,
        source_timezone=row.get("source_timezone", _DEFAULT_SOURCE_TIMEZONE),
        status=ForwardEnumValue.from_raw(status_raw, _STATUS_MAPPING),
        is_deleted=is_deleted,
        schema_version=int(row.get("schema_version", _DEFAULT_SCHEMA_VERSION)),
        properties=properties,
    )


def _build_link(row: dict[str, Any], sync_scope: SyncScope) -> CoreLinkRecord | None:
    """从 row 构造 CoreLinkRecord，两端应用 ``niushop:1:{source_pk}`` 命名空间。"""
    link_type = row.get("link_type")
    if not link_type:
        return None
    source_external_id = row.get("source_external_id") or _format_external_id(
        str(row["source_pk"])
    )
    target_external_id = row.get("target_external_id") or _format_external_id(
        str(row["target_source_pk"])
    )
    source_identity = ExternalIdentityKey(
        org_id=sync_scope.org_id,
        workspace_id=sync_scope.workspace_id,
        platform=sync_scope.platform,
        shop_or_marketplace_id=sync_scope.shop_or_marketplace_id,
        external_id=source_external_id,
    )
    target_identity = ExternalIdentityKey(
        org_id=sync_scope.org_id,
        workspace_id=sync_scope.workspace_id,
        platform=sync_scope.platform,
        shop_or_marketplace_id=sync_scope.shop_or_marketplace_id,
        external_id=target_external_id,
    )
    cursor_external_id = row.get("cursor_external_id") or source_external_id
    return CoreLinkRecord(
        link_type=link_type,
        source_type=row["source_type"],
        source=source_identity,
        target_type=row["target_type"],
        target=target_identity,
        source_updated_at=_parse_datetime(row["source_updated_at"]),
        cursor_external_id=cursor_external_id,
        is_deleted=bool(row.get("is_deleted", False)),
        properties=dict(row.get("properties", {})),
    )


def _format_external_id(source_pk: str) -> str:
    """构造 ``niushop:1:{source_pk}`` 命名空间下的唯一键（frozen/02 §通用骨架）。"""
    return f"{_NIUSHOP_PLATFORM}:{_NIUSHOP_SITE_ID}:{source_pk}"


def _parse_datetime(value: Any) -> datetime:
    """解析 datetime，保证 timezone-aware UTC。"""
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    # ISO 8601 字符串
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _build_batch_command(
    *,
    sync_scope: SyncScope,
    objects: list[CoreObjectRecord],
    links: list[CoreLinkRecord],
    pipeline_id: str,
    store: Any,
) -> BatchCommand:
    """构造 BatchCommand，查询当前 checkpoint version 作为 expected。

    - ``next_checkpoint`` 取 batch 内最大 (source_updated_at, external_id) 二元组
      （BatchCommand validator 要求 ``next_checkpoint >= max(batch_cursors)``）
    - ``expected_checkpoint_version`` 先查 store.get_checkpoint：None→0（首装），
      否则取当前 version（增量）
    - ``idempotency_key`` 基于 pipeline_id + max cursor，保证同 batch 重跑幂等
    """
    cursors = [record.cursor_key() for record in objects] + [
        link.cursor_key() for link in links
    ]
    max_cursor = max(cursors)
    next_checkpoint = StableCursor(
        source_updated_at_utc=max_cursor[0],
        external_id=max_cursor[1],
    )
    idempotency_key = (
        f"{pipeline_id}:{max_cursor[0].isoformat()}:{max_cursor[1]}"
    )

    # 先用 expected=0 构造 probe 查当前 checkpoint（get_checkpoint 只用 scope）
    probe = BatchCommand(
        scope=sync_scope,
        idempotency_key=idempotency_key,
        expected_checkpoint_version=0,
        next_checkpoint=next_checkpoint,
        objects=objects,
        links=links,
    )
    existing = store.get_checkpoint(probe)
    expected_version = int(existing["version"]) if existing else 0

    if expected_version == 0:
        return probe
    # frozen model：用 model_copy 更新 expected，重新构造会触发 validator 开销
    return probe.model_copy(update={"expected_checkpoint_version": expected_version})
