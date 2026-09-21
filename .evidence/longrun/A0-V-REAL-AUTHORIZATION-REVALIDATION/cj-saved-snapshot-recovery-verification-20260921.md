# CJ 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CJ_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。唯一自然 attempt
`d0326f13-2ccb-49c0-ade9-0729dc188717` 正式 failed rev5，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；worker stop-only 退出，definition
已推进到 rev175 disabled。全过程未读取商城源数据、未调用 `run_definition`、未重发。

## 1/6 plan 与基线

HEAD `3681c30b`；CJ `184e0d1d-128a-462c-b677-d19bc5bf0891` / generation
`f45f46a9-56ae-49b5-966d-083cdf19282b`，binding rev6/epoch3 ready、九路 rev231/group258、
唯一 Host PID 88320；definition rev172 disabled、recovery56、attempt=0，12/12 与零副作用。

## 2/6 纯 HTTP 18181

`check`/`serve` 读回 Cron=false、snapshot worker=false、进程内 Host=false、sourceCalls=0；
`/v1/health` 与 OpenAPI=200，prepare/schedule-ingest/controls 各确认 12 项，随后 18181 释放，
第二 Host=0，PID 88320 保持在线。

## 3/6 冻结输入转移

transfer 生成 rev173 disabled/hash
`sha256:d23785de2ea7a47136a9dc11bed4f6c3598461c93ac943a7b7019be2a43829ff`；
renew 生成 recovery57/hash
`sha256:01c5506cb0d32daa41cba70de767ca676924ccb6b596aaf524f24979ead7ce40`；
enable 生成 rev174 enabled/hash
`sha256:4190cfd9eb69c44c56eb8c35a44e2f95500f755420437bb43ce6df863badd2a0`。
manifest 仍为 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
各阶段 sourceReads=0。

## 4/6 唯一自然 worker

Lease `A0V-CJ-SNAPSHOT-WORKER-20260921` 已在 worker 启动前登记；唯一 worker PID 90034
自然创建上述 attempt，幂等键
`snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
`sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

50 秒只读采样见 running rev2，100 秒见 running rev3，150 秒见 failed rev5；accepted_at
`2026-09-21T08:36:52.941941Z`，completed_at `2026-09-21T08:38:27.726439Z`。
不是 deadline 情形；worker SIGTERM returnCode=-15，未升级 kill。

## 6/6 终态、零副作用与下一波

exact guard 冻结 rev174/recovery57/failed rev5；pause-terminal 生成 rev175 disabled/hash
`sha256:1ae173620d83402e80502555648329ffa83cd86f60d0a92ac48aa38da8784e1a`。
最终 12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0、worker=0、18181=0，Host PID 88320 仍在。
下一波为 CJ 正式退休与 CK direct successor。本提交完成后自动进入该波。
