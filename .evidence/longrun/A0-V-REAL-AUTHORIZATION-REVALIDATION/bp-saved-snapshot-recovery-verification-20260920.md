# BP 保存快照恢复冻结验证（2026-09-20）

## 结论

`BP_SAVED_SNAPSHOT_FAILED_FREEZE_BOUNDARY`。

BP 保存快照波产生且仅产生一个自然 attempt；该 attempt以正式failed终态结束，worker已停止，definition
已通过原stop-only Owner从rev123 enabled推进为rev124 disabled。十二Run继续running，全部业务副作用为
零。本波未读取商城源数据、未调用`run_definition`、未重发未知结果。

## 1. 纯HTTP与冻结输入

- 18181受控API读回`AOS_QYH_CRON_ENABLED=false`、
  `AOS_SNAPSHOT_GROUP_WORKER_ENABLED=false`、`AOS_EXTENSION_RUNTIME_HOST_ENABLED=0`；OpenAPI返回200、
  2711条路径，`sourceCalls=0`、`runsCreated=0`。
- 纯HTTP阶段外置Runtime Host恰好一个（PID 57278），第二Host=0；关闭后18181端口释放。
- prepare、12路schedule-ingest、12路controls均精确命中BP installation
  `17ba9792-9f24-42e4-9557-4d84547c7d97` / generation
  `4f1bddfa-74a0-4fcb-b25e-f363139eed83`；未读取商城源。

## 2. definition与recovery链

- predecessor为BO definition rev121 disabled/hash
  `sha256:e12b288fc65522b7978b439fe02d169e1367a50d44d66c6f72ff1b8def484044`、recovery
  rev39/hash `sha256:39ca604ec957db0f8a7b20fedecd11f25e3ed8d60e3cc0feea56d6568d8cc2ec`。
- transfer生成BP rev122 disabled/hash
  `sha256:f3e1b9b942364cc77fbb04caa723f3c67188fe78f01ee0f162c59958e9998901`。
- renew生成recovery rev40/hash
  `sha256:ac3656e9f5b9852b438a43adad574c2a30e6b80420282b196dd51a5605ecff97`，request
  hash `sha256:cc2457a285ccad8c6ea16f2483511dcc0e30166275fc89298ecc09d9263d2ebc`。
- definition rev123 enabled/hash
  `sha256:a19cde7f277e204e615f374d6411f9b849606268f4114339020e314381f0f0e7`；上述步骤均读回
  `sourceReads=0`。

## 3. 唯一自然attempt与连续观察

- 启动前BP attempt=0、外置Host=1、snapshot worker=0、supervisor=0；BP专用lease排除商城源读取、
  手工`run_definition`、第二worker/Host、cron、dev-org mutation、push与230 L0。
- 唯一attempt `051397ad-7027-4ee5-9d4c-f32374841cd9`，accepted
  `2026-09-20T11:13:35.849029Z`，completed `11:15:36.743822Z`，idempotency key
  `snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。
- 50秒连续样本依次确认attempt=0、running revision2、running revision3、failed revision5；正式终态为
  `RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`，不是
  `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED`，因此不进入1800秒deadline续等路径。
- supervisor在正式终态后对worker PID 83554发送SIGTERM，return=-15，未升级SIGKILL；最终worker=0、
  supervisor=0、attemptCount=1。

## 4. 冻结边界与零副作用

- stop-only pause生成definition rev124 disabled/hash
  `sha256:6472cbec4f4a3dcf31540bf54ea3f1ca03d832dcc4c601d54d7dfb508a26d353`。
- 十二member、十二running Run、十二Dataset Receipt保持；succeeded/failed Run均0；relationship=1、
  link command=1、linkCount=1168。
- retirement=0、Store Receipt=0、`ecom_link=0`、link outbox=0、projection pending=0；BP三资源仍live，
  `dev-org/dev-project` canary=0；九路仍为BP rev171/group198。
- 当前外置Host仍恰好一个PID 57278；18181、snapshot worker、supervisor均为0。

## 5. 偏差、修复与下一波

- 首次HTTP探针请求了不存在的`/healthz`并得到404；随后改用只读`/openapi.json`确认200，未产生业务写。
- prepare后过早关闭18181，首次schedule-ingest在TCP connect阶段失败；没有结果文件或提交边界。重新以
  相同纯HTTP配置启动后完成12路只读对账，再关闭端口。该偏差不是未知结果重发。
- 启动前修复BP supervisor采样顺序：先读取/分类attempt，再判断worker是否已自行退出，避免已修复worker
  在unknown tick后退出时被误报为“无attempt边界”；不改变50秒间隔或执行授权。
- 五个专项脚本通过语法编译，saved-snapshot与released-retirement回归共25项全部通过；最终guard只读
  复核与`git diff --check`通过。
- 下一波自动进入 **BP正式failed-terminal retirement与BQ direct successor**：先停止唯一外置Host，正式
  disable/detach BP并释放三资源，再从exact detach authority创建、注册、cutover并观察BQ；不得在BP内
  再次启动worker。
