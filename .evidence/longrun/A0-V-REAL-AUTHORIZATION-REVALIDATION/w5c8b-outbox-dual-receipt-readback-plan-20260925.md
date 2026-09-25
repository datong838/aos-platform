# W5c8b Outbox 双 Receipt 只读对账与 Coordinator fixture 复验计划

## 上位与目标

承接 231、A0-V fail-closed、W5c8a `5dd544cd`：自动歧义重领已在代码/隔离 PG 冻结，但真实环境未迁移/未重启。W5c7y 的 Coordinator PG 三例在 `analysis snapshot group differs from original source` 处红，不能直接借其声称 `complete_a0v_050` 结果未知的可恢复性。本波先定位该 fixture 是构造错误还是生产合同错误；只在隔离 PG 证明 ACK 已提交而调用方响应丢失时，原 attempt/token/两份 Receipt 能被只读独立回读，绝不重新调用 coordinator 或来源。若证据不足，如实保留 RED，拆后继最小修复。

## 文件级清单

- 复习 `services/aos-api/alembic/versions/a0v_050_data_requirement_outbox_completion.py`、`aos_api/data_requirement_outbox_store.py`、`ecommerce_analysis_snapshot_coordinator.py`、`ecommerce_product_event_analysis_service.py` 与 `pipeline_snapshot_group_locator.py`。
- 定位/最小测试改动：`services/aos-api/tests/extension_runtime/test_analysis_snapshot_coordinator_pg.py`、`test_analysis_snapshot_resume_chain_pg.py`；若只是 fixture 身份/控制引用漂移，仅修 fixture，不放宽生产校验。
- 新增或扩展隔离 PG 测试：先真实 `complete_a0v_050` 双 Receipt commit，再模拟调用方响应丢失；用 runtime SELECT 单独回读 `acked`、原 attempt/token、两份 Ref，负例排除错 token/错 attempt/错租户/单份 Ref；只读回读不得第二次调用 `complete` 或 coordinator。
- 不迁移真实 DB、不重启 8080，不修改真实 A0-V generation；证据与 docs CAS 只在专项确证后推进。

## 九步及停止条件

1. 复习当前 m1、authority、上位安全门、W5c8a 与现有 PG 红项。
2. 本方案提交，固定文件级范围和只读回读断言。
3. 诊断 fixture 原因并做最小修复；若生产校验发现真实缺陷，先补方案再改生产代码。
4. 跑原 Coordinator PG 红例与新 ACK 丢响应负例；只有精确双 Receipt 回读才算通过。
5. 跑受影响专项和近期 A0-V 短累计；历史长例不复算。
6. 内置浏览器只读 rev4/停用，队列不冲刷。
7. 方案/代码/SQL 双向复审，区分只读确认 ACK 与 unknown/claimed 的未恢复情形。
8. verification 落盘提交、AOS CAS、Prime 强投影回读；红项如实保留。
9. 自动进入 W5c8c：原 attempt 的独立冻结恢复设计/实现，不以第二次 coordinator 调用替代。

任何 unknown 提交边界不重发、不手工 `run_definition`；真实 closure 无全机拓扑/Fresh Owner/独立 plan-key 不执行；m1 单写不 push，商城源行不读、230 L0 挂起、dev-org 仅隔离 canary。
