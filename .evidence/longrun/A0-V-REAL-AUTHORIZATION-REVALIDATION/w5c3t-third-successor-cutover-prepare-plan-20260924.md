# W5c3t 第三继任者九路 Cutover Prepare 方案（2026-09-24）

## 起点与唯一写入

W5c3s `3e2d526d`：当前主库 proposal `proposal-acf0531dcc7d42f598a8` approved，最后 approval ref `approval-9a7388ca0ddd44e497c8` rev2/hash `sha256:bcb222353e0a67fb8b82b7cbf916b049c1c9dd1b9a124d01dd09bfb37c9981b6`；policy externalEffectsAllowed=false/fallbackAllowed=false、注册 Receipt `7861c44a-94b4-4e7a-8898-1d9f70a3d214`。九路 group365 legacy/fenced，Host PID17302、12 schedules off。此波只调用原 `EcommerceGrowthCutoverStore.prepare_activation` 一次；不 pause/commit/validate/resume、不执行业务。

## 串行步骤

1. 再验批准尚未过期、原 proposal/checker 链/policy/hash 与 W5c3s 冻结文件一致、注册 Receipt、目标 active/etag5、binding rev4/epoch3 ready、Host/三 held 资源、四来源/预算、九路 route rev338/group365、零 running/unresolved/pending/canary、12 schedule off、业务计数。新 prepare 键/operation 0。
2. 固定新 operation UUID 和幂等键 `a0v-w5c3t-third-successor-cutover-prepare-20260924-v1`，checkpoint `canonical-router@1`、occurrenceWatermark null、pendingTargetReceiptRefs 空，引用精确 approval/policy/registration，0600 intent 先落盘。
3. 原 cutover Owner 单次 `prepare_activation`。未知提交边界只按新 key/operation/Receipt 只读对账，绝不重发。成功须 status prepared、prepare Receipt/hash 正式读回，九路仍 legacy/fenced、group365、业务与调度不变。
4. verification 与 m1 commit；下一波才 pause/begin commit，之后各相位独立波。若审批过期或目标/九路漂移，不复用本次 intent。

## 停止条件

任何审批权限/期限/Receipt 不当前，或 Runtime/Host/租约/预算/九路/调度/在途/canary 漂移、结果未知，立即停写并只读对账；不读商城源、不手工 run_definition。
