# BP 保存快照恢复与单一自然 attempt 方案（2026-09-20）

## 1. 当前权威

- HEAD `fad5ba06`；BP installation `17ba9792-9f24-42e4-9557-4d84547c7d97` /
  generation `4f1bddfa-74a0-4fcb-b25e-f363139eed83` 已完成九路切换与12次新增健康续租。
- binding rev6/epoch3 enabled/ready/unfenced，route rev171/group198；definition rev121 disabled，
  BP attempt=0。
- recovery rev39/hash
  `sha256:39ca604ec957db0f8a7b20fedecd11f25e3ed8d60e3cc0feea56d6568d8cc2ec`；十二 Run仍
  running、十二 Dataset Receipt保留；Store Receipt、`ecom_link`、projection pending、runtime
  pending与canary均为0。本波只转移BO留存的冻结输入，不读取商城源数据，不调用`run_definition`。
- 当前唯一外置 Runtime Host PID 57278保持运行；纯HTTP阶段不得停止它。“第二 Host=0”按外置Host
  总数=1执行，不误读为外置Host总数=0。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定上述BP、definition rev121/recovery rev39、attempt=0、十二Run/Receipt、
   零副作用边界、单写者m1与一个外置Runtime Host。
2. **纯 HTTP 18181**：在现有Host不停机的前提下启动一个受控纯HTTP API；读回Cron=false、
   snapshot worker=false、进程内Runtime Host=false；外置Runtime Host总数恰好1，第二Host=0。
3. **冻结输入转移**：prepare、schedule-ingest、controls；关闭18181并确认端口释放；从BO
   rev121 disabled/recovery rev39执行transfer -> BP rev122 disabled、renew -> recovery rev40 /
   definition rev123 enabled，enable读回`sourceReads=0`。
4. **唯一自然 worker**：以exact lease启动同一个supervisor/worker；固定BP installation、generation、
   definition rev123、recovery rev40、数据库accepted_at与request hash。禁止手工`run_definition`、
   第二worker、第二Runtime Host或第二attempt。worker得到未知执行结果后必须停止本轮serve。
5. **单轮观察窗**：每50秒只读采样唯一attempt直到正式terminal；若300秒出现
   `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED`且十二Run仍running、Store Receipt=0、`ecom_link`=0、
   projection pending=0，则不重发，在原accepted_at起算的1800秒有界预算内继续同一attempt。
   任何第二attempt或unknown边界立即冻结，禁止猜测成功或重发。
6. **终态/verification/commit**：正式终态及零副作用读回后，pause-terminal -> definition rev124
   disabled；若进程需停止，先SIGTERM，有界180秒后仅在exact terminal/attemptCount=1/零副作用/PID
   与进程组精确匹配时允许一次SIGKILL。落盘verification、测试、精确提交，然后自动进入BP正式退休
   与BQ direct successor波。

## 3. 停止条件

- 任一identity、Receipt/hash、definition/recovery revision、十二Run/Receipt或route/binding漂移；
- Cron、snapshot worker或进程内Runtime Host在纯HTTP阶段被启用；外置Host总数不等于1，或出现第二
  worker/attempt；
- 商城源读取、`dev-org/dev-project`非零写、Store Receipt/`ecom_link`/projection pending；
- 未知提交边界、手工`run_definition`、300秒失败后重发或更换idempotency key。

所有非人工决策型工程阻断由当前唯一开发在上述边界内自行诊断、最小修复与继续；不push、不动其他
分支，230 L0继续挂起。

## 4. 已继承修复

- transfer必须把predecessor policyRef解析为目标release的同路径、同类型、同摘要canonical alias，
  应用层与数据库`a0v_090`约束一致；不得放宽resourceId/contentHash。
- source claim successor校验接受已由recovery authority验证的同实体canonical alias revision，其他差异
  fail closed。
- snapshot worker得到`SNAPSHOT_EXECUTION_UNCONFIRMED`后必须退出本轮serve，禁止自然产生第二attempt。
