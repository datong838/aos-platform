# SC4-5l6e6e 原初始化至完整快照统一续跑验证

日期：2026-09-15
基线：`d460879e295596813321ab02e73c7b30419e394d`（m1 / AOS-000573）

## 实现与边界

新增 `services/aos-api/tests/extension_runtime/test_analysis_snapshot_resume_chain_pg.py`，没有修改生产状态机。测试在每用例私有、完整迁移的 PostgreSQL 数据库中组合既有原 Owner：产品事件自然初始化 Case/BusinessInvestigationRun/Task/TaskRun/Checkpoint，原 `AnalysisDataRequirementPreparation` 建立 Pending DataRequirement，随后十二路源组由原 `PipelineSnapshotGroupCompletion` 完成对象、关系、条件清退与调度终态；再由原 Source/Query/Quality/Business Evidence、Brief/Bundle、SourceReadiness/Fulfillment 和 `_AnalysisSnapshotResumeSession` 提交统一 `AnalysisRuntimeReceipt`。

事务顺序按实际进程边界固定：初始分析、Pending Requirement 和 occurrence 接单先作为一个事务提交；十二路源 worker 使用独立连接完成；恢复事务从新 SERIALIZABLE 快照读取已完成结果。能力目录由独立控制面连接写入命名绑定，业务运行连接始终保持 `aos_runtime`，没有为测试增加表权限或临时 GRANT。

正向验证同一原 Run 从 `WAITING_DATA` 前进到 `PREPARING`，同一 TaskRun 从 `paused` 前进一版，十二个 Schedule 全部 succeeded/stopped，十二个对象 Receipt 加一个关系 Receipt 共 13 条，源读取仅一次；重建 Session 按原 unified Receipt 只读回放，不再读取源或重复推进状态。负向验证在恢复前撤销当前 Business Evidence，原 Run/TaskRun 保持不变且统一运行回执为零。

## Red、修正和新鲜验证

- 第一次完整组合进入 Source Evidence 时，旧 SERIALIZABLE 分析快照与十二路独立完成事务发生 `SerializationFailure: could not serialize access due to concurrent update`。修正测试编排为先提交原初始化/Pending/occurrence，再执行独立源 worker，并从新事务读取；没有降低数据库隔离级别或绕过当前性锁。
- 组合推进到 Query Binding 时，测试曾用运行身份直接写 `aip_capability_binding`，数据库以 `InsufficientPrivilege` 正确拒绝。修正为独立控制面连接建立命名能力绑定；运行身份只读取和使用当前绑定。
- 正向专项：`1 passed, 7 warnings in 98.32s`。
- 撤销拒绝专项：`1 passed, 7 warnings in 81.08s`。
- 最终整文件：`2 passed, 7 warnings in 168.44s`。
- Python 编译与 `git diff --check` 通过。
- `verify_closure.py --phase ar2-7`：`1952 scanned / 192 classified / 93 migrated`，`hashErrors`、正向/反向未分类依赖、跨层导入与动态引用错误全部为空。
- Prime/shared-memory：八个投影中七个强一致投影 `CURRENT`，Codex eventual 投影保持 `PENDING_ASYNC`；`memoryctl validate` 为 GREEN，AOS-000573，1201 Delivery / 1183 Task / 2900 Event。

上述七项 warning 均为既有 Pydantic 字段遮蔽和 TestClient 依赖弃用提示，本波没有新增 warning。

## 限制与下一波

本波证明原内部组成能够在完整结构和真实 PostgreSQL 权限下贯通，不证明当前主运行库或栖月汇真实经营首链已经贯通。商城源读取、安装资产/签名和 Provider 健康仍为明确 named fixture；没有升级主库、发布或切换安装、读取真实商城、调用模型、创建主环境业务任务或产生外部副作用。用户原 `overall-progress-20260913.md`、`package.json`、`package-lock.json` 继续保护；不 push，230 L0 挂起。

下一波 SC4-5l6f 从原 `DataRequirement` Outbox 开始做自然消费接线：事件初始化产生 Pending 后，不由开发者直接调用 `prepare/complete/resume`，固定消费者应凭原 Outbox/Receipt 路由十二源组、完成交付并触发统一续跑；覆盖重启、重复投递、未知结果、撤权和租户隔离。完成后再进入主库候选升级、真实签名安装与栖月汇真实首链/八工作台/连续观察。
