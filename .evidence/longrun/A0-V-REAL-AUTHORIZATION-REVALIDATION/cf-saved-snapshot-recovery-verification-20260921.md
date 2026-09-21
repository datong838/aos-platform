# CF 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CF_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`d16e9452-0f4b-40cc-97f0-316841dfee29` 正式 failed rev4，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition 已推进到
rev163 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。

## 1/6 plan 与基线

HEAD `f04990a0`；CF `8cf0c597-cf81-4fa5-b1ff-f27e3537a94c` / generation
`88996259-ad79-4aa6-962c-c29a24559db8`，binding rev6/epoch3 ready、九路 rev219/group246、
唯一 Host PID 73889；definition rev160 disabled、recovery52、attempt=0，12/12 与零副作用。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；`/v1/health` 与
OpenAPI=200，prepare/schedule-ingest/controls 各确认 12 项，随后 18181 释放，第二 Host=0，PID 73889 保持在线。

## 3/6 冻结输入转移

transfer 生成 rev161 disabled/hash `sha256:8848e057c398d32ed9ca439583189f1ca3baf27f49d8421f6db3b9b1dbb5a7a6`；
renew 生成 recovery53/hash `sha256:de7600063dce230701986d346b616e9b4a9bbe185d01998541cb67128b300a42`；
enable 生成 rev162 enabled/hash `sha256:1a5ede8d241c7648b98da9ceac9616a1cfcc850705934d8d381a61ef8b6b0226`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，各阶段 sourceReads=0。

## 4/6 唯一自然 worker

Lease `A0V-CF-SNAPSHOT-WORKER-20260921` 已在 worker 启动前登记；唯一 worker PID 76221 自然创建上述
attempt，幂等键 `snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样先见 running rev2，90 秒见 failed rev4；accepted_at `2026-09-21T05:40:13.964604Z`，
completed_at `2026-09-21T05:41:34.670329Z`。不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev162/recovery53/failed rev4；pause-terminal 生成 rev163 disabled/hash
`sha256:df8c70e88712b6d0092121304f8a98577897ea67e8d13c9226efa2bc4c2644b7`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、projection pending=0、
canary=0、worker=0、18181=0，Host PID 73889 仍在。目标回归 `140 passed, 7 warnings`。
下一波为 CF 正式退休与 CG direct successor。本提交完成后自动进入该波。
