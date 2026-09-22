# DD 保存快照恢复正式终态验证（2026-09-22）

## 结论

`DD_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`a2396b18-ade6-4c91-912d-1c953d8e17b5` 正式 failed **rev4**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；definition 已推进到 rev232
disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。本波从 DC
installation `02d39eb8-174e-432f-9776-57de7c4436c8` rev229/recovery75 转入 DD。
本波无页面改动，未开浏览器。

## 1/6 plan 与基线

HEAD `5d30d3b4`；DD `6e05658b-5d0a-40ae-ab8e-81fcca5269db` / generation
`422d2d5b-752a-4182-b1e8-831a8f63c2a1`，binding rev6/epoch3 ready、九路 rev291/group318、
唯一 Host PID 70991；definition 为 DC rev229 disabled、recovery75、attempt=0，12/12 与
零副作用。configuration rev1 已引用 RuntimePolicy rev11。

## 2/6 纯 HTTP 18181

check/serve Cron=false、snapshot worker=false、进程内 Host=false；prepare/schedule/controls
各 12 项；previewHash `sha256:573ec44a1e91938bf66a0da53fec3e5f36bacf97c2040b324efbd7ab761b34ec`；
随后 18181 SIGTERM，Host 70991 保持唯一。

## 3/6 冻结输入转移

transfer rev230/`sha256:a0163aa4f8d439058aa83f559a80c1ae2e5ea883cd585afe95558d58f5e5fbdb`；
renew recovery76/`sha256:8227326046fa3efd5f2449b35e0c497fe1b91b77ac253222e617969589879e2a`；
enable rev231/`sha256:606b156723373161c02cde9ecb2b9f481b7323cef16829df2a6579860e573cdb`；
sourceReads=0。

## 4–5/6 唯一自然 attempt

enable 后唯一 attempt 自然出现并在独立 supervisor 启动前已 terminal（attemptCount=1）；
未启动第二 worker。accepted_at `2026-09-22T01:43:06.412357Z`；幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`；request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。Lease
`A0V-DD-SNAPSHOT-WORKER-20260922` 已登记（docs，不进本 commit）。

## 6/6 终态

pause-terminal 经 exact guard 冻结 FAILED_FREEZE_BOUNDARY，生成 rev232 disabled/hash
`sha256:a3cabf03a18a98c8c18dbd442d2f9a494695bcd854c2ac34504198ba438b3da9`。
12/12、Store=0、ecom_link=0、canary=0、18181=0，Host 70991 仍在。下一波：DD 正式退休与
DE direct successor；退休 preflight 前不得创建 `replacement-de`。
