# CI 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CI_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`4c67a2b5-34a6-47f7-9cc6-e59ce718d491` 正式 failed rev4，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition
已推进到 rev172 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。

## 1/6 plan 与基线

HEAD `64084809`；CI `1b9f500d-48a0-4f2c-8284-3db26e5cd4e7` / generation
`8de8994b-ad87-4039-a851-d944153bca08`，binding rev6/epoch3 ready、九路 rev228/group255、
唯一 Host PID 85436；definition rev169 disabled、recovery55、attempt=0，12/12 与零副作用。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；
`/v1/health` 与 OpenAPI=200，prepare/schedule-ingest/controls 各确认 12 项，随后 18181 释放，
第二 Host=0，PID 85436 保持在线。

## 3/6 冻结输入转移

transfer 生成 rev170 disabled/hash
`sha256:a97a5142d4abe011df8381913d26b5e69c53ac5589073ac1ea26ca73aecd44bf`；
renew 生成 recovery56/hash
`sha256:d32b15b1aa187d82bbd8fc190c565c560e6e155217d9f1a5f127200bc6f0fd99`；
enable 生成 rev171 enabled/hash
`sha256:aef7911a77514d5f37ebf10ea746a816feff0fdb22e3e433291b794f6dad0a1b`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
各阶段 sourceReads=0。

## 4/6 唯一自然 worker

Lease `A0V-CI-SNAPSHOT-WORKER-20260921` 已在 worker 启动前登记；唯一 worker PID 87456
自然创建上述 attempt，幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样先见 running rev2，90 秒见 failed rev4；accepted_at
`2026-09-21T08:08:23.557012Z`，completed_at `2026-09-21T08:09:48.986464Z`。
不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev171/recovery56/failed rev4；pause-terminal 生成 rev172 disabled/hash
`sha256:5824326a864278441eacd14acb14a9ba7c02d5325377c9db4ebf5785fd6e3aef`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0、worker=0、18181=0，Host PID 85436 仍在。
下一波为 CI 正式退休与 CJ direct successor。本提交完成后自动进入该波。
