# W5c3pR Cutover 审批权限恢复验证（2026-09-24）

## 结论

**GREEN，仅根因和合法连接路径；未重发审批。** W5c3p 的历史 `_approve` 默认 `aos_api.db.connect` 指向本机旧库 `aos_meta`，而本波 AOS 正式权威库是 `aos_meta_head`。旧库存在 `meta_action_type` 但没有目标 proposal 表，报表权限错误只是连接错库的首个表象。主库的 `aos_runtime` 对必要表有效权限存在，未作 GRANT/迁移/扩权。

## 只读证据

- 主库会话 `database=aos_meta_head`、原登录 `aos_app`；使用现有 `apply_transaction_scope` 后为租户 `org-org/dev-project` 的 `aos_runtime`，action type SELECT 和 proposal INSERT 均有效，当前 cutover action type 唯一。原 `AipActionStore` 通过该窄连接成功读取 action 快照，revision hash `e6fe651c784f8a2a686dddd77447cd8b5f7afee96c4093173a8baac74879e872`。
- 旧 `aos_api.db.connect` 会话 `database=aos_meta`，没有目标 proposal 表；不用于主库审批。W5c3p 原键 `reconcile` 已证明 proposal0/cutover0，九路 rev365，保留 intent、不重试。
- 新只读 `scripts/a0v_w5c3pr_approval_permission_inventory.py` 的 `head_action_connection` 要求精确租户、主库和 runtime 角色；反租户测试 2 passed，`git diff --check` 通过。未读商城源、未切九路/调度。

## 下一波 W5c3s

先方案，再给历史审批 Owner 包装 **主库租户受控连接**，新审批键/新私有 intent；预检旧键 proposal0、注册 Receipt/current live 状态与 policy 仍精确，原 AIP Store 按 maker/checker 正式审批，独立读回批准链。若现行审批模型拒绝，按正式错误冻结，不放宽 policy 或冒用身份。审批 GREEN 后才单独计划 cutover prepare。
