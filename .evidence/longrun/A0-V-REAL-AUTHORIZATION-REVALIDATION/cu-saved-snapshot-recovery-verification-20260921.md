# CU 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CU_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`e845cb50-44dd-489c-a85d-85a8932b4d0f` 正式 failed **rev5**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition
已推进到 rev205 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。本波从
CT installation `b4847c85-b452-4c87-bf56-8a57bc9f8d25` rev202/recovery66 转入 CU。
本波无页面改动，未开浏览器。

## 1/6 plan 与基线

HEAD `e4aab6f0`；CU `2c2d5506-1f80-4557-bf4b-00ead0258002` / generation
`bcaa7ea0-62b1-4238-8615-28db45e3014e`，binding rev6/epoch3 ready、九路 rev264/group291、
唯一 Host PID 22753；definition 为 CT `b4847c85-b452-4c87-bf56-8a57bc9f8d25` rev202
disabled、recovery66、attempt=0，12/12 与零副作用。configuration rev1 已引用
RuntimePolicy rev11。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；
`/v1/health`=200，prepare/schedule-ingest/controls 各确认 12 项，随后 18181 python PID 25307
SIGTERM 释放，第二 Host=0，PID 22753 保持在线。prepare 在 binding rev6/epoch3 上一次通过，
previewHash `sha256:b948db7fe72d353527942953a6a99d78ed2db39789dd108a06dada780d712c05`。

## 3/6 冻结输入转移

transfer 生成 rev203 disabled/hash
`sha256:bd0d9b15e194bf7d84f5558edb87a8e60f348ba81abf74d6e7d5872546fed9ec`；
renew 生成 recovery67/hash
`sha256:7dcfc71097e84bc4b25529a1c70a98904768ea1655b037bb777c24cae51ab3b9`；
enable 生成 rev204 enabled/hash
`sha256:c2d2b40d01e40c8566c7a9185a9f0c0036b4b71702dea6a08e66770095ac29f9`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
各阶段 sourceReads=0。

## 4/6 唯一自然 worker

Lease `A0V-CU-SNAPSHOT-WORKER-20260921` 已在 worker 启动前登记；唯一 worker PID 25951
自然创建上述 attempt，幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样见 running rev2，随后见 running rev3，再见到 failed rev5；accepted_at
`2026-09-21T14:11:41.195104Z`，completed_at `2026-09-21T14:13:12.748220Z`。
不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev204/recovery67/failed rev5；pause-terminal 生成 rev205 disabled/hash
`sha256:b341ed9ef3772e4990f9631820897e7623f65099a3d795d35fa13ad58d7a2525`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0、worker=0、18181=0，Host PID 22753 仍在。
注意终态为 **rev5**，guard overlay 仍需 predecessor_view revision=4。本提交完成后自动进入
CU 正式退休与 CV direct successor。不使用定时 wake。本波无页面改动。
