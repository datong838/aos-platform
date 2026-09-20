# CB 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CB_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。CB 已将 CA 留下的冻结输入转移到当前
generation，并由唯一自然 worker 产生且只产生一个 attempt。attempt 正式终结为 failed，原因
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；supervisor stop-only 关闭 worker，definition
推进到 rev151 disabled。全过程未读取商城源数据、未调用 `run_definition`、未产生业务副作用，不重发。

## 1/6 plan 与基线

- HEAD `4404dad6`；CB installation/generation `3d6df614-5a05-4c6f-823e-688d81e84096` /
  `0cceac8c-c831-4b3f-92c3-fc35240c5414`，binding rev6/epoch3 ready，九路 rev207/group234，
  唯一外置 Host PID 36215。
- definition rev148 disabled/hash `sha256:bfceb8c79e25559b1473e7b26fa88710b3c2641006aeb62cb443083aad0b2ed9`；
  recovery48/hash `sha256:d6549653845e2e3bad2766bc8dbbdf5b43ff9497efc72e455d4d5fa75b25e728`；
  attempt=0，12 members/12 running Run/12 Dataset Receipt。

## 2/6 纯 HTTP 18181

- CB launcher 复用已验证的固定 credentials/bundle/trust roots；`check` 及 `serve` 读回 Cron=false、snapshot
  worker=false、进程内 Host=false、sourceCalls=0/runsCreated=0。
- `/openapi.json`=200；外置 Host 仍唯一，第二 Host=0。
- prepare/schedule-ingest/controls 分别确认 12 个只读 draft、12 个既有 schedule、12 组 control/binding，
  sourceReads=0；API 随后正常关闭，18181 释放。

## 3/6 冻结输入转移

- transfer 从 CA rev148/recovery48 生成 CB rev149 disabled/hash
  `sha256:0bac09cd36875d573a9a83d664495d3eee2c3bb23b13b521e79ddfc102961ebb`。
- renew 生成 recovery49/hash
  `sha256:6a5673ae858453ca9a525d0759bf29b63c681f9f07eb1aa07d347fd7d116bf5b` 与 definition
  rev150 enabled/hash `sha256:ef79e47baf538a0600719c73c23c0ee09b0a78cc04a9202c3ffe570304ff4e9c`。
- manifest 固定 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
  recovery 控制窗口至 `2026-09-21T00:52:17.137220Z`，各阶段 `sourceReads=0`。renew/enable 输出首次未在
  串行命令观察窗内显现，先以只读 inspect 对账到 rev150/recovery49，随后 immutable 结果文件落盘；未重发。

## 4/6 唯一自然 worker

- CB 专用 Lease、worker 与 supervisor 锁定 m1、单 worker、50 秒采样、1800 秒上限；启动前 attempt=0、
  worker=0、18181=0、外置 Host=1。supervisor 仅薄包装复用上一波已验证的有界实现，并覆盖 CB
  installation/generation 与 worker 路径，没有新增执行判断。
- 唯一 worker PID 37559；自然创建 attempt `727af369-a8ce-4500-86a7-1cf412a42cb3`，幂等键
  `snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

- 同一 supervisor 只读观察 running rev2 及 heartbeat/lease，随后在 90 秒样本读到正式 failed rev4；
  accepted_at `2026-09-20T18:53:44.780510Z`，completed_at `2026-09-20T18:55:04.549444Z`。
- terminal reason `RECOVERABLE_EXECUTION_EXCEPTION`、error type `IngressJournalConflict`，不是
  `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED`，不进入 1800 秒延续路径。
- supervisor 以 SIGTERM 关闭 worker，returnCode=-15、stopped=true、killEscalated=false。

## 6/6 终态、零副作用与下一波

- exact guard 先冻结 rev150 enabled/recovery49/failed rev4 边界；pause-terminal 生成 definition rev151
  disabled/hash `sha256:f32d555f0fab51da085050993c07d36f786be867f7ef25d2f7fd32ebaa6d905a`。
- 最终 12 members、12 running Run、0 succeeded/failed Run、12 Dataset Receipt；relationships=1、
  linkCommands=1、linkCount=1168；retirements=0、Store Receipt=0、`ecom_link`=0、link outbox=0、
  projection pending=0、canary=0；九路 rev207/group234、liveResources=3、Host PID 36215、worker=0、18181=0。
- `py_compile`、完整约束测试与 `git diff --check` 作为提交前门禁。下一波自动执行 CB 正式退休与 CC
  direct successor；以本文件 failed rev4、definition rev151 disabled、recovery49 与 3 个 live resource 为 authority。
