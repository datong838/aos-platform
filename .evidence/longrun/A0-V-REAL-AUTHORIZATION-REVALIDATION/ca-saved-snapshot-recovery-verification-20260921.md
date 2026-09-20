# CA 保存快照恢复正式终态验证（2026-09-21）

## 结论

`CA_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。CA 已将 BZ 留下的冻结输入转移到当前
generation，并由唯一自然 worker 产生且只产生一个 attempt。attempt 正式终结为 failed，原因
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；supervisor stop-only 关闭 worker，definition
推进到 rev148 disabled。全过程未读取商城源数据、未调用 `run_definition`、未产生业务副作用，不重发。

## 1/6 plan 与基线

- HEAD `816e4375`；CA installation/generation `0d834ab1-fd2b-4dbc-b9a5-0f0dee712647` /
  `1f18a077-12c6-4242-982a-0c3fa1159540`，binding rev6/epoch3 ready，九路 rev204/group231，
  唯一外置 Host PID 34620。
- definition rev145 disabled/hash `sha256:327b7b1e8288a61dbc6703f16949ee88c6b2b2c0f80a6a2d05e164cdb4b30a91`；
  recovery47/hash `sha256:76faf4a8280a9d078e510ec3ddba0dd03048f4e0ea7689b8695652791f2002ee`；
  attempt=0，12 members/12 running Run/12 Dataset Receipt。

## 2/6 纯 HTTP 18181

- CA launcher 复用已验证的固定 credentials/bundle/trust roots；`check` 及 `serve` 读回 Cron=false、snapshot
  worker=false、进程内 Host=false、sourceCalls=0/runsCreated=0。
- `/openapi.json`=200；外置 Host 仍唯一，第二 Host=0。
- prepare/schedule-ingest/controls 分别确认 12 个只读 draft、12 个既有 schedule、12 组 control/binding，
  sourceReads=0；API 随后正常关闭，18181 释放。

## 3/6 冻结输入转移

- transfer 从 BZ rev145/recovery47 生成 CA rev146 disabled/hash
  `sha256:df0e3f174f5faf793c03663159c245c561b465aa329771b682f337db33537262`。
- renew 生成 recovery48/hash
  `sha256:d6549653845e2e3bad2766bc8dbbdf5b43ff9497efc72e455d4d5fa75b25e728` 与 definition
  rev147 enabled/hash `sha256:01db21ac48d5b139e68b519058d3b7f162e72c10e1acf6b63f56388d3fdb048b`。
- manifest 固定 `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`，
  recovery 控制窗口至 `2026-09-21T00:24:37.861830Z`，各阶段 `sourceReads=0`。

## 4/6 唯一自然 worker

- CA 专用 Lease、worker 与 supervisor 锁定 m1、单 worker、50 秒采样、1800 秒上限；启动前 attempt=0、
  worker=0、18181=0、外置 Host=1。supervisor 仅薄包装复用上一波已验证的有界实现，并覆盖 CA
  installation/generation 与 worker 路径，没有新增执行判断。
- 唯一 worker PID 35889；自然创建 attempt `4a3ca4e5-db9f-47a0-a283-2adf23d25e84`，幂等键
  `snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。

## 5/6 连续观察

- 同一 supervisor 只读观察 running rev2 及 heartbeat/lease，随后在 90 秒样本读到正式 failed rev4；
  accepted_at `2026-09-20T18:25:51.665926Z`，completed_at `2026-09-20T18:27:11.099919Z`。
- terminal reason `RECOVERABLE_EXECUTION_EXCEPTION`、error type `IngressJournalConflict`，不是
  `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED`，不进入 1800 秒延续路径。
- supervisor 以 SIGTERM 关闭 worker，returnCode=-15、stopped=true、killEscalated=false。

## 6/6 终态、零副作用与下一波

- exact guard 先冻结 rev147 enabled/recovery48/failed rev4 边界；pause-terminal 生成 definition rev148
  disabled/hash `sha256:bfceb8c79e25559b1473e7b26fa88710b3c2641006aeb62cb443083aad0b2ed9`。
- 最终 12 members、12 running Run、0 succeeded/failed Run、12 Dataset Receipt；relationships=1、
  linkCommands=1、linkCount=1168；retirements=0、Store Receipt=0、`ecom_link`=0、link outbox=0、
  projection pending=0、canary=0；九路 rev204/group231、liveResources=3、Host PID 34620、worker=0、18181=0。
- `py_compile`、完整约束测试与 `git diff --check` 作为提交前门禁。下一波自动执行 CA 正式退休与 CB
  direct successor；以本文件 failed rev4、definition rev148 disabled、recovery48 与 3 个 live resource 为 authority。
