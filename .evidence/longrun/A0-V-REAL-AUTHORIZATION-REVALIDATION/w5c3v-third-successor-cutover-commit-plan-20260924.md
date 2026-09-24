# W5c3v 第三继任者九路原子 Commit 方案（2026-09-24）

## 起点与唯一写入

W5c3u `a3d79691`：operation `9273172f-8b30-55dd-bb48-1aac06965454` draining，claim gate paused=true/rev1，pause Receipt `2bc7f6b9-4530-4d9f-98b6-3b5d457b32d4`/hash `sha256:ea0a6f6d1dfe1dd4280a87e67a0c8639249ad7ba02f3539248bff61285e6c672`，`CutoverCommitRequest` key `a0v-w5c3u-third-successor-cutover-commit-20260924-v1`/hash `sha256:fee8148ea725c952330eeed54847476c11763ac02146570f7de32c7d3f8bf5ae`。目标 binding rev5/epoch3 fenced、九路 route338/group365 legacy/fenced、12 schedule off、Host PID17302。此波只原 `commit_activation` 一次，原子切九路，不 validate/resume 或业务 Run。

## 串行步骤

1. 独立回读 prepare/pause 正式 Receipt/hash、同一原请求、draining/gate paused、九路旧快照、binding rev5/fenced/三 held 资源/Host、approval 与四来源/预算当前、running/claimed/unknown/canary0、12 schedule off、业务计数不变。commit Receipt0。
2. 私有 0600 intent 精确引用 W5c3u 原请求/key/hash，不新建另一 commit key；原 Owner 单次 `commit_activation`。结果未知仅按 operation/Receipt/九路只读对账，绝不重发。
3. 成功只认正式 commit Receipt、operation committed、九路 9/9 extension 且全部指向当前 installation/generation/epoch3、route339/group366、binding rev5 fenced/gate paused、12 schedule off、业务计数不变；verification 与 m1 commit。
4. 下一波单独 validate，随后 resume；在 resume 前不得放行 claims。12 selection/control/definition 后续波，不能把 cutover 等同业务成功。

## 停止条件

任一 Receipt/approval/Runtime/Host/lease/预算/九路/调度/在途/canary 漂移或提交边界未知，停写对账；不读商城源、不手工 run_definition。
