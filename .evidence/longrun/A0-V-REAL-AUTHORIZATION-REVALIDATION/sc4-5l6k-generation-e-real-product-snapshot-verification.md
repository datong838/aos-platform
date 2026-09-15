# SC4-5l6k E 代真实商品快照验证

日期：2026-09-15  
基线：`a32213bb`  
范围：`org-org/dev-project` 的 P02 单次真实只读源调用、Ingress、Dataset、Receipt 与 checkpoint；不含 ProductEvent 成功结论。

## 结果

`scr-a5a23c835eb04a73` 于 `2026-09-15T12:23:55.589012Z` 成功结束，`executor_id=ec-live-v1`、`executor_stopped=true`、`durationMs=13407`、`rowsWritten=65`。执行器在调用前临时启用 `sch-p02-qyh-controlled-20260913-v1`，完成后在 `finally` 恢复 `enabled=false`；最终 Schedule 的 `last_run.id` 精确等于本次 Run。

该 Run 使用 E installation `1c08edfb-ec0d-4abb-a411-7b6ec0d6066a`、generation `ebaa620a-8831-4c2a-b971-788383f352f8` 的当前控制链。`pipeline_controlled_source_claim` 对本 Run 恰好 1 行，`call_ordinal=1`，不存在第二次源调用。

## 三阶段与哈希链

- `ecommerce_ingress_command`：1 行；65 objects、65 outputRows、0 links；`sourceId=niushop-qyh`；`sourceRevision=a84b6c79-8654-48f0-98c2-57d41b067b3d`。
- command 存储哈希与规范 JSON 重算均为 `e0bb5b2fa4e4158c74fbdfb86649081e99eece78b54732d1412fdbddd3153f20`。
- `ecommerce_ingress_derived_command`：1 行；0 条派生命令；`parentHash` 精确指向 command；存储哈希与重算均为 `52799dfe2e6545e3e1fef493bf35a876cf6e5ec790adcbd6b31810f7faad8cfd`。
- `ecommerce_ingress_dataset_receipt`：1 行；`parentHash`、`derivedHash` 精确指向前两阶段；存储哈希与重算均为 `4ade37e3fe598c18d3b2296528ab7f936053ef20a4cd1dcde7251d5170c94252`。
- Dataset `ri.aos.main.dataset.P02-product-qyh` 为 `READY`，Build `db-ingress-ae94a70abd3e5b674967e990ce51d996` 为 `success`，`completion.expected=65`、`projected=65`、`pending=0`。

## observation materialization 与幂等

命令使用幂等键 `P02-product-qyh:2026-09-15T12:23:48.655620+00:00:niushop:1:9`，声明 `expected_checkpoint_version=1`，下一游标为 observation 时间 `2026-09-15T12:23:48.655620Z` / `niushop:1:9`。

对应 `ecom_ingest_receipt` 仅有同一键的成功结果：`replayed=false`、`objects_written=57`、`objects_tombstoned=8`、`objects_ignored=0`、link 写入/清退/忽略均为 0、`checkpoint_version=2`。当前 checkpoint 精确为版本 2、同一 observation 时间与 external id。

当前 Product 投影合计 65 个唯一 external id、65 个不同 payload hash；57 个 active、8 个 soft-deleted。全部 `source_updated_at` 等于本次 observation 截止，因此已证明 Niushop 1.23 的 observation 版本能够在源 `modify_time` 不变化时安全推进同键快照，没有重现上一代同键内容冲突。

## 隔离与边界

`dev-org/dev-project` 在 `pipeline_controlled_source_claim`、command、derived、dataset、`ecom_ingest_receipt`、checkpoint、`ecom_object` 七类表中均为 0。执行没有商城写、发布、触达、投流、改价、库存或履约副作用。

主库当前 `ecommerce_investigation_schedule_policy_head` 和 `automation_schedule_binding` 在正租户均为 0；本 Run 对应的 ProductEvent origin、Occurrence 与 outbox 也均为 0。因此本证据只判定 `GENERATION_E_REAL_PRODUCT_SNAPSHOT_GREEN`，不能判定 ProductEvent/Case/分析链成功。

## 下一步

进入第 5/6 步：先以现有经营方案和当前 E 安装/来源权威生成真实 Case 与 ProductEvent 策略配置方案；使用正式 Case、Proposal/Approval、安装 Host port 和 event-control Receipt 完成配置与启用。不得直接插入策略、绑定、Occurrence 或 Case，不得手工调用 Worker 内部方法。
