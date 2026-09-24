# W5c3u 第三继任者 Cutover Pause Claims 方案（2026-09-24）

## 起点

W5c3t `4537090f`：operation `9273172f-8b30-55dd-bb48-1aac06965454` prepared，prepare Receipt `2ac2ef0b-b5ea-4b32-9036-f40b9ed373fb`/hash `sha256:34750026f38a50e7aceaab78a8a9a53ddd1cb43d038941ce63c5aa656f4e63bc`，现行九路仍 group365 legacy/fenced、12 schedule off。目标 Host PID17302/三 held 资源，业务 claims40/runs53。此波只 begin_activation_commit 暂停 claims，不提交九路。

## 串行步骤与停止

1. 原独立 audit 复核 prepare Receipt/hash、operation prepared、审批仍有效、Host/目标 binding rev4/epoch3、资源 held、九路 rev338/group365、零 running/claimed/unknown/canary、12 schedule off、业务计数不变。
2. 固定 `CutoverCommitRequest`，key `a0v-w5c3u-third-successor-cutover-commit-20260924-v1`；该 request/key 将供下一波 commit **同一请求** 使用，但 pause 本波只发一次 `begin_activation_commit`。0600 intent/result；未知结果只读对账，不调用 commit。
3. 独立核 operation draining、唯一 pause Receipt/hash、claim gate paused、九路仍 group365 legacy/fenced、零在途/12 schedule off/业务不变；verification、m1 commit。下一波才原 Owner `commit_activation`，必须引用本波同一请求和 prepare/pause 正式 Receipt。

任一审批过期、Runtime/Host/lease/预算/路由/调度/在途/canary 漂移或 pause 边界未知，停止写且不重发；绝不读商城源或手工 run_definition。
