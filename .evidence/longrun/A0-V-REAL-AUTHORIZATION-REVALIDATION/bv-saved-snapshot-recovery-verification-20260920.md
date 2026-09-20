# BV 保存快照恢复正式终态验证（2026-09-20）

## 结论

`BV_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。BV已将BU留下的冻结输入转移到当前
generation，并由唯一自然worker产生且只产生一个attempt。attempt正式终结为failed，原因
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；supervisor stop-only关闭worker，definition
推进到rev133 disabled。全过程未读取商城源数据、未调用 `run_definition`、未产生业务副作用，不重发。

## 1/6 plan 与基线

- HEAD `4055a7da`；BV installation/generation `2b1aa826-b595-40d4-aeb2-9a7ce9d33c36` /
  `e8a5b32b-9a29-41bf-9c7f-87c7cd96b359`，binding rev6/epoch3 ready，九路rev189/group216，
  唯一外置Host PID 15565。
- definition rev130 disabled/hash `sha256:5a07cdb9584a79f3f51fefc33a5ece622700c08cde8799eb522beff59c857392`；
  recovery42/hash `sha256:2f137e718e768aa98116af8dfa8c28a5eb66d2f3270fe8ac4c1f87b16d7cd963`；
  attempt=0，12 members/12 running Run/12 Dataset Receipt。
- 纯HTTP与BV单worker租约在不扩大excluded scope的前提下续至2026-09-21；230 L0、商城源读取、
  手工run_definition、第二Host/worker、负租户写和push仍明确排除。

## 2/6 纯HTTP 18181

- BV固定launcher绑定20260920 credentials/bundle/trust roots；`check`及`serve`读回Cron=false、snapshot
  worker=false、进程内Host=false、sourceCalls=0/runsCreated=0。
- `/openapi.json`=200；该公共schema读取被服务记录为dev-org零canary请求，无业务读取或写入；外置Host仍
  唯一，第二Host=0。
- prepare/schedule-ingest/controls分别确认12个只读draft、12个既有schedule、12组control/binding，
  私有结果均0600；组合命令在controls输出阶段达到前端30秒显示边界，但三份不可变结果均已落盘，故只
  对账未重发。API随后正常关闭，18181释放。

## 3/6 冻结输入转移

- transfer从BU rev130/recovery42生成BV rev131 disabled/hash
  `sha256:13709ec1bbe817d447409d76dcd94ab527415634a70ce5540da0739432349fcb`。
- renew生成recovery43/hash
  `sha256:4a14bb3109516487c5ede4ee27a131f0c27043ce6daed1e880fcd1222b303625`与definition
  rev132 enabled/hash `sha256:a070771e455754131bd691f44ea055a1ca2406ddbbe88a3908d89bd1d4819183`。
- manifest固定 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
  recovery控制窗口至 `2026-09-20T21:54:21.015271Z`，各阶段 `sourceReads=0`。

## 4/6 唯一自然worker

- BV专用Lease、worker与supervisor锁定m1、单worker、50秒采样、1800秒上限；启动前attempt=0、
  worker=0、18181=0、外置Host=1。
- rev132后旧direct-successor健康探针按设计因锁死rev130而fail closed；改用本波supervisor精确读回
  attempt=0，没有重发或启动第二进程。
- 唯一worker PID 19366；自然创建attempt `3afcfcae-b78c-4d15-8c64-4ec4e53325f3`，幂等键
  `snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

- 同一supervisor只读观察running rev2及heartbeat/lease，随后在90秒样本读到正式failed rev4；
  accepted_at `2026-09-20T15:55:36.392252Z`，completed_at `2026-09-20T15:57:00.052613Z`。
- terminal reason `RECOVERABLE_EXECUTION_EXCEPTION`、error type `IngressJournalConflict`，不是
  `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED`，不进入1800秒延续路径。
- supervisor以SIGTERM关闭worker，returnCode=-15、stopped=true、killEscalated=false。

## 6/6 终态、零副作用与下一波

- exact guard先冻结rev132 enabled/recovery43/failed rev4边界；pause-terminal生成definition rev133
  disabled/hash `sha256:353ea9fb1da5f282c1b70f77f90b2e79cf26f279648934836d524c512c899528`。
- 最终12 members、12 running Run、0 succeeded/failed Run、12 Dataset Receipt；relationships=1、
  linkCommands=1、linkCount=1168；retirements=0、Store Receipt=0、`ecom_link`=0、link outbox=0、
  projection pending=0、canary=0；九路rev189/group216、liveResources=3、Host PID 15565、worker=0、18181=0。
- `py_compile`与 `git diff --check` 通过；完整约束测试 `65 passed`。测试退出后的既有JDBC cleanup
  closed-stream日志不影响pytest成功退出。下一波自动执行BV正式退休与BW direct successor；以本文件failed
  rev4、definition rev133 disabled、recovery43与3个live resource为authority。
