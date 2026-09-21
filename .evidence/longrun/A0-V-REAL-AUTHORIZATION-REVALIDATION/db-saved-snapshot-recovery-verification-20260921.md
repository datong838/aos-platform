# DB 保存快照恢复正式终态验证（2026-09-21）

## 结论

`DB_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`1679bef7-84fc-408c-9bb2-d202ba68dc91` 正式 failed **rev4**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition
已推进到 rev226 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。本波从
DA installation `f4fcdf0b-a37b-419c-9de0-14b08cd7320d` rev223/recovery73 转入 DB。
本波无页面改动，未开浏览器。

## 1/6 plan 与基线

HEAD `e3a65959`；DB `aaaa1ac1-2c35-4c35-8e7b-3ed6cd47f9c8` / generation
`c1ae6205-0743-483c-82e3-1d1c95b1ab31`，binding rev6/epoch3 ready、九路 rev285/group312、
唯一 Host PID 48103；definition 为 DA `f4fcdf0b-a37b-419c-9de0-14b08cd7320d` rev223
disabled、recovery73、attempt=0，12/12 与零副作用。configuration rev1 已引用
RuntimePolicy rev11。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；
`/v1/health`=200，prepare/schedule-ingest/controls 各确认 12 项，随后 18181 python PID 49622
SIGTERM 释放，第二 Host=0，PID 48103 保持在线。prepare 在 binding rev6/epoch3 上一次通过，
previewHash `sha256:4499a4e9af8ab4aed1df9a2810b1a6f2b35dcf65d6c4e90780d786ff1c417dd2`。

## 3/6 冻结输入转移

transfer 生成 rev224 disabled/hash
`sha256:210a746b912d130bbeb66ed8c120a2ad48fe30b3b78aeca2abc0ce807c3acfc2`；
renew 生成 recovery74/hash
`sha256:b07f0b5552f66117e4006143999b5ccea65d49efe02b2c0d0d98389bbea405ab`；
enable 生成 rev225 enabled/hash
`sha256:037d54de3f92d4ae6e49d30ca2725f3bcdfa66bedf973eecf261153266ff99a2`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
各阶段 sourceReads=0。

## 4/6 唯一自然 worker

Lease `A0V-DB-SNAPSHOT-WORKER-20260921` 已在 worker 启动前登记；唯一 worker PID 50142
自然创建上述 attempt，幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样见 running rev2，随后见到 failed rev4；accepted_at
`2026-09-21T17:33:11.578322Z`，completed_at `2026-09-21T17:34:31.335614Z`。
不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev225/recovery74/failed rev4；pause-terminal 生成 rev226 disabled/hash
`sha256:1e36c37cb4db78b2543624dde191ef422d9d4f0968c105ed3d9f1cf1a1e25c18`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0、worker=0、18181=0，Host PID 48103 仍在。
注意终态为 **rev4**，guard overlay 仍需 predecessor_view revision=4。本提交完成后自动进入
DB 正式退休与 DC direct successor。不使用定时 wake。本波无页面改动。退休 preflight 前不得
创建 `replacement-dc`。
