# W5c8g｜unknown 原源组无行锁历史读取验证（2026-09-25 CST）

## 结论与边界

方案 `m1@3715ee77`、修订 `m1@bbe6737e` 先于代码；实现 `m1@c4175744`。本波仅交付**未接 Worker 的只读诊断证据**：同一 `transaction_read_only=on` 快照中，W5c8d 原 attempt 双 Receipt 与原 PREPARING Receipt、精确 Requirement/Run/Case/Occurrence、保存的源组和唯一源 Run 成员交叉核对。无 `reconcile_completed` 授权、无可执行 route、无源调用/Outbox 写入。旧 `read_unknown` 默认 `FOR SHARE OF o,a`、当前 head 检查和 Worker 路由未改。

## 九步证据

1. 复习 231、A0-V fail-closed、W5c8d/e/f、真实 gate、旧 SQL。W5c8f 的只读事务 `FOR SHARE` 故障是本波起点。
2. 文件级计划及显式无锁/旧默认分流先提交：`3715ee77`、`bbe6737e`。
3. PG 测试先 RED（新模块不存在），后最小实现：`ecommerce_growth_runtime_adapters.py` 仅显式 `read_only=True` 去行锁；`ecommerce_analysis_data_requirement_route.py` 增加诊断型历史读取；原 attempt 解析证据扩字段；新增同快照组合 reader，全部位于 `services/aos-api/aos_api/`，测试位于 `services/aos-api/tests/extension_runtime/`。
4. 隔离 PG 专项最终 `1 passed, 7 warnings in 221.17s`。正例原链一次源调用；错误 attempt、`dev-org/dev-project`、可写连接、错误源 Run/Occurrence 注入均拒绝；注入 `get_current` 抛错后历史诊断仍成功，证明不依赖当前 head。测试后的 `aos_test_*` 库数为 0。
5. 近期短累计 `107 passed, 7 warnings in 25.01s`；五文件 `py_compile`、`git diff --check` 通过。最终仅格式调整后复做静态检查，未改语义。
6. 内置浏览器只读核对：2026-09-25 23:36:54 CST，A0-V Canonical 数据组 `rev4`、`已停用`；有待同步写操作 1，未按冲刷按钮。验收用本地临时 Vite 已关闭。
7. 方案/代码复审：新 `HistoricalSourceGroupEvidence` 与旧 `AnalysisDataRequirementRoute` 类型分离；新 reader 查读只读状态且复用同一连接；无现网接线、无真实库迁移、无 8080 重启。源组唯一成员/manifest 依赖既有 `PipelineSnapshotGroupLocator` 校验，**本波未单独注入多组或持久 manifest 篡改负例**；W5c8d PG 原文件未增独立断言，新增字段由本波完整链间接覆盖。这些不是实网恢复许可。
8. 真实 closure gate 再读：`automaticAction=false`、`closureAuthorized=false`、`topologyComplete=false`、`runningOriginalRuns=12`、`stalledClosureReceipts=0`；缺全机 Host 拓扑、Fresh 单事务 Owner、独立真实 closure plan/key。AOS authority/Prime 与上下文按独立提交回读，不把本波 GREEN 记为真实运行 GREEN。
9. 下一波 W5c8h 应先出方案，评估**同一写事务** Host fence + 原双 Receipt/源组谓词的受控 `unknown` 对账；过期 `claimed` 另立状态迁移门。**用户已要求本波后暂停以重启电脑，故本次不启动 W5c8h。**

## 永久停线

未知结果不重发、不手工 `run_definition`；230 L0 仍挂起，商城源行不读，`dev-org` 仅零 canary，m1 单写不 push，不动其他分支。原 12 Run 未收束，rev4 disable 不等于正式退休。真实 A0-V 仍停在 no authority。
