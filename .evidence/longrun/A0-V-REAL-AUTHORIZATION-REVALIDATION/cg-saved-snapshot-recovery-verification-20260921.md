# CG 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CG_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`f7b2fc7f-9bce-4102-8f5b-48ec8879ae55` 正式 failed rev4，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition
已推进到 rev166 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。

## 1/6 plan 与基线

HEAD `ad9e092f`；CG `8f42819c-0fc7-48cf-a5c4-9ba96894a6f5` / generation
`3ed300fa-5fff-4949-9fb0-1926412e51ae`，binding rev6/epoch3 ready、九路 rev222/group249、
唯一 Host PID 77505；definition rev163 disabled、recovery53、attempt=0，12/12 与零副作用。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；
`/v1/health` 与 OpenAPI=200，prepare/schedule-ingest/controls 各确认 12 项，随后 18181 释放，
第二 Host=0，PID 77505 保持在线。

## 3/6 冻结输入转移

transfer 生成 rev164 disabled/hash
`sha256:b0645219d4b18a2cdd58d611a174370b8701795fd72bfa809a0a59c5cc58fa68`；
renew 生成 recovery54/hash
`sha256:c9536786347d902ff87a9a06613df5644dfb6d9597afbf39733cc6aa0539ed58`；
enable 生成 rev165 enabled/hash
`sha256:8bcd7283096151d51148db4ff88afb2a396351a439ae5fc2e40f37dc05215437`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
各阶段 sourceReads=0。

## 4/6 唯一自然 worker

Lease `A0V-CG-SNAPSHOT-WORKER-20260921` 已在 worker 启动前登记；唯一 worker PID 82432
自然创建上述 attempt，幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样先见 running rev2，90 秒见 failed rev4；accepted_at
`2026-09-21T07:14:08.532998Z`，completed_at `2026-09-21T07:15:38.581597Z`。
不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev165/recovery54/failed rev4；pause-terminal 生成 rev166 disabled/hash
`sha256:ae9eadb5dd835409985a729ae887cfe604a34c5888b4beeae9908590a71a2965`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0、worker=0、18181=0，Host PID 77505 仍在。
下一波为 CG 正式退休与 CH direct successor。本提交完成后自动进入该波。
