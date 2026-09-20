# BX 保存快照恢复正式终态验证（2026-09-21）

## 结论

`BX_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。BX已将BW留下的冻结输入转移到当前
generation，并由唯一自然worker产生且只产生一个attempt。attempt正式终结为failed，原因
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；supervisor stop-only关闭worker，definition
推进到rev139 disabled。全过程未读取商城源数据、未调用 `run_definition`、未产生业务副作用，不重发。

## 1/6 plan 与基线

- HEAD `d9fd25c6`；BX installation/generation `45db7b1e-6463-40f2-bf3c-c4e64ce3fd78` /
  `9beb5c99-aba7-4bec-9a10-4f98415aed2f`，binding rev6/epoch3 ready，九路rev195/group222，
  唯一外置Host PID 26649。
- definition rev136 disabled/hash `sha256:6f40e25f3c86325f843e4232eabde56d276d11ae557cb20842399d7bd7681187`；
  recovery44/hash `sha256:f7517614d7a73f7d3cb3c8e9e55ee5db995c95841147ecd2edcb91817fca64fe`；
  attempt=0，12 members/12 running Run/12 Dataset Receipt。

## 2/6 纯HTTP 18181

- BX launcher复用已验证的固定credentials/bundle/trust roots；`check`及`serve`读回Cron=false、snapshot
  worker=false、进程内Host=false、sourceCalls=0/runsCreated=0。
- `/openapi.json`=200；公共schema读取仅为dev-org零canary，无业务读取或写入；外置Host仍唯一，第二Host=0。
- prepare/schedule-ingest/controls分别确认12个只读draft、12个既有schedule、12组control/binding，
  sourceReads=0；API随后正常关闭，18181释放。

## 3/6 冻结输入转移

- transfer从BW rev136/recovery44生成BX rev137 disabled/hash
  `sha256:73b65b7e4ba23a6d957024329bb55c4d2866a5e7f297cc2c624c13fdc5a32ef5`。
- renew生成recovery45/hash
  `sha256:f00d142e1b579f6452bd7aa57ffdde273454ce2a4ed6a8cf6fe564f1ff0463da`与definition
  rev138 enabled/hash `sha256:b6ef70bc63ee4bd4183cc21222ec3a68d054366d6fb38c73e0e6d2ed607f8a03`。
- manifest固定 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
  recovery控制窗口至 `2026-09-20T22:58:56.702097Z`，各阶段 `sourceReads=0`。

## 4/6 唯一自然worker

- BX专用Lease、worker与supervisor锁定m1、单worker、50秒采样、1800秒上限；启动前attempt=0、
  worker=0、18181=0、外置Host=1。supervisor仅薄包装复用上一波已验证的有界实现，并覆盖BX
  installation/generation与worker路径，没有新增执行判断。
- 唯一worker PID 28963；自然创建attempt `dedb3bf6-46ef-4b25-9733-1197ea043d26`，幂等键
  `snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

- 同一supervisor只读观察running rev2及heartbeat/lease，随后在90秒样本读到正式failed rev4；
  accepted_at `2026-09-20T17:00:02.754993Z`，completed_at `2026-09-20T17:01:22.345197Z`。
- terminal reason `RECOVERABLE_EXECUTION_EXCEPTION`、error type `IngressJournalConflict`，不是
  `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED`，不进入1800秒延续路径。
- supervisor以SIGTERM关闭worker，returnCode=-15、stopped=true、killEscalated=false。

## 6/6 终态、零副作用与下一波

- exact guard先冻结rev138 enabled/recovery45/failed rev4边界；pause-terminal生成definition rev139
  disabled/hash `sha256:8986978b518d885bf6753510e1b38f6b860c8aeb5028309c9e3789fab351e7cf`。
- 最终12 members、12 running Run、0 succeeded/failed Run、12 Dataset Receipt；relationships=1、
  linkCommands=1、linkCount=1168；retirements=0、Store Receipt=0、`ecom_link`=0、link outbox=0、
  projection pending=0、canary=0；九路rev195/group222、liveResources=3、Host PID 26649、worker=0、18181=0。
- `py_compile`、完整约束测试与 `git diff --check` 作为提交前门禁。下一波自动执行BX正式退休与BY
  direct successor；以本文件failed rev4、definition rev139 disabled、recovery45与3个live resource为authority。
