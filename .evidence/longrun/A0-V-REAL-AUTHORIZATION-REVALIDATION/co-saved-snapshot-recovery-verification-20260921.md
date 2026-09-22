# CO 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CO_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`f3061da8-baee-4b3a-8307-88d835d42cca` 正式 failed **rev4**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition
已推进到 rev190 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。

## 1/6 plan 与基线

HEAD `7c2c0665`；CO `648b267b-bb8f-4582-ab29-288279f534c7` / generation
`db428c1b-2fe4-4869-8a69-ddffaa909ba7`，binding rev6/epoch3 ready、九路 rev246/group273、
唯一 Host PID 4016；definition rev187 disabled、recovery61、attempt=0，12/12 与零副作用。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；
`/v1/health` 与 OpenAPI=200，prepare/schedule-ingest/controls 各确认 12 项，随后 18181 释放，
第二 Host=0，PID 4016 保持在线。

## 3/6 冻结输入转移

transfer 生成 rev188 disabled/hash
`sha256:d9543fd72f425c2fc93999592a38b60888867f6e5570265df61457d4a94d07cc`；
renew 生成 recovery62/hash
`sha256:d5159f331c3565a2968fe183945c952784060e6c16950a054443eb4f0665fccb`；
enable 生成 rev189 enabled/hash
`sha256:2f82f85e217a5b09661088811aeb7812b7abfce708f4c2069fc77aa0e684afbb`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
各阶段 sourceReads=0。

## 4/6 唯一自然 worker

Lease `A0V-CO-SNAPSHOT-WORKER-20260921` 已在 worker 启动前登记；唯一 worker PID 6130
自然创建上述 attempt，幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样见 running rev2，随后见 failed rev4；accepted_at
`2026-09-21T11:14:02.380249Z`，completed_at `2026-09-21T11:15:29.288768Z`。
不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev189/recovery62/failed rev4；pause-terminal 生成 rev190 disabled/hash
`sha256:5dcbb95bdc7a8d8740e279514b07cb0da084185cad71a73e62d99499454993f9`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0、worker=0、18181=0，Host PID 4016 仍在。
目标回归 `203 passed, 7 warnings`。下一波为 CO 正式退休与 CP direct successor。注意终态为 **rev4**，guard overlay 仍需
predecessor_view revision=4。本提交完成后自动进入该波。
