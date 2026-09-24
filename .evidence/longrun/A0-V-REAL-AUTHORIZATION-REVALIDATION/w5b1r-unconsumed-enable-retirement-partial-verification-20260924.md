# W5b1R 取消悬挂 enable 的部分验收与事务冻结（2026-09-24）

## 结论

**未完成取消；事务被正式生命周期门禁回滚，绝不重发。** 按 `w5b1r-unconsumed-enable-retirement-plan-20260924.md`，写前精确验证旧 enable `1d5b0071-3067-456f-8ab5-ee1f666abd83` 为 accepted/过 deadline，唯一 outbox attempt0、未领取/未交付，binding rev11/epoch6 disabled/fenced、Config rev2、资源 released、attempt0、12 schedules off、canary0；新 disable 键此前为 0。

冻结 intent 0600 后，原 `RuntimeDisableService.request` 一次进入同事务取消流程，却被 `extension_dispatch_lifecycle_fence_ar2_017` 拒绝：`open activation claim gate authority drifted`。独立回读新键 `bundle_installation_command=0`、新 disable operation=0（该 DS 仅有 W5b0 的旧一条）、旧 enable 仍 accepted、binding 仍 rev11；本次数据库事务完整回滚。私有目录仅有 intent，无 request-result，不再调用 `request_disable`。

## 根因证据与边界

- 当前 DS 对应历史 `extension_dispatch_cutover_operation` 仍为 `resumed`，group `6a402d31-83ad-546c-807f-508c87498ce1`；但其 `extension_dispatch_claim_gate` 当前行不存在。
- 该 group 的 9 条 `extension_operation_dispatch_binding` 已全部回退为 `legacy` 且 `operation_fence=true`（group revision 365），`extension_dispatch_lifecycle_operation` 历史有 112 条 `detached`。当前并无一条 extension handler 仍挂在 DS 上。
- Python 生命周期回调仍可把这条历史 resumed activation 选作本次 disable 的待 fence 对象，随后 DB 函数严格要求开放的 claim gate rev2；这造成已退休 group 被再次 fence 的阻断。不能直接补一条 gate、改状态、删历史或传 `dependent=None` 绕过门禁。
- 当前 enable 仍未消费、不能以 deadline 到期视为取消；业务执行边界保持关闭。执行器拒绝已有私有状态、缺失正式 Receipt 和重复 claim 的测试 3 passed，`git diff --check` 通过。

## 下一波 W5b1R2

先方案后最小代码修复：在原 EcommerceGrowth lifecycle Owner 内，只有能独立证明同一 cutover group **恰好 9 条均 legacy/fenced、无目标安装 extension dispatch、无开放 claim gate，且历史已正式 detached** 时，才将该旧 resumed activation 判为无当前待 fence 关系；其他歧义仍 fail closed。先用隔离测试证明拒绝半退役/混合状态，再对 W5b1R 的旧 intent 作只读对账，使用**新波次、新幂等键**正式取消旧 enable，不在本波重发。若修复不能证明完整边界，继续冻结并转正式 direct successor 设计。
