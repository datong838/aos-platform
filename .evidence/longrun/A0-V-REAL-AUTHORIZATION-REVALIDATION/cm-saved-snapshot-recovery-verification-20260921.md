# CM 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CM_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`da4fed10-4cdc-4147-8595-d2f40c568419` 正式 failed **rev4**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition
已推进到 rev184 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。
pause-terminal 已先于 guard 落盘，guard 对共享 CB classify 叠加
`definitionState=enabled` / `definitionRevision=150` / `recoveryRevision=49` /
`revision=4`，live 权威仍是 rev184 disabled / recovery60 / failed rev4。

## 1/6 plan 与基线

HEAD `5b47dd48`；CM `b52c8e1c-a343-4ef4-b106-38d859ba9677` / generation
`d3ec88cc-a05a-4895-bc27-c983a367a9a8`，binding rev6/epoch3 ready、九路 rev240/group267、
唯一 Host PID 96921；definition rev181 disabled、recovery59、attempt=0，12/12 与零副作用。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；
`/v1/health` 与 OpenAPI=200，prepare/schedule-ingest/controls 各确认 12 项，随后 18181 释放，
第二 Host=0，PID 96921 保持在线。

## 3/6 冻结输入转移

transfer 生成 rev182 disabled/hash
`sha256:9f287f1df9e3069bec47be29b7b52a14d76b19f4682be038543c034277131a1a`；
renew 生成 recovery60/hash
`sha256:f372ccc196603b610e1a32c0323e3deb2bb43ef1dae561123adc6b7cfdc3b083`；
enable 生成 rev183 enabled/hash
`sha256:4786525ddb06e95af1bf005997fbdf770e72250334408971b133e8d77ee38e63`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
各阶段 sourceReads=0。

## 4/6 唯一自然 worker

Lease `A0V-CM-SNAPSHOT-WORKER-20260921` 已在 worker 启动前登记；唯一 worker PID 98778
自然创建上述 attempt，幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

唯一 attempt accepted_at `2026-09-21T10:07:17.339727Z`，completed_at
`2026-09-21T10:08:45.120323Z`，elapsed ~90s，正式 failed rev4。不是 deadline 情形；
worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

pause-terminal 生成 rev184 disabled/hash
`sha256:7c559d8b95bae85dca4bea7e66a398b93cd6d7c8f47a48f0948321eb717a9dec`，outcome
`CM_SAVED_SNAPSHOT_TERMINAL_RECOVERY_PAUSED`，不可重发。exact guard 冻结
rev184/recovery60/failed rev4 / 九路 240/267。最终 12 members、12 running Run、12
Dataset Receipt、Store Receipt=0、`ecom_link`=0、projection pending=0、canary=0、
worker=0、18181=0，Host PID 96921 仍在。累计测试 189 passed。
下一波为 CM 正式退休与 CN direct successor。本提交完成后自动进入该波。
