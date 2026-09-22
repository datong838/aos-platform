# DG 保存快照恢复正式终态验证（2026-09-22）

## 结论

`DG_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`6e9e2fc8-d598-4e61-a6f0-d265ef7bceed` 正式 failed **rev4**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；definition 已推进到 rev241
disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。本波从 DF
installation `a0639f78-af04-4249-97f6-d8507de45f44` rev238/recovery78 转入 DG。
本波无页面改动，未开浏览器。

## 1/6 plan 与基线

HEAD `6b78e6b2`；DG `d551d104-f240-4b27-b738-1ef47129b5a4` / generation
`6c1780ab-746b-4303-a9ad-dc30039af8a4`，binding rev6/epoch3 ready、九路 rev300/group327、
唯一 Host PID 82684；definition 为 DF rev238 disabled、recovery78、attempt=0，12/12 与
零副作用。

## 2/6 纯 HTTP 18181

check/serve Cron=false、snapshot worker=false、进程内 Host=false；prepare/schedule/controls
各 12 项；随后 18181 SIGTERM，Host 82684 保持唯一。

## 3/6 冻结输入转移

transfer rev239/`sha256:5e430daec21b18fd21aeb54530b1b7821fa417646bd1f86aafa2e9ae329c1acd`；
renew recovery79/`sha256:1c1e3cd66d597f5157eb6be4f4d6a00a9b50f5d077c5329f026247398d5f6ca4`；
enable rev240/`sha256:f4e6908c18e97aeacd5ec84e32fa46df6023a01ac2c24d510d3aa260217ffe24`；
sourceReads=0。

## 4–5/6 唯一自然 attempt

唯一 worker 经 supervisor 启动；唯一 attempt `6e9e2fc8…` 自然 terminal（attemptCount=1）；
未启动第二 worker。accepted_at `2026-09-22T03:15:29.984849Z`；幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`；request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。Lease
`A0V-DG-SNAPSHOT-WORKER-20260922` 已登记（docs，不进本 commit）。终态 revision=**4**。

## 6/6 终态

pause-terminal 经 exact guard 冻结 FAILED_FREEZE_BOUNDARY，生成 rev241 disabled/hash
`sha256:7831f6f90d84e4e8ef7881fd6215a3334439a26e370c7bfab168aca1f2f38222`。
12/12、Store=0、ecom_link=0、canary=0、18181=0，Host 82684 仍在。下一波：DG 正式退休与
DH direct successor；退休 preflight 前不得创建 `replacement-dh`。
