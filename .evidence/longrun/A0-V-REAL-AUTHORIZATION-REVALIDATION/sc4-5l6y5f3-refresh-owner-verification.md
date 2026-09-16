# Y5f-F3 同代次配置接续 Owner 验证

日期：2026-09-16

基线：`m1@c1d37652`

Task Receipt：`SC4-5L6Y5F3-REFRESH-OWNER-20260916`

## 结论

隔离 PostgreSQL 中，同 installation/generation 的配置续接已形成受控闭环：严格 F1 request 经独立 R2 maker-checker 审批绑定后，由专用 maintainer Owner 在一个事务中核验当前安装、已完成 configure/enable、ready binding、原 activation、最新前驱 Receipt 与九路 dispatch，原子推进九路 execution epoch/group revision 并写入不可变 Receipt。相同 key 只在相同 request/actor 且仍为链头时回读；第二次连续续接后，旧 key 被拒绝。

配置续接后的 disable/detach 不再使用首次 activation 的固定 revision/epoch。生命周期 Owner 解码最新 Refresh Receipt，以其 target revision/epoch 选择当前 authority，并把精确 `DispatchConfigurationRefreshReceipt` ref 写入 fence 与 detach Receipt；unknown attempt 检查覆盖同 installation/generation 的全部 epoch。无 Refresh 的既有路径保持兼容。

本结论仅为隔离库实现与验证完成。主库仍停在 a0v066，本波未部署 067/068、未创建真实审批、未切换真实 dispatch、未启停真实业务 Run、未读取商城源，也未触碰 230 L0。

## 实现文件

- `services/aos-api/alembic/versions/a0v_068_dispatch_configuration_refresh_owner.py`
- `services/aos-api/aos_api/ecommerce_dispatch_configuration_owner.py`
- `services/aos-api/aos_api/ecommerce_growth_lifecycle.py`
- `services/aos-api/aos_api/ecommerce_growth_cutover_action_binding.py`
- `services/aos-api/aos_api/ecommerce_growth_cutover_proposal_gate.py`
- `services/aos-api/aos_api/ecommerce_growth_cutover.py`
- `services/aos-api/aos_api/aip_action_policy.py`
- `services/aos-api/tests/extension_runtime/test_dispatch_configuration_refresh_owner_pg.py`
- `services/aos-api/tests/test_ecommerce_dispatch_configuration_owner.py`
- `services/aos-api/tests/extension_runtime/test_cutover_action_binding.py`
- `services/aos-api/tests/test_ecommerce_dispatch_configuration_contracts.py`

## 验证证据

1. 审批/action binding RED：新增 action type 前，refresh action 被固定集合拒绝；修正后 action snapshot、payload、tenant、installation 与 R2 maker-checker 均受现有 exact binding 约束。
2. 原子 Owner：九路中任一路 epoch 漂移时，零 Receipt；恢复后首次续接成功；相同 key 回读且零二次更新。
3. 连续链：第二次 configure/enable 后续接成功，Receipt revision 从 1 连续到 2；此后重放 revision 1 的旧 key 被 `idempotency conflict` 拒绝。
4. 生命周期：最新 revision 2 Refresh Ref 同时进入 fence/detach Receipt；九路最终恢复 legacy，证明配置可更新后仍可正式禁入和卸载。
5. 兼容回归：无 Refresh 的任意额外 binding revision/epoch 路径、claimed/unknown/occurrence 阻断及 regressed epoch 均保持原语义。
6. 累计命令结果：`75 passed, 1 skipped`，耗时 8.75 秒；skip 为既有条件项。新增 Owner 双重审批复验专项另为 `38 passed` 组合中的 2 项。
7. `git diff --check` 通过。

## 方案一致性与风险

- 生命周期表已有不可变 `authority_data`，无需新增可空列；Refresh Ref 保存在该 canonical authority JSON 中，旧 Receipt 缺字段时按 `None` 读取。
- 068 SQL 函数只接受非 superuser、非 bypass-RLS 且属于 `aos_extension_maintainer` 的 session user；完整当前审批、maker/checker membership 与 action binding 在同一事务的 Python Owner 中写前/写后各复验一次。F4 主库执行必须只走该 Owner，不把底层函数暴露为产品入口。
- 真实审批和配置操作尚不存在；隔离 fixture 只证明代码合同，不能当成真实 authority。
- 未执行主库迁移与真实 dispatch 切换，因此不能宣称 Y5f 或完整经营链完成。

## 下一波 F4

1. clone 主库 a0v066，部署 067/068 并执行保全、ACL、downgrade-retain、租户 canary 核验。
2. 读取当前安装/configure/enable/dispatch 与正式角色，生成一份真实但 `externalEffectsAllowed=false`、`resumeBusinessRuns=false` 的接续计划。
3. 创建独立 refresh Proposal/Approval，经 Owner 执行一次真实同代接续；未知提交只按 key 回读，不换 key 重发。
4. 验证九路新 epoch、Receipt 链、旧 epoch 无新 claim；再做受控 disable/detach/恢复证明，不启动自然经营 Run。
5. 浏览器显示当前配置与接续来源；完成后进入 Y5d/Y6d 自然触发首链。
