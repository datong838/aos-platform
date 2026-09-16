# SC4-5L6Z：旧活动 Run 对账与 P 正式退役方案

日期：2026-09-17

## 起点

Y 已证明真实 Cron `scr-4eda5462575a4740` 自然写入 65 行并产生 65 个 P occurrence，
但当前 Case/analysisType 的唯一活动槽仍指向旧 Run
`analysis-e5b19a5fe290ce1bf60d5038cb1d6cf6`。P 已因受控停机成为
revision7/epoch4、disabled/fenced/unknown，三资源 released；Policy11 binding1 仍 enabled，
十路仍为 P epoch3/group49，五个 attempt unknown、60 个 occurrence pending，Host stopped。

## 固定顺序

1. 只读枚举旧 Run 关联的 Run state、Task、TaskRun、Plan、Checkpoint、DataRequirement、
   Fulfillment、分析统一 Receipt、Outbox、occurrence 与 Case 版本；同时证明 P 五个 unknown
   没有 target Receipt 或新 Run。禁止用表存在推断业务完成。
2. 根据不可变 Receipt 只选一个分支：若旧 Run 有合法 pending/paused 续跑入口，则续跑旧
   Run；若已不可恢复，则使用原 Run 生命周期正式终止并释放 active slot。禁止 DELETE、
   手工 UPDATE 或绕过 BIW4-003。
3. 设计 P 正式退役顺序。必须保留 unknown attempts，使用既有 lifecycle fence/detach Receipt
   或先形成受控 fence 再走 UnacceptedAnalysisClosure；不得直接 disable binding、改 occurrence
   installation/generation 或复活 released P。
4. 五个 unknown 只有在 fence/detach Receipt 和“零 target Receipt、零对应 Run”同时成立时
   才能 closed_unaccepted；60 个 pending 必须按同一正式退休规则进入可审计终态，不能遗留为
   永久可执行任务。
5. 修复 `meta_schedule.last_run` 在 disable PATCH 后回退到旧 manual 投影的问题：不可变
   `meta_schedule_run` 与 ingress 是权威，PATCH 只能改 enabled，不得覆盖更新期间产生的新
   last_run。先复现并写迁移/服务最小修复方案，不能用脚本回填。
6. P 全部收口且旧 active Run 分支完成后，才允许创建干净 Q、登记 successor、切流并恢复
   Host。Q 初始保持 event binding disabled；先验证没有 active overlap，再开启下一短窗口。

## 停止条件

任一 unknown 存在 target Receipt、旧 Run 有未知提交、active slot 与 Run/Task 不一致、P 路由
或 binding 漂移、canary 非零，即停止写操作并只读核对。不得为赶整点重开 source，不得把
P occurrence 改绑给 Q，不得把测试绿色当成真实 Run 终态。

## 退出条件

- 旧 active Run 以正式续跑或正式终止二选一完成，Receipt 与 active slot 一致；
- P 的 65 个 occurrence 全部有可审计终态，Policy11 不可执行，P 正式 detached/uninstalled；
- schedule 投影不再因 PATCH 回退；
- Q（若需要）在 source disabled 下成为唯一 ready live target；
- 定向/累计测试、AR2 闭包、租户隔离、零 canary 和证据文档通过。

## 第 1 步只读结论与方案收敛

旧 Run 不是无事实的僵尸，但其当前 DataRequirement 也没有合法续跑入口。Outbox
`data-requirement-outbox-eb2ca2b8c1864f87b9a5a6490463dfb3` 已在创建后约 45 毫秒被
`analysis-data-requirement` 领取，并正式进入 `failed/CURRENT_ROUTE_REJECTED`；没有
Fulfillment、completion refs 或未知提交。原源 Run `scr-bddff0a74c2a4365` 有成功的 65 行
Store、SourceClaim 与已接受 occurrence，却没有 `pipeline_snapshot_group_member`、group claim
或 group input。DataRequirement route 必须以完整 group input 证明同一截止时点，不能用单路
P02 的成功 Run 补造十二源证据。因此本波第 2 项固定选择“正式终止旧 Run”，不得重领 failed
Outbox、补写旧 group 或把过期 Requirement 当作可恢复输入。

编码前的最小修复用于阻止同类 Run 再产生：

1. 修改 `services/aos-api/aos_api/ecommerce_product_event_discovery.py`，事件发现和已领取
   occurrence 的原路由回读都必须存在同租户、同 Run 的 snapshot group member、group claim
   与 group input；单路成功 schedule 继续保留为数据事实，但不得进入分析 occurrence。
2. 修改 `services/aos-api/aos_api/ecommerce_product_event_analysis_service.py`，移除以 occurrence
   创建时钟替代 source group 截止时钟的 legacy 分支；已存在 occurrence 也必须精确绑定原
   group actor、control/run pair 和 input clock，形成纵深防御。
3. 修改 `services/aos-api/tests/extension_runtime/test_product_event_discovery_pg.py`、
   `test_product_event_analysis_source_clock_pg.py` 及受影响的组合夹具：先写失败用例证明孤立
   P02 Run 不被发现、不生成 Run；再证明完整 group 路径保持原行为、租户隔离和 current
   authority 不变。若受影响回归显示普通内容事件依赖 legacy 路径，则停止并拆分分析专用发现
   合同，不扩大本修复。

该修复只封住新的错误入口，不处置当前旧 Run/P。代码与测试通过后，使用已有
`DataRequirementStore.reject`、`BusinessInvestigationRunStore.transition_control(CANCELLED)`
及相应 Receipt 顺序正式驳回过期 Requirement、取消旧 Run并释放 active slot；不得直接写表。

首次正式 reject 在任何数据库写入前暴露终态合同缺口：`DataRequirementRevisionRecord` 对全部
状态统一要求 `expiresAt > createdAt`，所以 Requirement 一旦真实过期，任何带新 `createdAt`
的 rejected/cancelled/unknown revision 都无法形成。最小修复追加修改
`services/aos-api/aos_api/data_requirement_contracts.py` 与
`services/aos-api/tests/test_data_requirement_store.py`：requested/accepted/planned 仍必须在创建时
有效；fulfilled 继续由 Fulfillment 路径约束；只有 rejected/cancelled/unknown 可保留原业务
有效期且仍要求 aware 时间、不可改变原 `expiresAt`。增加“过期 requested 不可新建、过期
requested 可正式 reject、终态不得改 expiresAt”测试。原 HTTP profile 对写路由返回确定性 405，
未进入 handler；保存 405 与零 Receipt 证据后，以同一冻结 intent/idempotency key 调用相同
application/store 权威，不生成第二次业务意图。

终态合同修复后，同一 intent 的首次 application 执行已成功形成 Requirement r2 rejected，随后
暴露原 `confirm_requirement` Saga 将 accept/reject 都错误复用 `RunStore.request_data`：数据库
正确拒绝既有 WAITING_DATA 再次进入 WAITING_DATA，故没有 Run v3 写入。补充最小 Saga 修复：
修改 `ecommerce_business_investigation_data_command.py` 使 reject 在读回/写入 Requirement 终态
Receipt 后调用既有 `RunStore.transition_control(CANCELLED)`，释放 active slot；accept 分支保持
原行为。本波同步修改其单元测试，覆盖 reject 半提交后同 key 重入只补 Run CANCELLED、不新增
Requirement revision。当前真实状态正好是该可恢复中间态，继续使用原 key。

Saga 重入继续被数据库约束挡在写入前：原 `ecommerce_investigation_run_control_biw4_006`
把 authority JSON 更新为 PREPARING/CANCELLED，却遗漏清空 head 的物理
`pending_requirement_ref`/`uncertain_command`，违反其自身状态约束。新增向前迁移
`services/aos-api/alembic/versions/a0v_075_run_control_pending_clear.py`，只以 exact function
definition 片段替换 UPDATE，保留原权限、Receipt、事件与 active-slot 语义；新增
`services/aos-api/tests/extension_runtime/test_a0v_run_control_pending_clear_pg.py`，从真实
PREPARING → WAITING_DATA → CANCELLED 验证 JSON/物理列一致、slot 释放、重放不新增事件。
既有 analysis service 正向夹具同步提供显式的单成员 snapshot group；无 group 用例继续单独
验证拒绝，避免以旧夹具的隐式单源假设稀释新的生产准入条件。
迁移先在隔离库通过，再升级 main；失败不得直接改 head。
main 升级使用 `scripts/a0v_z_main_run_control_migration.py` 两阶段执行：`prepare` 冻结 m1、
`a0v_074` 基线、单步 revision、迁移哈希、目标函数哈希及相关 Run/Requirement 表指纹；`apply`
在 advisory lock 内复核同一现场后运行 Alembic，仅接受 `a0v_075`，并要求业务表指纹完全不变、
函数精确包含 pending/uncertain 清空。两阶段私有证据均以 0600 新建，不覆盖既有结果。

Run v3 正式取消后只读复核发现，其编译产生的 canonical AIP Task/TaskRun 仍是
`paused`（Task v5、TaskRun v3）。领域 Run control 按边界不直接修改 AIP authority，但本波
“正式终止”不能遗留可恢复的暂停执行。于是追加一个独立、可重放的内部收口步骤：在确认领域
Run 已 `CANCELLED`、active slot 为零、Requirement r2 已 rejected 后，使用既有
`AipTaskStore.cancel_run` 以精确双版本和新幂等键将对应 Task/TaskRun 一起置为 cancelled，
保留 `run.control` Evidence；不复用领域 Receipt，不读取外部源，也不授权任何外部动作。
