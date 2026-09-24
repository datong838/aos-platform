# W5c3p 九路 Cutover 审批部分验证（2026-09-24）

## 结论

**停在审批前；没有 proposal、approval 或 cutover 写入。** 方案 `0c7e5c91`，新 policy `externalEffectsAllowed=false`、`fallbackAllowed=false`，注册 Receipt `7861c44a-94b4-4e7a-8898-1d9f70a3d214`。预检目标 active/ready、Host PID17302、九路 group365 legacy/fenced、12 调度关闭、零 attempt/canary、业务 claims40/runs53；4 个 policy/Receipt 正反测试通过。

私有 0600 intent 已冻结。原历史 `_approve` 在 `AipActionStore.action_type_snapshot` 的第一笔 `meta_action_type` SELECT 被 `permission denied for table meta_action_type` 拒绝，尚未到 `create_proposal`。只读 `reconcile` 证实该键 proposal0、目标 cutover operation0、九路 group rev365，故提交边界明确为 prewrite rejection；不重试同键、不删除 intent。未读商城源，未切路由/开调度/运行业务。

## 下一波 W5c3pR

先方案，读当前 AIP 产品/技术契约与权限、正常审批 HTTP/API/DB 路径，找具备合法 action-type 读写与 maker/checker 约束的现行 Owner；不直接扩权、不借历史过期审批、不伪造 checker。修复后用全新键并独立测试/预检，再单次审批。审批成功才进入 cutover prepare；本波绝不继续。
