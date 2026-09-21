# CE 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CE_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`c1b948a7-faf2-4b92-8e8d-1f9d66b51201` 正式 failed rev4，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition 已推进到
rev160 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。

## 1/6 plan 与基线

HEAD `61958b3c`；CE `29d1b06d-3baa-4476-9cf8-5ea345d134c7` / generation
`e51d0010-d57f-4f5c-8f7e-7a1d732bebf7`，binding rev6/epoch3 ready、九路 rev216/group243、
唯一 Host PID 62103；definition rev157 disabled、recovery51、attempt=0，12/12 与零副作用。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；health/OpenAPI=200，
prepare/schedule-ingest/controls 各确认 12 项，随后 18181 释放，第二 Host=0，PID 62103 保持在线。

## 3/6 冻结输入转移

transfer 生成 rev158 disabled/hash `sha256:8dc4a3ed2d7507b3e53f06993fd96a25e983a81e2d4f1a46417abc61e8fc3af6`；
renew 生成 recovery52/hash `sha256:77be40f32ad75219d8b763b1c1b07c06867989a5783a92dd516bd44361d44ffd`；
enable 生成 rev159 enabled/hash `sha256:ed8e0c03560747c7815de3a1d3a34cdec21d2c351c4eeec87ea568b9a1840a85`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，各阶段 sourceReads=0。

## 4/6 唯一自然 worker

Lease `A0V-CE-SNAPSHOT-WORKER-20260921` 已在 worker 启动前登记；唯一 worker PID 72594 自然创建上述
attempt，幂等键 `snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样先见 running rev2，90 秒见 failed rev4；accepted_at `2026-09-21T05:09:58.938412Z`，
completed_at `2026-09-21T05:11:23.918780Z`。不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev159/recovery52/failed rev4；pause-terminal 生成 rev160 disabled/hash
`sha256:92f0f0b16bde8eb7da3602672c7d8bd032a41664ec4ea8f8bb61cc952de7996f`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、projection pending=0、
canary=0、worker=0、18181=0，Host PID 62103 仍在。目标回归 `133 passed, 7 warnings`。
下一波应为 CE 正式退休与 CF direct successor。按本波方案与用户指令，本提交完成后暂停，不自动启动 CF。
