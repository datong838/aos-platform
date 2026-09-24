# W5c3s 第三继任者 Cutover 主库审批恢复验证（2026-09-24）

## 结论

**GREEN，仅 cutover 审批。** 原 AIP `_approve` 经已验证的 `aos_meta_head` 精确租户 `aos_runtime` 连接，使用新键 `a0v-w5c3s-third-successor-cutover-approval-20260924-v1` 一次生成 proposal `proposal-acf0531dcc7d42f598a8`，两位既有 checker 的正式批准链终态 approved；最后 approval ref `approval-9a7388ca0ddd44e497c8` rev2/hash `sha256:bcb222353e0a67fb8b82b7cbf916b049c1c9dd1b9a124d01dd09bfb37c9981b6`。策略 `externalEffectsAllowed=false`、`fallbackAllowed=false`，目标新安装、九路 group rev365、注册 Receipt 精确。

## 证据与边界

- 方案 `e0cb0819`；W5c3p 旧键经只读 reconcile 仍 proposal0/cutover0，旧 intent 未删除、未重发；当前主库 action-type 快照和权限预检通过，新键0。
- 0600 intent/result 独立保存；原 Owner 未修改，进程内仅将其连接工厂临时指向主库租户受控连接，退出时恢复。新 proposal 唯一，独立 AIP Store 读回 status approved、approval ref 与冻结 payload/policy 一致。
- 第三安装/Host PID17302、九路 9/9 legacy/fenced/group365、12 schedule off、业务 claims40/runs53 保持；canary0。定向测试 5 passed，`git diff --check` 通过。未读商城源、未切九路、未执行 definition。

## 下一波 W5c3t

审批有 45 分钟有效窗。立即先方案，再按原 cutover Owner 的 `prepare_activation` 生成独立 operation/prepare Receipt；后续 pause→commit→validate→resume 各波独立读回与停笔。若 approval 到期、Host/资源/预算/九路/调度漂移，先冻结，不沿用过期票。
