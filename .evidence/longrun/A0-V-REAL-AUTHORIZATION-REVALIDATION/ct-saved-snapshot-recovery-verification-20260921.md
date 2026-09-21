# CT 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CT_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`5b22aca6-70b5-46e0-b5aa-0f477964df96` 正式 failed **rev5**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition
已推进到 rev202 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。本波从
CS installation `ff72acba-1e59-4da3-b92a-18737e18e9d2` rev199/recovery65 转入 CT。

## 1/6 plan 与基线

HEAD `39ca44b5`；CT `b4847c85-b452-4c87-bf56-8a57bc9f8d25` / generation
`0d234db2-8b76-4ec8-a14a-a8c6eec9bbc6`，binding rev6/epoch3 ready、九路 rev261/group288、
唯一 Host PID 19682；definition 为 CS `ff72acba-1e59-4da3-b92a-18737e18e9d2` rev199
disabled、recovery65、attempt=0，12/12 与零副作用。configuration rev1 已引用
RuntimePolicy rev11。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；
`/v1/health`=200，prepare/schedule-ingest/controls 各确认 12 项，随后 18181 python PID 21691
SIGTERM 释放，第二 Host=0，PID 19682 保持在线。prepare 在 binding rev6/epoch3 上一次通过，
previewHash `sha256:a083d62e425444d5ef95e3ab727fe8bd0ecf31c0e33c3e86055b2a421445dfeb`。

## 3/6 冻结输入转移

transfer 生成 rev200 disabled/hash
`sha256:7f3d75a79d251c3b1d2fa65c658bc48d865a1e7a9c83b57a0211edb3640cb75d`；
renew 生成 recovery66/hash
`sha256:8090c986e3c22b2548a14e793dc8376230bdb262aedd84f10083e2139605230a`；
enable 生成 rev201 enabled/hash
`sha256:cc984662b1da96c5a08a37fb639d7ea2f4718514ee946f55083607bb7a31d868`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
各阶段 sourceReads=0。

## 4/6 唯一自然 worker

Lease `A0V-CT-SNAPSHOT-WORKER-20260921` 已在 worker 启动前登记；唯一 worker PID 22054
自然创建上述 attempt，幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样见 running rev2，随后见 running rev4，再见到 failed rev5；accepted_at
`2026-09-21T13:43:31.962740Z`，completed_at `2026-09-21T13:45:03.714078Z`。
不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev201/recovery66/failed rev5；pause-terminal 生成 rev202 disabled/hash
`sha256:9b95e4daa15bfb4dc5783c42a8b8557e05bd96522dd4bed452882d349ebcd0f5`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0、worker=0、18181=0，Host PID 19682 仍在。
注意终态为 **rev5**，guard overlay 仍需 predecessor_view revision=4。本提交完成后自动进入
CT 正式退休与 CU direct successor。不使用定时 wake。
