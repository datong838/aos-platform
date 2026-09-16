# SC4-5L6Z-P2：P 最终 shrink、detach 与 uninstall 方案

日期：2026-09-17

## 起点权威

P installation `9950e057-5cb4-4849-a499-35837d8d0fb6` 仍为 active/etag5；runtime
generation `df883b18-0170-410b-8424-442c7cdd60b4` 为 revision7/epoch4、
disabled/fenced/desired-enabled/observed-unknown，三资源全部 released。Policy11 已 revision2/disabled；
65 个 occurrence 已全部 cancelled，5 个 attempt 为 closed_unaccepted，65 个 closure Receipt 均为
businessAccepted=false，目标 command Receipt/Run 和负租户 canary 均为零。dispatch group revision50
有十路 extension，仅 event-control route fenced。

## 固定执行顺序

1. 用当前 fence Receipt、group revision50、runtime revision7 和独立 ActionApprovalEvent 执行 event
   shrink。只删除 event-control route，九路业务 route 保持 P epoch3 extension/unfenced，group 变为51。
2. 通过既有 `require_released_owner_settlement` 创建一次 runtime disable 请求，target 必须是 binding
   revision7。该请求只建立受控 runtime operation，不重复释放已经 released 的资源。
3. 使用固定 `RuntimeDisableConsumer` 领取该 operation。`begin_disable` 将 runtime 推进到 epoch5/
   revision8 并由 `EcommerceGrowthDisableDependent` fence 九路；`finish_disable` 在全代际 drain 为真后
   将 runtime 置 desired-disabled/revision9，并由同一 dependent 将九路改为 legacy/null target/
   fenced。预计 dispatch revision27→29、group revision51→53，保存 fence 与 detach Receipt。
4. 只有 operation succeeded、outbox acknowledged、九路完全 detached、runtime revision9/epoch5、
   资源仍全部 released、历史 event/closure/control/lifecycle Receipt 可回读时，才调用正式
   uninstall service，以 etag5 和新的幂等键把 installation 变为 uninstalled/etag6、active revision
   为空。正式 uninstall 同一事务还会把 retained runtime binding 从 revision9/
   desired-disabled/observed-unknown 推进为 revision10/desired-uninstalled/observed-stopped；资源与历史
   binding 不删除。

## 重启恢复与禁止项

受控 launcher 必须恢复既有 runtime/registration 私有身份；审批仅在显式 main DSN 范围内使用。
每个 action 先冻结 intent，再写 result；存在 intent 无 result 时只能回读数据库，不得重发未知
disable、detach 或 uninstall。禁止直接 UPDATE runtime、dispatch 或 installation，禁止改绑到未来
successor，禁止启动模型、内容、媒体或外部平台能力。

真实 uninstall 首次调用已提交，但执行器因仍期待 runtime revision9 而在写 result 前停止。恢复只
允许读取 `bundle_installation_command` 中同一 idempotency key 的
`bundle_installations.uninstall`、HTTP 200、response etag6，并同时验证 installation etag6/
uninstalled、runtime revision10/uninstalled/stopped；不得再次调用 uninstall service。

## 停止条件

任一 occurrence 非 cancelled、目标 Receipt/Run 非零、Policy11 重新 enabled、runtime/dispatch/
installation revision 漂移、非 event route 在 shrink 前被 fence、detach 后仍有 P target、lifecycle
Receipt 不完整、canary 非零，立即停止写入并只读对账。uninstall 之后仍需验证历史 Receipt 可读；
本波结果不等于 successor 自然链完成。

## 代码与证据目录

- 固定执行器：`scripts/a0v_z_p_final_lifecycle.py`
- 方案与公开结果：`.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/`
- 私有 intent/result：`.aos-recovery-20260916/state/.../successor-p/final-lifecycle-v7/`
