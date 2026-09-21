# CH 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CH_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`0be8900c-4e4f-41c7-a93b-7dbfecb2bfe6` 正式 failed rev4，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition
已推进到 rev169 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。

## 1/6 plan 与基线

HEAD `dc774180`；CH `990f96f7-764e-4002-b691-fc5eb8d4335c` / generation
`0521ccf8-304a-45b3-b820-dc6ebd64b51b`，binding rev6/epoch3 ready、九路 rev225/group252、
唯一 Host PID 83095；definition rev166 disabled、recovery54、attempt=0，12/12 与零副作用。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；
`/v1/health` 与 OpenAPI=200，prepare/schedule-ingest/controls 各确认 12 项，随后 18181 释放，
第二 Host=0，PID 83095 保持在线。

## 3/6 冻结输入转移

transfer 生成 rev167 disabled/hash
`sha256:f420df4215bc6ac341a2a19e88cb47810e96633f89abd28d336de1403bca1f4c`；
renew 生成 recovery55/hash
`sha256:9b479ea57323740d9fc9afd4a74474a32e405dbbe0b68cc675edbc2bcefc7ebb`；
enable 生成 rev168 enabled/hash
`sha256:d55f5b14f3f1c33a2cc0c03696334a8eae00cd393a957dc7963d0192d9aa52c8`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
各阶段 sourceReads=0。

## 4/6 唯一自然 worker

Lease `A0V-CH-SNAPSHOT-WORKER-20260921` 已在 worker 启动前登记；唯一 worker PID 84695
自然创建上述 attempt，幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样先见 running rev2，90 秒见 failed rev4；accepted_at
`2026-09-21T07:40:01.123484Z`，completed_at `2026-09-21T07:41:25.351203Z`。
不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev168/recovery55/failed rev4；pause-terminal 生成 rev169 disabled/hash
`sha256:807d42c9500373612589a1ba0d5f436df8d064ef6190b9b2a9c3e58474a127bd`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0、worker=0、18181=0，Host PID 83095 仍在。
下一波为 CH 正式退休与 CI direct successor。本提交完成后自动进入该波。
