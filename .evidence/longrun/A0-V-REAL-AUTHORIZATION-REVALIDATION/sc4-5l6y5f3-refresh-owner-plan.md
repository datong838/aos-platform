# Y5f-F3 同代次配置接续原子 Owner 方案

日期：2026-09-16

基线：m1 `c1d37652`

Task Receipt：`SC4-5L6Y5F3-REFRESH-OWNER-20260916`

## 目标与边界

在配置与启用操作已经由原 Extension Runtime 正式完成后，以一个新的、独立审批的内部控制动作，把九路电商 dispatch 从同一 installation/generation 的旧 runtime revision / execution epoch 原子切到新 revision / epoch，并写入 F2 不可变 Receipt。任一权限、审批、配置证据、启用证据、当前 dispatch、前驱 Receipt 或租户条件漂移，整个事务回滚。

本波只在隔离 PostgreSQL 验证，不迁移主库、不发布策略、不创建真实审批、不启用 Schedule、不读取商城源、不恢复业务 Run。F4 才做 clone、主库部署和真实接续。本波不触碰 230 L0。

## 方案复习结论

1. `commit_configuration` 将 binding 围栏、提交新 configuration，revision 连续增长；`commit_enabled` 再把同代次 binding 变为 enabled/ready/unfenced，并令 execution epoch 增长。
2. `extension_operation_dispatch_binding` 不会随上述两步自动更新，旧九路仍指向原 epoch；首次 cutover 不允许 extension→同 installation/generation 的直接重切。
3. 现有 `EcommerceGrowthDisableDependent` 与 `ar2_017` 的 fence/detach 函数仍以 activation 的初始 epoch/revision 为准。接续后必须从最新有效 Refresh Receipt 解析当前 target，否则“可配置但不可禁入/卸载”违反产品目标。
4. 原 AIP cutover 审批只接受 activate/rollback payload。配置接续必须登记独立 action type，审批内容绑定 F1 `approval_intent()`，不能复用旧 cutover approval 或客户端自称批准。

## 受保护事务

Python Owner 在同一 tenant-scoped maintainer 事务中：

1. 严格解析 F1 request，确认调用 actor、session role 与租户。
2. 锁定精确 ActionApprovalEvent/Proposal/Draft，重算 action snapshot、风险策略、payload binding；复验 maker、checker、executor 当前 membership/marking 与 installation operation 权限。
3. 调用 068 `SECURITY DEFINER` 函数。函数只允许非超级、非 bypass-RLS、具 maintainer member 的 session user。
4. 函数按固定顺序锁 installation、runtime binding、configure operation、enable operation、原 activation、前驱 Receipt、九路 dispatch；校验：
   - binding 正是 target config/revision/epoch，且 enabled/ready/unfenced；
   - configure 与 enable 均 `status=phase=succeeded`，revision、installation 和 actor 精确；
   - 两个 accepted event 的 `configurationTarget` 分别绑定 source revision 与 target revision 前一版，且均指向 target config；
   - 九路集合与 F1 固定集合完全一致，均为 extension、同 installation/generation、source epoch、同 expected group revision、未围栏；
   - 初次接续以 CutoverResumeReceipt 为源，后续接续必须是该组最新 Refresh Receipt，且 source 等于上一 target；
   - approval ref 与 request hash 保持原值，外部效果和业务续跑均为 false。
5. 单条事务内把九路 execution epoch 更新到 target、各自 revision+1、group revision+1，并插入 canonical Receipt；重复 idempotency key 仅在 request hash、actor、链头完全相同才返回既有 Receipt。
6. Python decode 回读 Receipt；提交前再次复验审批有效期和当前 executor 权限。未知提交由 GET-by-key/Receipt 回读解决，不自动重发不同 key。

## Disable / detach 兼容

068 提供“当前 dispatch authority”解析：无 Refresh 时返回原 resumed activation；有 Refresh 时要求最新 Receipt 链完整并返回其 target runtime revision/epoch/config。生命周期 Python 与数据库 fence/detach 都使用这个解析结果：

- fence 接受当前 binding revision = 最新 target revision + 1（runtime disable 围栏后），epoch = 最新 target epoch + 1；
- detach 接受 disable 完成后的 revision = 最新 target revision + 2；
- claimed/running/unknown 查询覆盖同 installation/generation 的所有 epoch，Receipt 记录实际发现项，不再只看首次 activation epoch；
- lifecycle Receipt 仍保留原 activation operation 作为根，并增加/核验最新 refresh authority ref，不能改写旧 activation 历史。

现有 lifecycle Receipt 的不可变 `authority_data` 足以保存该 ref，无需扩表；旧记录缺字段时保持可读，新接续后的 disable 必须非空。

## 实施状态

2026-09-16：F3 已在隔离库完成。两次连续续接、链头幂等、刷新后 fence/detach、全 epoch 未决阻断与旧路径回归均已验证；详见 `sc4-5l6y5f3-refresh-owner-verification.md`。主库部署和真实审批/接续属于 F4，仍未执行。

## 计划文件

- `services/aos-api/alembic/versions/a0v_068_dispatch_configuration_refresh_owner.py`
- `services/aos-api/aos_api/ecommerce_dispatch_configuration_owner.py`
- `services/aos-api/aos_api/ecommerce_dispatch_configuration_approval.py`
- `services/aos-api/aos_api/ecommerce_growth_cutover_action_binding.py`
- `services/aos-api/aos_api/ecommerce_growth_cutover_proposal_gate.py`
- `services/aos-api/aos_api/ecommerce_growth_cutover_current_approval.py`
- `services/aos-api/aos_api/aip_action_policy.py`
- `services/aos-api/aos_api/aip_action_store.py`（仅在固定 action 集合不能自然覆盖时最小改动）
- `services/aos-api/aos_api/ecommerce_growth_lifecycle.py`
- 对应 unit/native PG/既有 lifecycle 回归测试。

## 验收与停止规则

1. 先写原子 Owner 的失败测试，确认缺函数/缺 action binding 红灯。
2. 隔离 PG 正向一次接续；重复同 key 零二次更新；第二次连续接续成功。
3. 分别篡改租户、审批、配置目标、操作终态、binding revision/epoch、九路集合、group revision、前驱 Receipt，均零 dispatch/零 Receipt 副作用。
4. refresh 后 disable fence/detach 通过；旧无 refresh 路径回归通过；跨 epoch claimed/unknown/running 阻止 detach。
5. 累计 F1/F2/cutover/action/lifecycle 测试通过，`git diff --check` 通过；核对方案与实现一致后才提交。
6. 同一阶段连续两次出现相同根因则停止外部动作并复盘；本波无外部业务动作。下一波 F4：clone 067/068、保全核验、受控主库部署、真实审批与一次同代接续，再验 disable/detach/恢复和浏览器状态。
