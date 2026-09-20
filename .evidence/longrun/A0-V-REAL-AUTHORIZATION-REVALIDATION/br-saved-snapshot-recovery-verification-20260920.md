# BR 保存快照恢复正式终态验证（2026-09-20）

## 结论

`BR_SAVED_SNAPSHOT_SINGLE_NATURAL_ATTEMPT_FAILED_FROZEN`。

BR 已将 BP 留下的冻结输入转移到当前 generation，并由唯一自然 worker 产生且只产生一个 attempt。
该 attempt 正式终结为 failed，原因是 `RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`；
supervisor 随即 stop-only 关闭 worker，definition 单向推进到 rev127 disabled。全过程未读取商城源数据，
未调用 `run_definition`，未产生 Store Receipt、`ecom_link` 或 projection pending；失败边界明确，不重发。

## 1/6 plan 与前置基线

- HEAD `1f832030`；BR installation `fddfa0b0-158c-4271-b1ea-dc4e1e36e293` / generation
  `981d7a2d-3bbe-4cc1-a8d9-c872be0147d3`，binding rev6/epoch3 enabled/ready，九路
  rev177/group204，唯一外置 Runtime Host PID 26889。
- definition rev124 disabled/hash
  `sha256:6472cbec4f4a3dcf31540bf54ea3f1ca03d832dcc4c601d54d7dfb508a26d353`；recovery
  rev40/hash `sha256:ac3656e9f5b9852b438a43adad574c2a30e6b80420282b196dd51a5605ecff97`；
  attempt=0，12 members/12 running Run/12 Dataset Receipt。
- plan 固定 rev124 -> rev125 disabled -> recovery41/rev126 enabled -> 唯一自然 attempt -> rev127
  disabled，并明确所有 fail-closed 与零副作用停止条件。

## 2/6 纯 HTTP 18181

- 专项测试先为35项通过；受控 API `check` 返回
  `CONTROLLED_API_LOCAL_DIAGNOSTIC_PREFLIGHT_GREEN`，读回
  `AOS_QYH_CRON_ENABLED=false`、`AOS_SNAPSHOT_GROUP_WORKER_ENABLED=false`、
  `AOS_EXTENSION_RUNTIME_HOST_ENABLED=0`、`sourceCalls=0/runsCreated=0`。
- 18181 `/openapi.json` 返回200；`prepare` 形成12个只读 draft，`schedule-ingest` 确认12个既有
  schedule，`controls` 读回12组 selection/control/binding；没有商城源读取。
- 纯 HTTP 正常关闭并确认18181释放；外置 Host PID 26889保持唯一，第二 Host=0。

## 3/6 冻结输入转移

- `transfer` 从 BP installation `17ba9792-9f24-42e4-9557-4d84547c7d97` 的 rev124/recovery40
  生成 BR definition rev125 disabled/hash
  `sha256:725da5ea883c0e79eb5b94fcd6694317982c2a96a5f13721e5726983da3f7735`。
- `renew` 生成 recovery rev41/hash
  `sha256:400cf5d221f28501d763b194fb412a18a2c23c872057fe6e5f4c896a7721935d`，以及 definition
  rev126 enabled/hash `sha256:a2cdc04c9283bfd25ce4f7a79335915b1aeacba19b3233d649f92bb026ef72fd`。
- 三段均读回 `sourceReads=0`；输入 manifest 固定为
  `sha256:03ccccacfda079e3318abbea3a39dfa232d655560c309ff511ad0ecace335e01`。

## 4/6 唯一自然 worker

- 新增 BR 专用 worker/supervisor，并在共享 lease 登记
  `A0V-BR-SNAPSHOT-WORKER-20260920`；启动前专项测试37项通过，attempt=0、worker=0、18181=0、
  外置 Host=1。
- 唯一 worker PID 60479；自然创建 attempt
  `256207c9-4bc4-4c89-b00f-146f58012011`，幂等键
  `snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。
- 没有第二 worker、第二 Host、第二 attempt，也没有手工 `run_definition`。

## 5/6 50 秒连续观察

- 同一 supervisor 以50秒间隔只读采样；attempt 依次保持 running 并推进 revision/heartbeat/lease，
  未发生身份或幂等边界漂移。
- accepted_at `2026-09-20T12:26:07.088906Z`，completed_at
  `2026-09-20T12:30:45.439107Z`；326秒采样时已正式终结为 failed rev8，terminal reason
  `RECOVERABLE_EXECUTION_EXCEPTION`，error type `IngressJournalConflict`。
- 该结果不是 `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED`，因此不进入1800秒延长路径。supervisor 发送
  SIGTERM 后 worker returnCode=-15、stopped=true、killEscalated=false。

## 6/6 终态、零副作用与下一波

- 精确 guard 在暂停前读回 failed rev8、definition rev126 enabled、recovery41、attemptCount=1；
  `pause-terminal` 随后生成 definition rev127 disabled/hash
  `sha256:4e373626f25a3fcb643e04f5cf3468b553c5c03815c347098840a18c15697aa0`。
- 最终 guard 再次读回：12 members、12 running Run、0 succeeded、0 failed、12 Dataset Receipt；
  relationships=1、linkCommands=1、linkCount=1168保持；retirements=0、link Store Receipt=0、
  `ecom_link=0`、link outbox=0、projection pending=0、`dev-org/dev-project` canary=0；九路仍为
  rev177/group204，liveResources=3，唯一 Host PID 26889仍存活，worker=0，18181=0。
- 最终专项测试 **38 passed**。本波 verification 已落盘后精确提交；不 push、不动其他分支，230 L0
  继续挂起。
- 下一波自动执行 **BR 正式退休与 BS direct successor**：以本文件的 failed rev8、definition rev127
  disabled、recovery41、九路 rev177/group204 和三项 live resource 为 exact authority，先走正式
  retirement fence/detach，再创建并验证 BS lifecycle、九路 cutover、唯一外置 Host 与有界健康观察。
