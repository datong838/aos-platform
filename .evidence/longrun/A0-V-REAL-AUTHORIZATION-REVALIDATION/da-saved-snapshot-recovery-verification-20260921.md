# DA 保存快照恢复正式终态验证（2026-09-21）

## 结论

`DA_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`f61804b2-7863-4371-ac66-80e0a6eb1d0d` 正式 failed **rev4**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition
已推进到 rev223 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。本波从
CZ installation `162e4c29-a24e-4c6b-8da7-9582d090d708` rev220/recovery72 转入 DA。
本波无页面改动，未开浏览器。

## 1/6 plan 与基线

HEAD `e7d8a544`；DA `f4fcdf0b-a37b-419c-9de0-14b08cd7320d` / generation
`dbcdd8cb-c6f4-47cc-91f9-1662f54044c0`，binding rev6/epoch3 ready、九路 rev282/group309、
唯一 Host PID 45786；definition 为 CZ `162e4c29-a24e-4c6b-8da7-9582d090d708` rev220
disabled、recovery72、attempt=0，12/12 与零副作用。configuration rev1 已引用
RuntimePolicy rev11。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；
`/v1/health`=200，prepare/schedule-ingest/controls 各确认 12 项，随后 18181 python PID 47053
SIGTERM 释放，第二 Host=0，PID 45786 保持在线。prepare 在 binding rev6/epoch3 上一次通过，
previewHash `sha256:ae69552a095f341ed9bb7e7ef06eb78322d066b3ee6b094e848224b4afe11977`。

## 3/6 冻结输入转移

transfer 生成 rev221 disabled/hash
`sha256:b48d0bb38b6482a902c405593556b9b0bb1fe3134096bde6d129f650b9da8e24`；
renew 生成 recovery73/hash
`sha256:13d1f720afe37c554549a5c8605448fb3df7a85f519b92fdae367f0653477cdc`；
enable 生成 rev222 enabled/hash
`sha256:f320d7f19c07c5c5712cdbaa2c4a8051cd15a18acc2da7dcbf8c36b8d60757b0`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
各阶段 sourceReads=0。

## 4/6 唯一自然 worker

Lease `A0V-DA-SNAPSHOT-WORKER-20260921` 已在 worker 启动前登记；唯一 worker PID 47471
自然创建上述 attempt，幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样见 running rev2，随后见到 failed rev4；accepted_at
`2026-09-21T17:04:46.379126Z`，completed_at `2026-09-21T17:06:07.310695Z`。
不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev222/recovery73/failed rev4；pause-terminal 生成 rev223 disabled/hash
`sha256:02b21df15a3d68d768bdabdeb61c3a4912138a320dbac1c7374d40453d52990e`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0、worker=0、18181=0，Host PID 45786 仍在。
注意终态为 **rev4**，guard overlay 仍需 predecessor_view revision=4。本提交完成后自动进入
DA 正式退休与 DB direct successor。不使用定时 wake。本波无页面改动。退休 preflight 前不得
创建 `replacement-db`。
