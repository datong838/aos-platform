# CS 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CS_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`b7d12c25-6673-48b3-aaba-dc803edb9169` 正式 failed **rev5**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition
已推进到 rev199 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。本波从
CR installation `913cb7a1-4912-471a-abbf-452e3ce999a9` rev196/recovery64 转入 CS。

## 1/6 plan 与基线

HEAD `ccea6c1f`；CS `ff72acba-1e59-4da3-b92a-18737e18e9d2` / generation
`01a1719d-1109-440f-a233-1c5a6adb0d81`，binding rev6/epoch3 ready、九路 rev258/group285、
唯一 Host PID 16307；definition 为 CR `913cb7a1-4912-471a-abbf-452e3ce999a9` rev196
disabled、recovery64、attempt=0，12/12 与零副作用。configuration rev1 已引用
RuntimePolicy rev11。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；
`/v1/health`=200，prepare/schedule-ingest/controls 各确认 12 项，随后 18181 python PID 18088
SIGTERM 释放，第二 Host=0，PID 16307 保持在线。prepare 在 binding rev6/epoch3 上一次通过，
previewHash `sha256:592e5a9ae3e31d9914f63aa427a124a941d7661cf990b1e0350913b7e0daed0b`。

## 3/6 冻结输入转移

transfer 生成 rev197 disabled/hash
`sha256:4043701537f8acaefd25efd9a54d3c38157516095e9c910e0b6193c2cf488366`；
renew 生成 recovery65/hash
`sha256:d65a82d1bc3ffc049c3d0fe287707e894acd45456814575afdfa42b0290bf87c`；
enable 生成 rev198 enabled/hash
`sha256:884d79ed04a16d734edbde9cdb49c4532c0d0fad98701f28b975cfb84c44a3b2`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
各阶段 sourceReads=0。

## 4/6 唯一自然 worker

Lease `A0V-CS-SNAPSHOT-WORKER-20260921` 已在 worker 启动前登记；唯一 worker PID 18552
自然创建上述 attempt，幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样见 running rev2，随后见 running rev3，再见到 failed rev5；accepted_at
`2026-09-21T13:14:38.186769Z`，completed_at `2026-09-21T13:16:10.926345Z`。
不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev198/recovery65/failed rev5；pause-terminal 生成 rev199 disabled/hash
`sha256:54a2339e0bb2a23b30d721768077b79b76022202b2d5c95ca530a289afb30af5`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0、worker=0、18181=0，Host PID 16307 仍在。
注意终态为 **rev5**，guard overlay 仍需 predecessor_view revision=4。本提交完成后自动进入
CS 正式退休与 CT direct successor。不使用定时 wake。
