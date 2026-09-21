# CN 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CN_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`1cf52d77-baa9-49a5-9315-d705b864c8a0` 正式 failed **rev5**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition
已推进到 rev187 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。

## 1/6 plan 与基线

HEAD `f348c90a`；CN `1366f4dd-47d9-42c1-b26a-759c7bd556da` / generation
`cd0601e0-2668-496d-9f93-561d2e69a170`，binding rev6/epoch3 ready、九路 rev243/group270、
唯一 Host PID 519；definition rev184 disabled、recovery60、attempt=0，12/12 与零副作用。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；
`/v1/health` 与 OpenAPI=200，prepare/schedule-ingest/controls 各确认 12 项，随后 18181 释放，
第二 Host=0，PID 519 保持在线。

## 3/6 冻结输入转移

transfer 生成 rev185 disabled/hash
`sha256:750424897154bf30db2652ad9e804985779752174f0a0e8aadb883dca86d9885`；
renew 生成 recovery61/hash
`sha256:73a5a3bcbf2812dc4bddff81f8ef4cf62f712769286db3cfcebd26eb28cc04cb`；
enable 生成 rev186 enabled/hash
`sha256:c78b7669ba0ad70ccd7feb1022b005dd5157190d4ed9864b142c58128b6a9a1e`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
各阶段 sourceReads=0。

## 4/6 唯一自然 worker

Lease `A0V-CN-SNAPSHOT-WORKER-20260921` 已在 worker 启动前登记；唯一 worker PID 3039
自然创建上述 attempt，幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样见 running rev2，100 秒见 running rev3，150 秒见 failed rev5；accepted_at
`2026-09-21T10:43:40.480307Z`，completed_at `2026-09-21T10:45:13.169272Z`。
不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev186/recovery61/failed rev5；pause-terminal 生成 rev187 disabled/hash
`sha256:1679be118aa4fb1a2a3a5e2ce8347c46c08bbd45cfc9ec4ae359deb7204c56c1`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0、worker=0、18181=0，Host PID 519 仍在。
下一波为 CN 正式退休与 CO direct successor。本提交完成后自动进入该波。
