# BW 保存快照恢复正式终态验证（2026-09-21）

## 结论

`BW_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。BW已将BV留下的冻结输入转移到当前
generation，并由唯一自然worker产生且只产生一个attempt。attempt正式终结为failed，原因
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；supervisor stop-only关闭worker，definition
推进到rev136 disabled。全过程未读取商城源数据、未调用 `run_definition`、未产生业务副作用，不重发。

## 1/6 plan 与基线

- HEAD `254ba795`；BW installation/generation `9b6e1277-a0a2-447d-9062-a98adfed3f22` /
  `62cf014b-9ce5-4512-8a34-b55a79e053c3`，binding rev6/epoch3 ready，九路rev192/group219，
  唯一外置Host PID 20193。
- definition rev133 disabled/hash `sha256:353ea9fb1da5f282c1b70f77f90b2e79cf26f279648934836d524c512c899528`；
  recovery43/hash `sha256:4a14bb3109516487c5ede4ee27a131f0c27043ce6daed1e880fcd1222b303625`；
  attempt=0，12 members/12 running Run/12 Dataset Receipt。
- 纯HTTP与BW单worker租约在不扩大excluded scope的前提下续至2026-09-21；230 L0、商城源读取、
  手工run_definition、第二Host/worker、负租户写和push仍明确排除。

## 2/6 纯HTTP 18181

- BW固定launcher绑定20260920 credentials/bundle/trust roots；`check`及`serve`读回Cron=false、snapshot
  worker=false、进程内Host=false、sourceCalls=0/runsCreated=0。
- `/openapi.json`=200；公共schema读取仅为dev-org零canary，无业务读取或写入；外置Host仍唯一，第二Host=0。
- prepare/schedule-ingest/controls分别确认12个只读draft、12个既有schedule、12组control/binding，私有结果
  均0600；组合命令在前端30秒显示边界后，三份不可变结果均已落盘，故只对账未重发。API随后正常关闭，
  18181释放。

## 3/6 冻结输入转移

- transfer从BV rev133/recovery43生成BW rev134 disabled/hash
  `sha256:d9519add0bd72bed1534b89f7001f5573beb72b86cfed3620db181a6d3516e59`。
- renew生成recovery44/hash
  `sha256:f7517614d7a73f7d3cb3c8e9e55ee5db995c95841147ecd2edcb91817fca64fe`与definition
  rev135 enabled/hash `sha256:75098ba2b68fd8cd79a31ecf4c71da542a191ee09eee36c6ca369926464c8c04`。
- manifest固定 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
  recovery控制窗口至 `2026-09-20T22:26:14.245876Z`，各阶段 `sourceReads=0`。

## 4/6 唯一自然worker

- BW专用Lease、worker与supervisor锁定m1、单worker、50秒采样、1800秒上限；启动前attempt=0、
  worker=0、18181=0、外置Host=1。
- 唯一worker PID 22634；自然创建attempt `4e3846d8-28b2-4c50-934b-8383df598956`，幂等键
  `snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

- 同一supervisor只读观察running rev2及heartbeat/lease，随后在90秒样本读到正式failed rev4；
  accepted_at `2026-09-20T16:28:08.222055Z`，completed_at `2026-09-20T16:29:31.315961Z`。
- terminal reason `RECOVERABLE_EXECUTION_EXCEPTION`、error type `IngressJournalConflict`，不是
  `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED`，不进入1800秒延续路径。
- supervisor以SIGTERM关闭worker，returnCode=-15、stopped=true、killEscalated=false。

## 6/6 终态、零副作用与下一波

- exact guard先冻结rev135 enabled/recovery44/failed rev4边界；pause-terminal生成definition rev136
  disabled/hash `sha256:6f40e25f3c86325f843e4232eabde56d276d11ae557cb20842399d7bd7681187`。
- 最终12 members、12 running Run、0 succeeded/failed Run、12 Dataset Receipt；relationships=1、
  linkCommands=1、linkCount=1168；retirements=0、Store Receipt=0、`ecom_link`=0、link outbox=0、
  projection pending=0、canary=0；九路rev192/group219、liveResources=3、Host PID 20193、worker=0、18181=0。
- 电脑重启后pytest首次因Docker测试库5433未恢复而在fixture前失败；恢复原有`aos-dev-pg`后同一静态测试
  通过，未触发业务动作。`py_compile`、完整约束测试与 `git diff --check` 作为提交前门禁。
- 下一波自动执行BW正式退休与BX direct successor；以本文件failed rev4、definition rev136 disabled、
  recovery44与3个live resource为authority。
