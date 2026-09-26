# W5cay｜内容 TaskRef 创建引用与运行版本分离（施工前）

## 上位复习与最早缺口

- 231-5 §1、§4 与 231-9 §2 要求 exact 方法评审后自动交接内部内容任务，真实能力生成可读产物，人工评审后系统自动续跑；工程师不能手补 TaskRun 引用。W5cax 已在反馈入口要求内容 TaskRun `succeeded`、Task `completed`，但不制造终态。
- 当前 `ReviewAdvanceHostService._review_lineage` 只在原事务创建 `aip_task` 与 v2 Brief，其正式 Review Receipt 明示 `taskRunCreatedCount=0`。`AipTaskStore.create_plan/approve_plan/create_run/start_run/complete_run` 是公共 Owner，但需要合法批准 Plan、Run 和所有 Step 终态；`ContentGenerateHostService` 的 v2 出队与 `CurrentContentContextReader` 又依赖同 Task 的 AgentRun→TaskRun/容量预约。尚未发现 Handoff Receipt 到该公共 Owner 的自然桥，真实系统不能由操作员补接口引用，也不能在不改回执合同的情况下把 Run 偷塞回 Handoff 原事务。
- 另一个更早的兼容缺口：`ContentGenerateHostService._task_brief` 将 Handoff 的 TaskRef 固定为创建修订 1，而 `ContentReviewHostService._task_brief_authority` 却把当前可变 `aip_task.version` 当成同一个 Ref 的 revision。合法 Plan/Run 推进后版本必然增加，人工内容评审会误拒绝。先 RED 复现并修成“创建 Ref 稳定、当前状态另行核验”，不能放宽 payload/hash/Brief 精确闭包。

## 文件级清单与顺序

1. 已只读追踪 Handoff→内容 Plan/Run→AgentRun/容量→`content.generate`→Artifact→Review 的现有入口：Handoff 的正式 Receipt 明示零 TaskRun，公共 AIP Owner 有 Plan/Run/Step 状态机，但缺持久 Review Receipt 到内容 Plan/Run 的自然桥；不能用原回执冒充运行完成。
2. 本波先 RED：合法 Task.version>1 仍应按 Handoff 原创建 Ref 通过内容评审的 Task/Brief 读回，篡改 payload/hash 仍拒绝。修改 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_authority_feedback.py`，最小修复 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`，保留 Brief/source exact 闭包。本波不动生产库、不人工建 Run。
3. W5caz 紧接着为 v2 Review Receipt→独立幂等 Plan/Run 自然启动另出计划/RED，候选文件 `services/aos-api/aos_api/ecommerce_content_taskrun_owner.py` 及同名测试。必须由持久 Review Receipt/current Dispatch/安装驱动，复用原 AIP Owner，不新造 TaskRun enum、不松散多事务制造孤儿 Run。未经正式可追溯审批不得自动 approve 内容 Plan。
4. 后续再接原 `ContentResultConsumer`、Provider 双 Receipt/用量/预算/Artifact 独立回读和公共 Step/Run 正式完成；UNKNOWN/失败只冻结并对账，不假装首链闭环。

## 验证与停止

- RED→最小改动→专项/累计/隔离 PG→浏览器或无可信实例说明→方案/代码一致性→verification→m1 commit→D-waves/AOS/Prime 记忆→下一波。
- 无当前真实安装/费用/Provider 权威则不开真实 Worker、不迁移现场、不发外呼；旧 12 Run 后置，230 L0 挂起，dev-org 零 canary。未经正式审批不得自动 approve 内容 Plan；若现有批准 GrowthPlan 不足以作为公共 AIP Plan 授权，先停在设计/证据，不能偷换为自动审批。
