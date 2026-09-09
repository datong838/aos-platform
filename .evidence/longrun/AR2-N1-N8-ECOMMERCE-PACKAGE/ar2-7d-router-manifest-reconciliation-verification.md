# AR2-7D Router 权威清单对账验证

- 基线 `m1@681ebdc7`；对账对象是 `bf92ff8e` 已交付的 `ecommerce_growth_dispatch` HTTP Router。本切片不改变其运行语义。
- Red：`scripts/generate_domain_aggregates.py --check` 报聚合文件 stale；登记 Router 后，清单守卫先以 `548 != 549`、`4544 != 4545` 失败，随后以旧 route inventory hash、旧 OpenAPI path 数失败。
- Green：`domain_manifest.json` 末尾新增连续 `order=548`，未重排原 548 项；生成文件与 `bf92ff8e` 内容一致，`--check` 显示 `OK router aggregate matches 549 manifest entries`。
- 守卫同步为 549 个唯一 Router、workshop 118 项、4545 条运行时路由、2744 个 OpenAPI paths，并明确要求 `/v1/ecommerce-growth/operations/{operation_id}` 存在；完整运行时 inventory SHA256 为 `ccfa3d9d7aaa61ee6deccd2a81e9cc11edf76c7d2c862bceb589e95e603d2a3b`。
- `test_domain_router_manifest.py` 与 `test_ecommerce_growth_dispatch_http.py` 合计 **14 passed, 7 warnings, 2 subtests passed in 17.48s**；没有放宽重复路由、关键路径、迁移失败传播或 bootstrap 守卫。
- `verify_closure.py --phase ar2-1`：扫描1707、分类91、迁移57，`hashErrors`、正反向未分类依赖、跨层导入、动态引用错误均为空。只更新 `ar2-1` 精确哈希，`ar2-0` 冻结基线保持原值。
- `memory-validate` 为 `AOS-000571 / GREEN`，865 delivery receipts、2226 events、846 task receipts；未推进项目修订。`git diff --check` 通过。
- SHA256：`domain_manifest.json` `88b862a6d4553235cf7939c52619d158685acfe9435dfd8a4a842c3a7f8afa58`；`domain_aggregates.py` `aec9f083998f75d5f5cf73743e774dfef0bfddb5bb0ad5da8a818a6e97945d37`；测试 `0a7cff711c3446c3c2949c02f0367101df0722b3c096fa66ffef5cbf02cd339b`。
- 未访问真实源、Provider 或发布端点；不宣称 D3/D4/AR2-7D 整波完成，不改变230 L0挂起状态。
- 本地独立只读复核确认：只追加现有 Router、`ar2-0` 与 preHash 未改、registration-only 边界和精确守卫均保持，无阻断项；不代表外部 Prime PASS。
