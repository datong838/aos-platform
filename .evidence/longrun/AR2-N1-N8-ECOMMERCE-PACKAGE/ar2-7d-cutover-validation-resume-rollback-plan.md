# AR2-7D D5C 切换验证、恢复与失败回滚施工方案

日期：2026-09-09
状态：施工前冻结；仅在隔离 PostgreSQL 验证，不执行真实租户 cutover

## 1. 已落地基线与本阶段边界

- D5B commit 后九项 dispatch 已是同一 extension generation/epoch/group revision，但 claim gate 仍 paused，target runtime 为 `desired=enabled / observed=ready / enabled=false / operation_fence=true / revision=N+1`。因此当前状态可检查、不可执行业务。
- D5C 成功路径只做确定性结构验证：exact commit Receipt、9/9 dispatch、新 runtime fence、claim gate、当前 Approval/Proposal/Draft 与无在途事实全部一致后，保存不可变 validate Receipt；不调用 Provider、真实源或领域 handler。
- validate Receipt 不是放量。resume 必须引用 exact validate Receipt，并由数据库函数在同一事务内恢复 target runtime 与打开 claim gate，随后 9/9 Router 数据库读回才形成 `resumed` Receipt。
- 本阶段失败回滚只处理“D5B commit 后、D5C resume 前”的验证失败窗口。该窗口 runtime/gate 已关闭，没有新 extension 执行；D6 负责 resume 后的停用、卸载和生命周期回滚，不能复用本阶段捷径。

## 2. 成功路径合同

1. 线性迁移 `ar2_015_ecommerce_growth_cutover_finalize.py` 扩展 cutover event/Receipt/status 枚举，增加 `validate`、`resume` 及对应不可变历史约束。
2. `validate_activation` 只接受 exact commit Receipt ref。它锁定 activation operation、cutover group、target runtime 和当前审批三表，核对 commit authority/hash/event、九项 `newDispatchSnapshot`、paused gate、disabled/fenced revision N+1、零 claimed/running 事实，再写 `CUTOVER_VALIDATED` 与 validate Receipt。
3. `resume_activation` 只接受 exact validate Receipt ref。固定 SECURITY DEFINER 函数重验上述数据库状态，将 runtime 原子推进为 enabled/unfenced revision N+2，并将 gate 推进为 `claim_paused=false/revision+1`；operation 变为 `resumed`。Python 同事务读回九项、runtime 与 gate，写 `CUTOVER_RESUMED` 和 resume Receipt。
4. deferred history guard 要求 `validated` 状态必须有 validate Receipt、`resumed` 状态必须有 resume Receipt；直接调用函数缺 Receipt 时事务提交失败，所有入口变化一并回滚。

## 3. 验证失败回滚合同

1. 接续线性迁移 `ar2_016_ecommerce_growth_cutover_rollback.py`；不回改已验证的 `ar2_015`。`prepare_validation_rollback` 接受新的 rollback operation/idempotency、exact activation commit Receipt、失败原因和新的 exact `ActionApprovalEvent`。审批 action type 固定为 `ecommerce_growth_cutover_rollback`，payload 必须绑定 activation operation/commit Receipt、group revision、九项 operationId 与目标 runtime identity。
2. 数据库函数要求 activation 仍为 `committed` 或 `validated`、gate paused、runtime disabled/fenced、九项仍为 exact extension snapshot；它先把九项 dispatch 整组 CAS 为 fenced extension snapshot（revision/group revision 各 +1），把 gate Owner 转给 rollback operation，并写 `CUTOVER_FENCED` 与 fence Receipt。任一行漂移为 0/9 回滚。
3. `commit_validation_rollback` 再次枚举 occurrence/dispatch/runtime attempt；claimed/running 阻断，UNKNOWN 只进入 reconcile-only 列表。排空后同事务写 drain Receipt，并把九项从 exact fenced snapshot 整组 CAS 回 activation prepare 的 legacy snapshot身份，使用新的 revision/group revision；删除当前 gate，runtime 保持 disabled/fenced，rollback operation 变为 `rolled_back`，写 rollback Receipt。
4. rollback 失败或 CAS 冲突保持 runtime/gate/dispatch fence，operation 转人工前不盲重试；任何已知或 UNKNOWN attempt 只按原 Receipt 对账，不调用 handler。

## 4. 文件与验证

- 新增 `services/aos-api/alembic/versions/ar2_015_ecommerce_growth_cutover_finalize.py` 与接续 `ar2_016_ecommerce_growth_cutover_rollback.py`，先封存成功出口，再实现失败出口。
- 修改 `services/aos-api/aos_api/ecommerce_growth_cutover.py`，新增 validate/resume 与 validation-window rollback DTO、Store 方法和严格 readback。
- 扩展 `services/aos-api/tests/extension_runtime/test_ecommerce_growth_cutover_pg.py`，覆盖成功恢复、直接函数回滚、审批/Receipt/九行/runtime/gate 漂移、并发 claim/attempt、9/9→0/9 回滚、UNKNOWN 保留、租户与非特权角色。
- 更新 closure manifest 与验证文档；运行 D5 聚焦 PostgreSQL、Router/Host/occurrence 邻接、完整 extension_runtime、Alembic 单头、closure、memory、compile 和 diff check。
- 相同阶段失败两次先定位根因；不改用共享库，不执行真实租户、Provider、生产迁移、发布或 push，230 L0 继续挂起。
