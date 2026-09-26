# W5cay｜内容 TaskRun 自然 Owner（施工前）

## 上位复习与最早缺口

- 231-5 §1、§4 与 231-9 §2 要求 exact 方法评审后自动交接内部内容任务，真实能力生成可读产物，人工评审后系统自动续跑；工程师不能手补 TaskRun 引用。W5cax 已在反馈入口要求内容 TaskRun `succeeded`、Task `completed`，但不制造终态。
- 当前 `ReviewAdvanceHostService._review_lineage` 只在原事务创建 `aip_task` 与 v2 Brief，其正式 Review Receipt 明示 `taskRunCreatedCount=0`。`AipTaskStore.create_plan/approve_plan/create_run/start_run/complete_run` 是公共 Owner，但需要合法批准 Plan、Run 和所有 Step 终态；`ContentGenerateHostService` 的 v2 出队与 `CurrentContentContextReader` 又依赖同 Task 的 AgentRun→TaskRun/容量预约。尚未发现 Handoff Receipt 到该公共 Owner 的自然桥，真实系统不能由操作员补接口引用，也不能在不改回执合同的情况下把 Run 偷塞回 Handoff 原事务。

## 文件级清单与顺序

1. 先只读追踪 Handoff→内容 Plan/Run→AgentRun/容量→`content.generate`→Artifact→Review 的所有现有生产入口与状态转移，核对是否已有其它自然 Owner；把调用/Receipt/提交边界列在本波验证，不读商城源和旧 12 Run。
2. 先写 RED：已批准 GrowthPlan 的 v2 Review Receipt 必须能以独立幂等启动命令自然取得同租户、同 Brief/Task、唯一可回读的内容 Plan/Run；没有当前审批、相同键不同内容、旧安装、跨租户与未知提交不得产生第二 Run。测试优先新建 `services/aos-api/tests/extension_runtime/test_ecommerce_content_taskrun_owner.py` 与专用 PG 测试，原 Handoff 0 Run 合同保持不变。
3. 最小实现预计新增 `services/aos-api/aos_api/ecommerce_content_taskrun_owner.py`，由持久 Review Receipt/current Dispatch/安装筛选驱动，优先复用 `AipTaskStore`/原 AIP 权威和原状态机，不新造 TaskRun enum、不单独手写终态。Plan/Run 创建应有受限 transaction-bound Owner 接口或有明确 Receipt-first Saga；不能用松散多事务制造孤儿 Run，也不能以原 Review Receipt 假称 Run 已创建。
4. 生成结果后检查原 `ContentResultConsumer` 与公共 Step/Run 完成条件：只有 Provider 双 Receipt、用量/预算/Artifact 独立回读和人工 Review exact ACCEPT 后，才能由合法 Owner 推进相应 Step/Run；UNKNOWN/失败只冻结并只读对账。若这需要另一独立提交边界，则本波先完成自然创建 Owner，下一波单独做正式终态，不假装全闭环。

## 验证与停止

- RED→最小改动→专项/累计/隔离 PG→浏览器或无可信实例说明→方案/代码一致性→verification→m1 commit→D-waves/AOS/Prime 记忆→下一波。
- 无当前真实安装/费用/Provider 权威则不开真实 Worker、不迁移现场、不发外呼；旧 12 Run 后置，230 L0 挂起，dev-org 零 canary。未经正式审批不得自动 approve 内容 Plan；若现有批准 GrowthPlan 不足以作为公共 AIP Plan 授权，先停在设计/证据，不能偷换为自动审批。
