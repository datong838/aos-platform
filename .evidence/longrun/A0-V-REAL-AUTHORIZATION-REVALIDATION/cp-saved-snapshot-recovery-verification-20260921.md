# CP 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CP_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`4c63e9fd-6f11-461d-a753-87962f5306ad` 正式 failed **rev4**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition
已推进到 rev193 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。

## 1/6 plan 与基线

HEAD `73265166`；CP `1d8b71c5-1cde-4d16-b16f-835f92bf8663` / generation
`9b0201fc-9822-4527-b63c-23cbd416057d`，binding rev6/epoch3 ready、九路 rev249/group276、
唯一 Host PID 6635；definition rev190 disabled、recovery62、attempt=0，12/12 与零副作用。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；
`/v1/health` 与 OpenAPI=200，prepare/schedule-ingest/controls 各确认 12 项，随后 18181 释放，
第二 Host=0，PID 6635 保持在线。

## 3/6 冻结输入转移

transfer 生成 rev191 disabled/hash
`sha256:11be0b236f6873867cdad7c67d03c8b8009d4156ee573cefd16b2c9049528c98`；
renew 生成 recovery63/hash
`sha256:785823471c14d9eda4e67250e19f9b498116aaf510e62a77ff47d0275dfa24e6`；
enable 生成 rev192 enabled/hash
`sha256:9c3caba3ab62dc6a365ec84fc5fd5630986fabdd6979c69844881ae86966b8c5`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
各阶段 sourceReads=0。

## 4/6 唯一自然 worker

Lease `A0V-CP-SNAPSHOT-WORKER-20260921` 已在 worker 启动前登记；唯一 worker PID 8020
自然创建上述 attempt，幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样见 running rev2，随后见 failed rev4；accepted_at
`2026-09-21T11:37:24.038318Z`，completed_at `2026-09-21T11:38:47.386758Z`。
不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev192/recovery63/failed rev4；pause-terminal 生成 rev193 disabled/hash
`sha256:e1bee2c59d4803a5e996fd125a51ef1534853b5478af3b56b667513592320cf9`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0、worker=0、18181=0，Host PID 6635 仍在。
目标回归 `210 passed, 7 warnings`。下一波为 CP 正式退休与 CQ direct successor。注意终态为 **rev4**，guard overlay 仍需
predecessor_view revision=4。本提交完成后自动进入该波。
