# CK 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CK_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`7c99b249-fc1e-4844-abc5-8b7cc268fd39` 正式 failed rev5，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition
已推进到 rev178 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。

## 1/6 plan 与基线

HEAD `61b78012`；CK `c1cb44ba-68ae-4d32-9974-5f031554fed2` / generation
`1edb1688-e2b6-42f0-b513-849ae372859e`，binding rev6/epoch3 ready、九路 rev234/group261、
唯一 Host PID 91080；definition rev175 disabled、recovery57、attempt=0，12/12 与零副作用。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；
`/v1/health` 与 OpenAPI=200，prepare/schedule-ingest/controls 各确认 12 项，随后 18181 释放，
第二 Host=0，PID 91080 保持在线。

## 3/6 冻结输入转移

transfer 生成 rev176 disabled/hash
`sha256:8b378de9553fa18226eafb972db10ae1168d48c0a9aad8491b387438b795d11f`；
renew 生成 recovery58/hash
`sha256:b2a6a614463c337ec75e54dcedd7269332f9f54c33c3005c2296b72965081eb8`；
enable 生成 rev177 enabled/hash
`sha256:a43eae9dd2b9a500941938f51f0806922dc26bd2b95e6126b36fdf9cfb614847`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
各阶段 sourceReads=0。

## 4/6 唯一自然 worker

Lease `A0V-CK-SNAPSHOT-WORKER-20260921` 已在 worker 启动前登记；唯一 worker PID 93411
自然创建上述 attempt，幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样见 running rev2，100 秒见 running rev3，150 秒见 failed rev5；accepted_at
`2026-09-21T09:15:37.460276Z`，completed_at `2026-09-21T09:17:08.296334Z`。
不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev177/recovery58/failed rev5；pause-terminal 生成 rev178 disabled/hash
`sha256:85bc2d60525a8ad8866655367d31e5df62eef90aea048fb5ae9897ac473b5ff4`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0、worker=0、18181=0，Host PID 91080 仍在。
下一波为 CK 正式退休与 CL direct successor。本提交完成后自动进入该波。
