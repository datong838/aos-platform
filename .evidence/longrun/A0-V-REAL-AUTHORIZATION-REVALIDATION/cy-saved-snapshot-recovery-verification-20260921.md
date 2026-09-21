# CY 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CY_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`35c2b886-7d38-4ca7-9db6-3f90815420a2` 正式 failed **rev4**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition
已推进到 rev217 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。本波从
CX installation `2e374e12-7523-466d-aed7-bdabe8b69aff` rev214/recovery70 转入 CY。
本波无页面改动，未开浏览器。

## 1/6 plan 与基线

HEAD `b0d34938`；CY `917cd341-96a5-4428-9508-03c716c587ad` / generation
`a2fdbdb1-430c-417b-969d-6bd30874d38c`，binding rev6/epoch3 ready、九路 rev276/group303、
唯一 Host PID 39950；definition 为 CX `2e374e12-7523-466d-aed7-bdabe8b69aff` rev214
disabled、recovery70、attempt=0，12/12 与零副作用。configuration rev1 已引用
RuntimePolicy rev11。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；
`/v1/health`=200，prepare/schedule-ingest/controls 各确认 12 项，随后 18181 python PID 41859
SIGTERM 释放，第二 Host=0，PID 39950 保持在线。prepare 在 binding rev6/epoch3 上一次通过，
previewHash `sha256:d3777af290048c51024b8baf50655274561b22cd11c2cddfbd05da69dc988339`。

## 3/6 冻结输入转移

transfer 生成 rev215 disabled/hash
`sha256:3f4da61806522df14440a5d51ebedb7964afaba376325a3d9d8099081c2e957d`；
renew 生成 recovery71/hash
`sha256:3f085ba307099ce825c33f8b75c8a5a7f62da436ae0b134c3825e3e050ea8131`；
enable 生成 rev216 enabled/hash
`sha256:fdfb6e2b90530ef07c589c912dd03df2e1e02ad317b06af8122700bb0f256a43`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
各阶段 sourceReads=0。

## 4/6 唯一自然 worker

Lease `A0V-CY-SNAPSHOT-WORKER-20260921` 已在 worker 启动前登记；唯一 worker PID 42326
自然创建上述 attempt，幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样见 running rev2，随后见到 failed rev4；accepted_at
`2026-09-21T16:12:39.581186Z`，completed_at `2026-09-21T16:13:59.266417Z`。
不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev216/recovery71/failed rev4；pause-terminal 生成 rev217 disabled/hash
`sha256:d2a8c307d843b61790b18159920ca1097fb505d501fbc7e587ad127a5bc56a71`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0、worker=0、18181=0，Host PID 39950 仍在。
注意终态为 **rev4**，guard overlay 仍需 predecessor_view revision=4。本提交完成后自动进入
CY 正式退休与 CZ direct successor。不使用定时 wake。本波无页面改动。退休 preflight 前不得
创建 `replacement-cz`。
