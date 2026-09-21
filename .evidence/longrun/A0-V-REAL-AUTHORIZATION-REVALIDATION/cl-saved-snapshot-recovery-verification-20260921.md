# CL 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CL_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`bf2ff936-6c93-4712-93cb-30dd312f11eb` 正式 failed rev5，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition
已推进到 rev181 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。

## 1/6 plan 与基线

HEAD `dde14d6c`；CL `64e49f66-b0ef-4676-91c1-eb05f6d1d0b1` / generation
`a583218d-f65b-4697-9e60-7281a0bff66e`，binding rev6/epoch3 ready、九路 rev237/group264、
唯一 Host PID 94133；definition rev178 disabled、recovery58、attempt=0，12/12 与零副作用。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；
`/v1/health` 与 OpenAPI=200，prepare/schedule-ingest/controls 各确认 12 项，随后 18181 释放，
第二 Host=0，PID 94133 保持在线。

## 3/6 冻结输入转移

transfer 生成 rev179 disabled/hash
`sha256:483e4ce71b2f79cafb74fbaffa03b1da389421aebe9c6dafe6a5202f078e330e`；
renew 生成 recovery59/hash
`sha256:398205f8a032adc5af6fad259ba7780f600340382a7b542530725c0d78fd426f`；
enable 生成 rev180 enabled/hash
`sha256:1ae23b85e72eef7823b0584de4a70f222b94944e5bd5ea0550a6ce8b2cb94618`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
各阶段 sourceReads=0。

## 4/6 唯一自然 worker

Lease `A0V-CL-SNAPSHOT-WORKER-20260921` 已在 worker 启动前登记；唯一 worker PID 96160
自然创建上述 attempt，幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样见 running rev2，100 秒见 running rev3，150 秒见 failed rev5；accepted_at
`2026-09-21T09:41:26.976027Z`，completed_at `2026-09-21T09:42:59.553579Z`。
不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev180/recovery59/failed rev5；pause-terminal 生成 rev181 disabled/hash
`sha256:bd3b51d3f936f460b1ed12906edb09f08e7f7cf61ee38736472251f3bba154d5`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0、worker=0、18181=0，Host PID 94133 仍在。
下一波为 CL 正式退休与 CM direct successor。本提交完成后自动进入该波。
