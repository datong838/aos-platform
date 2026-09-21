# CD 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CD_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`3eae682d-fddb-4b3b-a7b0-da0eb91152d2` 正式 failed rev4，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition 已推进到
rev157 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。

## 1/6 plan 与基线

HEAD `16a5c6e6`；CD `01b41c17-fce2-4bcf-8d9e-a48d2d4bf743` / generation
`22639b06-1211-424d-9f64-696822e0add4`，binding rev6/epoch3 ready、九路 rev213/group240、
唯一 Host PID 58751；definition rev154 disabled、recovery50、attempt=0，12/12 与零副作用。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；health/OpenAPI=200，
prepare/schedule-ingest/controls 各确认 12 项，随后 18181 释放，第二 Host=0。

## 3/6 冻结输入转移

transfer 生成 rev155 disabled/hash `sha256:e127f7ea3572d13ab44d6a0e014f7823865e1a189cf4090d6276814d4c0d6749`；
renew 生成 recovery51/hash `sha256:b7855ac0261f076c33b84af83a3b2b0f05348033c394238a71cfa05e7350daeb`；
enable 生成 rev156 enabled/hash `sha256:eac4db8f6c417a110397a4e590682c1dca603676003e9b0039c3e5161ee26806`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，各阶段 sourceReads=0。

## 4/6 唯一自然 worker

首次 worker 在 attempt=0 前被缺失 CD Lease 安全拒绝，无业务写入；外部 Lease 以 apply_patch 新增并校验 JSON 后，
唯一 worker PID 61507 自然创建上述 attempt，幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样先见 running rev2，90 秒见 failed rev4；accepted_at `2026-09-21T01:59:47.364725Z`，
completed_at `2026-09-21T02:01:13.968581Z`。不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev156/recovery51/failed rev4；pause-terminal 生成 rev157 disabled/hash
`sha256:e019ab300a0a6cd590e00b92a4207279c0d48fc1a1426dce156f2ddd3bbbf282`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、projection pending=0、
canary=0、worker=0、18181=0。下一波自动执行 CD 正式退休与 CE direct successor。
