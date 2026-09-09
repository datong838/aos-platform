# AR2-7D D5A 整组切换 prepare 权威施工方案

日期：2026-09-09
状态：施工前冻结；仅建立 prepare 权威，不执行 dispatch cutover

## 1. 依据与现场差距

- `closure-manifest.md` §5 要求九项 operation 以同一 `cutover_group_id` 整组 CAS，切换前记录旧入口 checkpoint、旧/新代次、policy/approval、occurrence watermark 和未决 target Receipt。
- `231-6-串行施工包与双目标联合验收实施方案.md` 的 AR2-7D-D5 要求 `ecommerce_growth_cutover.py`、tenant-scoped cutover operation、不可变事件和 Receipt；现场 `ar2_005` 只有 host invocation Receipt，因此不回改历史迁移，在线性头 `ar2_012` 后新增 `ar2_013`。
- 当前 Canonical Router 对 legacy 与 extension 均要求 `operation_fence=false`。prepare 不得提前 fence legacy，也不得改写九行 dispatch；唯一切换点留给后续 commit。

## 2. 本切片合同

1. 新增 `extension_dispatch_cutover_operation`，以租户、cutover operation UUID 为主键，以 `kind=activate`、`status=prepared` 冻结：稳定九项 operation 顺序、同一旧 group revision、逐行旧 snapshot、目标 installation/generation/epoch/runtime revision、新 group revision、checkpoint、occurrence watermark、pending target Receipt refs、policyRef、approvalRef、request hash、actor 与数据库时间。
2. 新增不可变 `extension_dispatch_cutover_event` 和 `extension_dispatch_cutover_receipt`。prepare 成功时在一个 serializable 事务内写 operation、`CUTOVER_PREPARED` 事件和 prepare Receipt；同 idempotency key/同 request hash 只回读，hash 漂移冲突。
3. `EcommerceGrowthCutoverStore.prepare_activation` 只接受受信 `TenantScope` 与严格 DTO。事务顺序固定为 cutover group advisory lock → operationId 字典序读取 dispatch 行 → target installation advisory lock → generation advisory lock与binding读取 → approval/proposal。`aos_runtime` 对 dispatch 继续仅有 SELECT，不因 prepare 扩大成任意更新权；后续 commit 通过专用整组 CAS。九行必须精确等于固定 operation 集、全为同一 group revision、当前 handler 为 legacy 且未 fence；目标 runtime binding 的外键已锚定 Installation，并且必须是同一 installation/generation、精确 revision/epoch、`desired_state=enabled`、`observed_state=ready`、enabled 且未 fence。
4. approvalRef 必须精确回读当前未过期、decision=approved 的 `ActionApprovalEvent`，摘要匹配；其 Proposal 必须仍为 approved、`action_type_id=ecommerce_growth_cutover`、proposal/action binding hash 一致，并在 payload 中精确绑定 cutoverGroupId、expectedGroupRevision、targetInstallationId、targetGeneration、targetExecutionEpoch、targetRuntimeRevision 与固定九项 operations。
5. checkpoint 为严格 JSON object；policyRef 为严格 exact ref；pendingTargetReceiptRefs 为严格 exact ref 数组且去重；watermark 可空。它们只由 prepare 请求和 Receipt 冻结，不宣称 Store 已枚举全部运行事实；commit 必须重新查询 occurrence、attempt 与 target authority。旧/新 dispatch 快照只能由 Store 从数据库生成，调用方不能上传。
6. 三表 FORCE RLS、撤销 PUBLIC；普通 `aos_runtime` 无写权限，只有专用、非特权 `aos_extension_maintainer` 通道可准备，并且 operation 只开放 status/updated_at 列更新。历史事件与 Receipt 禁止 UPDATE/DELETE；非空迁移禁止 downgrade。

## 3. 本切片不做

- 不暂停 occurrence claim，不 fence 当前 legacy，不修改 dispatch 或 runtime binding，不执行九行 CAS。
- 不调用领域 handler、Provider、真实数据源，不产生费用、内容、外部发布或真实租户写入。
- commit、UNKNOWN/drain 门、rollback 的 9/9→0/9 验证在 D5B/D5C 串行完成；prepare Receipt 不代表切换成功或业务启用。

## 4. 文件与验证

- 新增 `services/aos-api/alembic/versions/ar2_013_ecommerce_growth_cutover.py`。
- 新增 `services/aos-api/aos_api/ecommerce_growth_cutover.py`。
- 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_growth_cutover_pg.py`。
- 更新 `closure-manifest.md` 接续闭包登记。
- 专项覆盖 prepare 成功、精确重放、hash 漂移、九项缺失/多余/顺序、group/revision、legacy fence、runtime 状态、审批漂移、跨租户 RLS、事务回滚、不可变历史、dispatch 零修改和非空 downgrade。
- 专项通过后运行受影响 runtime/Router 邻接回归、阶段 closure 与 memory validate，再形成 verification 文档和精确提交。
