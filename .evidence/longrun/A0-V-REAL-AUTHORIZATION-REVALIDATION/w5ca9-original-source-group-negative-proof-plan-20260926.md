# W5ca9｜原始源组多组/持久 manifest 篡改隔离负例方案

## 上位与授权边界

复习 231 A0-V→A1、230 L0 挂起、W5c8g 原双 Receipt+源组只读诊断、`a0v_045` 的不可变/唯一索引、`PipelineSnapshotGroupLocator` 的同快照校验，以及 W5ca5 原组 closure no-authority。AOS-000723 明确保留 `W5C8G_SOURCE_GROUP_MULTI_GROUP_AND_PERSISTED_MANIFEST_TAMPER_NEGATIVE_CASES_NOT_SEPARATELY_TESTED`。仅在一次性隔离 PG synthetic fixture 补测试，不连接真库或商城源。

## 文件级最小清单

- 只读：`services/aos-api/alembic/versions/a0v_045_snapshot_group_journal.py`、`services/aos-api/aos_api/pipeline_snapshot_group_locator.py`、`services/aos-api/tests/extension_runtime/test_a0v_w5c8g_unknown_source_group_read_only_pg.py` 与 W5c8g verification。
- 仅修改上述 `test_a0v_w5c8g_unknown_source_group_read_only_pg.py`：在原完整 synthetic 链已构建、unknown 只读对账已成功后，尝试将相同 `run_id` 插入第二组，要求数据库唯一约束拒绝且原读不漂移；再尝试 UPDATE 原保存 `pipeline_snapshot_group_input.manifest`，要求不可变触发器拒绝且原读不漂移。每个失败事务须 rollback，不能继续带错误状态读。若真实约束未拦截，先停并另立生产修复方案，不在测试波顺手改迁移。
- 用项目 `.venv` 和 `pytest --noconftest` 运行单一隔离 PG 专项；需要 `aos_test_*` 一次性 DB，不使用共享主库；运行前后确认真库/18181 不变、测试 DB 0。再跑短无 PG 邻接回归与静态检查。
- 本目录 audit/verification、D-waves、AOS/Prime CAS 和精确 m1 提交。

## 九步与退出

1. 上位复习；2. 本计划先提交；3. 测试 RED/约束行为定位；4. 最小测试变更；5. 专项/累计/清理；6. 8080 离线，18181 文档只读，浏览器业务验收不适用；7. 方案/代码一致性和误授权风险复审；8. verification、上下文/Prime、提交；9. 自动下一波。

只证明**隔离 PG** 对持久歧义/篡改的拒绝，不证明原组行语义、ACK/closure、全机 Fleet 或真库迁移。unknown 不重发、不手工 run_definition；230 L0/商城源/dev-org 零 canary/m1 单写不 push 不变。
