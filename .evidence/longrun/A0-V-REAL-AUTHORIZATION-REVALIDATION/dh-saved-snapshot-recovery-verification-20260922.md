# DH 保存快照恢复正式终态验证（2026-09-22）

## 结论

`DH_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`40429d74-6faf-4895-8b2a-b0cc69df35a3` 正式 failed **rev4**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；definition 已推进到 rev244
disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。本波从 DG
installation `d551d104-f240-4b27-b738-1ef47129b5a4` rev241/recovery79 转入 DH。
本波无页面改动，未开浏览器。

## 1/6 plan 与基线

HEAD `f59255db`；DH `10d583ad-96ee-4b1a-bb18-92e428abe16e` / generation
`107a24f5-691d-4f2a-9b46-4e7b21938146`，binding rev6/epoch3 ready、九路 rev303/group330、
唯一 Host PID 86843；definition 为 DG rev241 disabled、recovery79、attempt=0，12/12 与
零副作用。

## 2/6 纯 HTTP 18181

check/serve Cron=false、snapshot worker=false、进程内 Host=false；prepare/schedule/controls
各 12 项；随后 18181 SIGTERM，Host 86843 保持唯一。

## 3/6 冻结输入转移

transfer rev242/`sha256:75df67b91f3781b4f99cd02a1d15c6980b8060292e5b25a971b22837b8deef66`；
renew recovery80/`sha256:fb08b9f42322876be1e8d0f859852d5c6b5ff21d2cf720d003388534ffb69675`；
enable rev243/`sha256:9408a6cb3e28e00304be6e5a0156c49a2c7833ec5beeee776143ffb58794c5ed`；
sourceReads=0。

## 4–5/6 唯一自然 attempt

唯一 worker 经 supervisor 启动；唯一 attempt `40429d74…` 自然 terminal（attemptCount=1）；
未启动第二 worker。accepted_at `2026-09-22T03:39:32.183428Z`；幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`；request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。Lease
`A0V-DH-SNAPSHOT-WORKER-20260922` 已登记（docs，不进本 commit）。终态 revision=**4**。

## 6/6 终态

pause-terminal 经 exact guard 冻结 FAILED_FREEZE_BOUNDARY，生成 rev244 disabled/hash
`sha256:7cee5c0e24912051229a8fd77bf3012f71598d8cc7b06236631d76f64cc14196`。
12/12、Store=0、ecom_link=0、canary=0、18181=0，Host 86843 仍在。下一波：DH 正式退休与
DI direct successor；退休 preflight 前不得创建 `replacement-di`。
