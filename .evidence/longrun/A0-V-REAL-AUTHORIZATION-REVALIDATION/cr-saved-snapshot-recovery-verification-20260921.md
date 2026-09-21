# CR 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CR_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`11e98b8f-d898-4b1b-a6fc-c210bb44e5d7` 正式 failed **rev5**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition
已推进到 rev196 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。CQ 未接过
definition，本波按 AX 先例从仍冻结的 CP rev193/recovery63 转入 CR。

## 1/6 plan 与基线

HEAD `24b8fac0`；CR `913cb7a1-4912-471a-abbf-452e3ce999a9` / generation
`a4a16448-5581-4948-b962-777ff601e855`，binding rev6/epoch3 ready、九路 rev255/group282、
唯一 Host PID 12390；definition 仍为 CP `1d8b71c5-1cde-4d16-b16f-835f92bf8663` rev193
disabled、recovery63、attempt=0，12/12 与零副作用。configuration rev1 已引用
RuntimePolicy rev11。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；
`/v1/health` 与 OpenAPI=200，prepare/schedule-ingest/controls 各确认 12 项，随后 18181 释放，
第二 Host=0，PID 12390 保持在线。prepare 在 binding rev6/epoch3 上一次通过，证明 CQ 被拒的
J binding 合同已由 CR 当前策略切断。

## 3/6 冻结输入转移

transfer 生成 rev194 disabled/hash
`sha256:b39873341a7f66b52a49ddbb629ab2803eabfa99a2b01f7b8ea175a034c5f2b4`；
renew 生成 recovery64/hash
`sha256:a7ac1581109526f9ebcf492ab38264a892ca6ec732bbfd773c1fa8a8b388b4dd`；
enable 生成 rev195 enabled/hash
`sha256:733f8f7fe137e03162b128116bd70c95b7f31405dba7bca4d7747c246b00ad10`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
各阶段 sourceReads=0。

## 4/6 唯一自然 worker

Lease `A0V-CR-SNAPSHOT-WORKER-20260921` 已在 worker 启动前登记；唯一 worker PID 15199
自然创建上述 attempt，幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样见 running rev2，随后见 running rev4，再见到 failed rev5；accepted_at
`2026-09-21T12:43:03.165821Z`，completed_at `2026-09-21T12:44:34.404581Z`。
不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev195/recovery64/failed rev5；pause-terminal 生成 rev196 disabled/hash
`sha256:7800cc53151703efb5b85b9ef3652d79614745632475ec77846d4148cbc616b2`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0、worker=0、18181=0，Host PID 12390 仍在。
注意终态为 **rev5**，guard overlay 仍需 predecessor_view revision=4。本提交完成后自动进入
CR 正式退休与 CS direct successor。
