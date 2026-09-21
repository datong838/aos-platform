# CW 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CW_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`0f9c30e6-012d-4a08-9aed-f7b0e0492c31` 正式 failed **rev4**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition
已推进到 rev211 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。本波从
CV installation `f94149ca-a01e-4a20-836f-3f5132e0dbb7` rev208/recovery68 转入 CW。
本波无页面改动，未开浏览器。

## 1/6 plan 与基线

HEAD `eb54dafc`；CW `0d5d5a7f-6e40-4725-b337-b79acc7d896a` / generation
`a60036f1-5887-4157-ad32-616925b547bf`，binding rev6/epoch3 ready、九路 rev270/group297、
唯一 Host PID 32943；definition 为 CV `f94149ca-a01e-4a20-836f-3f5132e0dbb7` rev208
disabled、recovery68、attempt=0，12/12 与零副作用。configuration rev1 已引用
RuntimePolicy rev11。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；
`/v1/health`=200，prepare/schedule-ingest/controls 各确认 12 项，随后 18181 python PID 35235
SIGTERM 释放，第二 Host=0，PID 32943 保持在线。prepare 在 binding rev6/epoch3 上一次通过，
previewHash `sha256:9c512b0be551e3972413f39e6ce973d324ffc9f7cafecc8a10dd1d378ceeade1`。

## 3/6 冻结输入转移

transfer 生成 rev209 disabled/hash
`sha256:f9e1f3ff60564e421e4bca05aeba8d63de9ec5522e45a968714c6606f39a4c8e`；
renew 生成 recovery69/hash
`sha256:d03e6744c2d58040157332409945c6d67073eba4a5b5592a96459d6eeba276f5`；
enable 生成 rev210 enabled/hash
`sha256:8cacbd9ee2163df63cc2940913386ce9b2d073fe1787aea657ac48d476abe5be`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
各阶段 sourceReads=0。

## 4/6 唯一自然 worker

Lease `A0V-CW-SNAPSHOT-WORKER-20260921` 已在 worker 启动前登记；唯一 worker PID 35833
自然创建上述 attempt，幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样见 running rev2，随后见到 failed rev4；accepted_at
`2026-09-21T15:20:19.074988Z`，completed_at `2026-09-21T15:21:43.412712Z`。
不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev210/recovery69/failed rev4；pause-terminal 生成 rev211 disabled/hash
`sha256:ba6bc2d3e788809ebfc2624fd9b3984440c0d93f578627cc5ebe7bd8d5014260`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0、worker=0、18181=0，Host PID 32943 仍在。
注意终态为 **rev4**，guard overlay 仍需 predecessor_view revision=4。本提交完成后自动进入
CW 正式退休与 CX direct successor。不使用定时 wake。本波无页面改动。
