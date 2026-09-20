# BU 保存快照恢复正式终态验证（2026-09-20）

## 结论

`BU_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。BU 已将 BR 留下的冻结输入转移到当前
generation，并由唯一自然 worker 产生且只产生一个 attempt。attempt 正式终结为 failed，原因
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；supervisor stop-only关闭worker，definition
推进到rev130 disabled。全过程未读取商城源数据、未调用 `run_definition`、未产生业务副作用，不重发。

## 1/6 plan 与基线

- HEAD `5c1e4d6c`；BU installation/generation `d1dcf5c2-f6ff-48b2-b6f1-fb05d17b7895` /
  `cb8ace71-ba8d-4e08-816b-8d6bbc0f0281`，binding rev6/epoch3 ready，九路rev186/group213，
  唯一外置Host PID 10997。
- definition rev127 disabled/hash `sha256:4e373626f25a3fcb643e04f5cf3468b553c5c03815c347098840a18c15697aa0`；
  recovery41/hash `sha256:400cf5d221f28501d763b194fb412a18a2c23c872057fe6e5f4c896a7721935d`；
  attempt=0，12 members/12 running Run/12 Dataset Receipt。

## 2/6 纯HTTP 18181

- 首次误用通用launcher，旧默认凭据被 `CREDENTIAL_FILE_INVALID` 安全拒绝，18181未启动、无写入；随后新增
  BU固定launcher，绑定20260920 credentials/bundle/trust roots。
- `check`读回Cron=false、snapshot worker=false、进程内Host=false、sourceCalls=0/runsCreated=0；
  `/openapi.json`=200，外置Host仍唯一，第二Host=0。
- prepare/schedule-ingest/controls分别确认12个只读draft、12个既有schedule、12组control/binding；
  API随后正常关闭，18181释放。

## 3/6 冻结输入转移

- transfer从BR rev127/recovery41生成BU rev128 disabled/hash
  `sha256:6b3c881834394eadf50e0d428a72bc31827c1b9e9e02b8a8fef2d02c1d6d34ab`。
- renew生成recovery42/hash
  `sha256:2f137e718e768aa98116af8dfa8c28a5eb66d2f3270fe8ac4c1f87b16d7cd963`与definition
  rev129 enabled/hash `sha256:8e481abc6cad1ad37371a7ab3ecfcfe15de78e7a2f7402efd59d43e555d65f87`。
- manifest固定 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
  各阶段 `sourceReads=0`。

## 4/6 唯一自然worker

- BU专用Lease、worker与supervisor均锁定m1、单worker、50秒采样、1800秒上限；启动前attempt=0、
  worker=0、18181=0、外置Host=1。
- 唯一worker PID 14269；自然创建attempt `617da078-f4ef-4ad9-9ac6-bd764468fa67`，幂等键
  `snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

- 同一supervisor只读观察running rev2及heartbeat/lease，随后在90秒样本读到正式failed rev4；
  accepted_at `2026-09-20T15:19:14.514945Z`，completed_at `2026-09-20T15:20:43.551673Z`。
- terminal reason `RECOVERABLE_EXECUTION_EXCEPTION`、error type `IngressJournalConflict`，不是
  `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED`，不进入1800秒延续路径。
- supervisor以SIGTERM关闭worker，returnCode=-15、stopped=true、killEscalated=false。

## 6/6 终态、零副作用与下一波

- exact guard先冻结rev129 enabled/recovery42/failed rev4边界；pause-terminal生成definition rev130
  disabled/hash `sha256:5a07cdb9584a79f3f51fefc33a5ece622700c08cde8799eb522beff59c857392`。
- 最终12 members、12 running Run、0 succeeded/failed Run、12 Dataset Receipt；relationships=1、
  linkCommands=1、linkCount=1168；retirements=0、Store Receipt=0、`ecom_link`=0、link outbox=0、
  projection pending=0、canary=0；九路rev186/group213、liveResources=3、Host PID 10997、worker=0、18181=0。
- 完整约束测试 `57 passed`，`py_compile`与`git diff --check`通过；测试退出后的既有JDBC cleanup
  closed-stream告警不影响成功退出。下一波自动执行BU正式退休与BV direct
  successor；以本文件failed rev4、definition rev130 disabled、recovery42与3个live resource为authority。
