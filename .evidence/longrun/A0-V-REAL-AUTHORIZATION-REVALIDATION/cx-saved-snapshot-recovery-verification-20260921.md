# CX 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CX_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`715c69b5-db78-4503-9f6e-2e6a5f132b1d` 正式 failed **rev4**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition
已推进到 rev214 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。本波从
CW installation `0d5d5a7f-6e40-4725-b337-b79acc7d896a` rev211/recovery69 转入 CX。
本波无页面改动，未开浏览器。

## 1/6 plan 与基线

HEAD `702a23e4`；CX `2e374e12-7523-466d-aed7-bdabe8b69aff` / generation
`222870ba-ad3c-4cf5-a6de-e1b3a52ab5bc`，binding rev6/epoch3 ready、九路 rev273/group300、
唯一 Host PID 36763；definition 为 CW `0d5d5a7f-6e40-4725-b337-b79acc7d896a` rev211
disabled、recovery69、attempt=0，12/12 与零副作用。configuration rev1 已引用
RuntimePolicy rev11。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；
`/v1/health`=200，prepare/schedule-ingest/controls 各确认 12 项，随后 18181 python PID 38712
SIGTERM 释放，第二 Host=0，PID 36763 保持在线。prepare 在 binding rev6/epoch3 上一次通过，
previewHash `sha256:58ae77a7a56da95d2823d6dd20c9232856ca29de99f84154de9841b12fe58b25`。

## 3/6 冻结输入转移

transfer 生成 rev212 disabled/hash
`sha256:5e325aef122e2addd93b2774fc8c7a59e8ea9ff321fbdc6d7c4b748f8ffb44ee`；
renew 生成 recovery70/hash
`sha256:46c6ad1eb001f60bbbb6028920be8457b5d99911d56e5e05411b11fd6cc3e068`；
enable 生成 rev213 enabled/hash
`sha256:fbb8bff81c3a49c330a50a9be74afb25bb31f0b69df947cf6cf8b67187336bb8`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
各阶段 sourceReads=0。

## 4/6 唯一自然 worker

Lease `A0V-CX-SNAPSHOT-WORKER-20260921` 已在 worker 启动前登记；唯一 worker PID 39093
自然创建上述 attempt，幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样见 running rev2，随后见到 failed rev4；accepted_at
`2026-09-21T15:46:10.694174Z`，completed_at `2026-09-21T15:47:34.222467Z`。
不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev213/recovery70/failed rev4；pause-terminal 生成 rev214 disabled/hash
`sha256:74a1bb4d5f9790c1aa09eccadf7735ff5ec7828c4b61b112a7466acadb7c5d6c`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0、worker=0、18181=0，Host PID 36763 仍在。
注意终态为 **rev4**，guard overlay 仍需 predecessor_view revision=4。本提交完成后自动进入
CX 正式退休与 CY direct successor。不使用定时 wake。本波无页面改动。
