# BZ 保存快照恢复正式终态验证（2026-09-21）

## 结论

`BZ_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。BZ 已将 BY 留下的冻结输入转移到当前
generation，并由唯一自然 worker 产生且只产生一个 attempt。attempt 正式终结为 failed，原因
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；supervisor stop-only 关闭 worker，definition
推进到 rev145 disabled。全过程未读取商城源数据、未调用 `run_definition`、未产生业务副作用，不重发。

## 1/6 plan 与基线

- HEAD `fdf439e7`；BZ installation/generation `9b30837c-da4d-4cfd-b438-de40aa5e3d7a` /
  `6f1e6e77-24aa-4052-9102-88e4a432fe55`，binding rev6/epoch3 ready，九路 rev201/group228，
  唯一外置 Host PID 31607。
- definition rev142 disabled/hash `sha256:82637ea76a9d9a6169ffe5e9264d4c157075933017038caef6208ebd37bfe8c3`；
  recovery46/hash `sha256:a0e1a232f699d30d97c95cf7143665c6976033b6cf011b55ff783e20bc586142`；
  attempt=0，12 members/12 running Run/12 Dataset Receipt。

## 2/6 纯 HTTP 18181

- BZ launcher 复用已验证的固定 credentials/bundle/trust roots；`check` 及 `serve` 读回 Cron=false、snapshot
  worker=false、进程内 Host=false、sourceCalls=0/runsCreated=0。
- `/openapi.json`=200；外置 Host 仍唯一，第二 Host=0。
- prepare/schedule-ingest/controls 分别确认 12 个只读 draft、12 个既有 schedule、12 组 control/binding，
  sourceReads=0；API 随后正常关闭，18181 释放。

## 3/6 冻结输入转移

- transfer 从 BY rev142/recovery46 生成 BZ rev143 disabled/hash
  `sha256:5e93c0016d117f5db43eb7e553d5a2ad841c816cddbd862f93419f16b32c3d26`。
- renew 生成 recovery47/hash
  `sha256:76faf4a8280a9d078e510ec3ddba0dd03048f4e0ea7689b8695652791f2002ee` 与 definition
  rev144 enabled/hash `sha256:4744830b177314031bf9a459f19ab6c54e17d74512df00daef2456d63d06e1d7`。
- manifest 固定 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
  recovery 控制窗口至 `2026-09-20T23:56:47.252110Z`，各阶段 `sourceReads=0`。

## 4/6 唯一自然 worker

- BZ 专用 Lease、worker 与 supervisor 锁定 m1、单 worker、50 秒采样、1800 秒上限；启动前 attempt=0、
  worker=0、18181=0、外置 Host=1。supervisor 仅薄包装复用上一波已验证的有界实现，并覆盖 BZ
  installation/generation 与 worker 路径，没有新增执行判断。
- 唯一 worker PID 34054；自然创建 attempt `b7044a35-43f8-4089-ba79-4da3d92cbf64`，幂等键
  `snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

- 同一 supervisor 只读观察 running rev2 及 heartbeat/lease，随后在 80 秒内读到正式 failed rev4；
  accepted_at `2026-09-20T17:57:37.930553Z`，completed_at `2026-09-20T17:58:57.375432Z`。
- terminal reason `RECOVERABLE_EXECUTION_EXCEPTION`、error type `IngressJournalConflict`，不是
  `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED`，不进入 1800 秒延续路径。
- supervisor 以 SIGTERM 关闭 worker，returnCode=-15、stopped=true、killEscalated=false。

## 6/6 终态、零副作用与下一波

- exact guard 先冻结 rev144 enabled/recovery47/failed rev4 边界；pause-terminal 生成 definition rev145
  disabled/hash `sha256:327b7b1e8288a61dbc6703f16949ee88c6b2b2c0f80a6a2d05e164cdb4b30a91`。
- 最终 12 members、12 running Run、0 succeeded/failed Run、12 Dataset Receipt；relationships=1、
  linkCommands=1、linkCount=1168；retirements=0、Store Receipt=0、`ecom_link`=0、link outbox=0、
  projection pending=0、canary=0；九路 rev201/group228、liveResources=3、Host PID 31607、worker=0、18181=0。
- `py_compile`、完整约束测试与 `git diff --check` 作为提交前门禁。下一波自动执行 BZ 正式退休与 CA
  direct successor；以本文件 failed rev4、definition rev145 disabled、recovery47 与 3 个 live resource 为 authority。
