# DC 保存快照恢复正式终态验证（2026-09-21）

## 结论

`DC_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`6092d972-5734-44f1-abe4-56020afb2b4d` 正式 failed **rev4**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition
已推进到 rev229 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。本波从
DB installation `aaaa1ac1-2c35-4c35-8e7b-3ed6cd47f9c8` rev226/recovery74 转入 DC。
本波无页面改动，未开浏览器。

## 1/6 plan 与基线

HEAD `a97cdf7e`；DC `02d39eb8-174e-432f-9776-57de7c4436c8` / generation
`bd59503f-eb9e-4fe6-a09d-a92a3b924682`，binding rev6/epoch3 ready、九路 rev288/group315、
唯一 Host PID 51083；definition 为 DB `aaaa1ac1-2c35-4c35-8e7b-3ed6cd47f9c8` rev226
disabled、recovery74、attempt=0，12/12 与零副作用。configuration rev1 已引用
RuntimePolicy rev11。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；
`/v1/health`=200，prepare/schedule-ingest/controls 各确认 12 项，随后 18181 python PID 52520
SIGTERM 释放，第二 Host=0，PID 51083 保持在线。prepare 在 binding rev6/epoch3 上一次通过，
previewHash `sha256:5feaff1d1edf0c8938dfce1e0e9154b2b663bbe69c81571ab2e9c17c31448026`。

## 3/6 冻结输入转移

transfer 生成 rev227 disabled/hash
`sha256:2a866395cafae6c0f3cb2fa02ccebe2c14f105896140443eb5c85720800980d3`；
renew 生成 recovery75/hash
`sha256:21518179c91919d832a5130e47079fdf0395802e3f738be25df26436071df757`；
enable 生成 rev228 enabled/hash
`sha256:4614c3e987432d49e2326698c79c7b8c65d325d8cad0f3cd575d823f282f5b02`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
各阶段 sourceReads=0。

## 4/6 唯一自然 worker

Lease `A0V-DC-SNAPSHOT-WORKER-20260921` 已在 worker 启动前登记；唯一 worker PID 53063
自然创建上述 attempt，幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样见 running rev2，随后见到 failed rev4；accepted_at
`2026-09-21T18:03:16.572281Z`，completed_at `2026-09-21T18:04:36.794590Z`。
不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev228/recovery75/failed rev4；pause-terminal 生成 rev229 disabled/hash
`sha256:ca50bd7d360871e8a5d016361ce6faee27a683b1401bc822822f1e71edea9781`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0、worker=0、18181=0，Host PID 51083 仍在。
注意终态为 **rev4**，guard overlay 仍需 predecessor_view revision=4。本提交完成后自动进入
DC 正式退休与 DD direct successor。不使用定时 wake。本波无页面改动。退休 preflight 前不得
创建 `replacement-dd`。
