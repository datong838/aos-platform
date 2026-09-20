# CC 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CC_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`74ee33d8-b0d4-444a-9c01-ba31e9358552` 正式 failed rev4，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition 已推进到
rev154 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。

## 1/6 plan 与基线

HEAD `ec90af79`；CC `03942567-0f78-4530-b9dd-634bec59c780` / generation
`c1ffee4f-c13b-4d1a-93d2-c3b35bd66ca2`，binding rev6/epoch3 ready、九路 rev210/group237、
唯一 Host PID 38020；definition rev151 disabled、recovery49、attempt=0，12/12 与零副作用。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；OpenAPI=200，
prepare/schedule-ingest/controls 各确认 12 项，随后 18181 释放，第二 Host=0。

## 3/6 冻结输入转移

transfer 生成 rev152 disabled/hash `sha256:221adb0e02fee0e4dae6e7caff8f6d53592cb59f12078d4b5c48b96183f9d079`；
renew 生成 recovery50/hash `sha256:bd94a859c10729c3b988c714a29441c823dcaab85f33c005f69d7aecdd25cad8`；
enable 生成 rev153 enabled/hash `sha256:616eae11453d44f6064a6811c2bc2e180c937589c5e2f170b49588a7c751aa6e`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，各阶段 sourceReads=0。

## 4/6 唯一自然 worker

唯一 worker PID 40667；自然创建上述 attempt，幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样先见 running rev2，90 秒见 failed rev4；accepted_at `2026-09-20T20:11:30.902195Z`，
completed_at `2026-09-20T20:12:51.929911Z`。不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev153/recovery50/failed rev4；兼容别名缺失首次只读校验 fail-closed，未写入，最小修复后通过。
pause-terminal 生成 rev154 disabled/hash `sha256:50d59d0646f3840e9e4eca7f0eca318cf90fc6f93c0deb46aa12fce166258e4b`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、projection pending=0、
canary=0、worker=0、18181=0。下一波自动执行 CC 正式退休与 CD direct successor。
