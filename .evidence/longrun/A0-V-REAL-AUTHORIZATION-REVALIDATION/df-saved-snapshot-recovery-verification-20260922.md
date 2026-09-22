# DF 保存快照恢复正式终态验证（2026-09-22）

## 结论

`DF_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`20318703-942c-49da-8d3b-98409c590c05` 正式 failed **rev4**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；definition 已推进到 rev238
disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。本波从 DE
installation `5d993078-18ec-4302-9286-7081a1463cc0` rev235/recovery77 转入 DF。
本波无页面改动，未开浏览器。

## 1/6 plan 与基线

HEAD `bfc436b7`；DF `a0639f78-af04-4249-97f6-d8507de45f44` / generation
`ec18c8c6-2694-44c1-a9c9-ea79ea606e45`，binding rev6/epoch3 ready、九路 rev297/group324、
唯一 Host PID 79478；definition 为 DE rev235 disabled、recovery77、attempt=0，12/12 与
零副作用。

## 2/6 纯 HTTP 18181

check/serve Cron=false、snapshot worker=false、进程内 Host=false；prepare/schedule/controls
各 12 项；随后 18181 SIGTERM，Host 79478 保持唯一。

## 3/6 冻结输入转移

transfer rev236/`sha256:4e0f8de8a56c3b324220b145f75808e66aa0f31ffc4478c209d15a3521a9dd86`；
renew recovery78/`sha256:16ec5ac89f55dd59c04a042c0638b799b58cdd068fa5ae4d300736a6c1ff2a10`；
enable rev237/`sha256:223dc8c102e18d2a97044586a1623c91621de9cec6deff915c99ec295e98dad7`；
sourceReads=0。

## 4–5/6 唯一自然 attempt

唯一 worker 经 supervisor 启动；唯一 attempt `20318703…` 自然 terminal（attemptCount=1）；
未启动第二 worker。accepted_at `2026-09-22T02:43:15.913972Z`；幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`；request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。Lease
`A0V-DF-SNAPSHOT-WORKER-20260922` 已登记（docs，不进本 commit）。终态 revision=**4**。

## 6/6 终态

pause-terminal 经 exact guard 冻结 FAILED_FREEZE_BOUNDARY，生成 rev238 disabled/hash
`sha256:b67650f22db1c138fbfe2c9114d35aa9a91433a44c147abdb143b5121e5bd736`。
12/12、Store=0、ecom_link=0、canary=0、18181=0，Host 79478 仍在。下一波：DF 正式退休与
DG direct successor；退休 preflight 前不得创建 `replacement-dg`。
