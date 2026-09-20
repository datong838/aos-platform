# BO 保存快照恢复与单一自然 attempt 方案（2026-09-20）

## 1. 当前权威

- HEAD `c55cfdee`；BO installation `307399a0-21bb-4d55-95b2-8b0fee238913` /
  generation `030bf59c-c998-4ee6-aedb-11d8d7d5831a` 已完成九路切换与 12 次新增健康续租。
- binding rev6/epoch3 enabled/ready/unfenced，route rev168/group195；definition rev118 disabled，
  BO attempt=0。
- 十二 Run 仍 running、十二 Dataset Receipt 保留；Store Receipt、`ecom_link`、projection pending、
  runtime pending 与 canary 均为 0。本波只转移 BL 留存的冻结输入，不读取商城源数据，不调用
  `run_definition`。
- 当前唯一外置 Runtime Host保持运行；纯 HTTP阶段不得停止它。“第二 Host=0”按外置 Host总数=1
  执行，不再误读为外置 Host总数=0。

## 2. 串行步骤 1-6

1. **plan/preflight**：固定上述 BO、definition rev118、attempt=0、十二 Run/Receipt、零副作用边界、
   单写者 m1 与一个外置 Runtime Host。
2. **纯 HTTP 18181**：在现有 Host不停机的前提下启动一个受控纯 HTTP API；读回 Cron=false、
   snapshot worker=false、进程内 Runtime Host=false；外置 Runtime Host总数恰好1，第二 Host=0。
3. **冻结输入转移**：prepare、schedule-ingest、controls；关闭18181并确认端口释放；从 BL
   rev118 disabled/recovery rev38 执行 transfer -> BO rev119 disabled、renew -> recovery rev39 /
   definition rev120 enabled，enable读回 `sourceReads=0`。
4. **唯一自然 worker**：以 exact lease启动同一个 supervisor/worker；固定 BO installation、
   generation、definition rev120、recovery rev39、数据库 accepted_at与request hash。禁止手工
   `run_definition`、第二 worker、第二 Runtime Host或第二 attempt。
5. **单轮观察窗**：每50秒只读采样唯一 attempt直到正式 terminal；若300秒出现
   `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED` 且十二 Run仍 running、Store Receipt=0、
   `ecom_link`=0、projection pending=0，则不重发，在原 accepted_at起算的1800秒有界预算内继续
   同一 attempt。unknown只冻结边界，不猜测成功。
6. **终态/verification/commit**：正式终态及零副作用读回后，pause-terminal -> definition rev121
   disabled；若进程需停止，先SIGTERM，有界180秒后仅在 exact terminal/attemptCount=1/零副作用/
   PID与进程组精确匹配时允许一次SIGKILL。落盘verification、测试、精确提交，然后自动进入
   failed/terminal retirement + direct successor波。

## 3. 停止条件

- 任一 identity、Receipt/hash、definition/recovery revision、十二 Run/Receipt或route/binding漂移；
- Cron、snapshot worker或进程内 Runtime Host在纯 HTTP阶段被启用；外置 Host总数不等于1，或出现
  第二 worker/attempt；
- 商城源读取、`dev-org/dev-project`非零写、Store Receipt/ecom_link/projection pending；
- 未知提交边界、手工 `run_definition`、300秒失败后重发或更换idempotency key。

所有非人工决策型工程阻断由当前唯一开发在上述边界内自行诊断、最小修复与继续；不push、不动其他
分支，230 L0继续挂起。

## 4. 执行中实现修复

- transfer 前本地 BL `renew-result.json` 已随旧运行目录丢失；数据库 readback仍提供 exact recovery
  rev38/hash，且与已提交 BL verification一致。BO wrapper只接受该固定 ref并将其写入结果，不重建
  predecessor、不放宽 revision/hash。
- 首次正式 transfer在事务内因旧 definition 的 1.23.1 `policyRef`不属于 BO 当前 1.23.2 release而
  回滚。根因是共享 `transfer_saved_recovery` 更新了 members/installation，却错误保留 predecessor
  policy version。修复限定为：仍以旧 policy的同一 exported path为约束，在目标十二-member current
  group guard内由 Registry解析目标 release的 exact policy ref，再进入既有 policy owner验证与保存；
  禁止调用方提供新hash或绕过 artifact/release校验。补充回归测试后，数据库确认 rev118/recovery38
  未变，才允许用原 idempotency key继续。
- renew的 successor read-semantics门进一步读回：十二组差异仅为 mapping/schema/masking exact ref的
  canonical alias revision `1.23.0 -> 1.23.2`，每一项 resourceType、resourceId、contentHash均完全相同；
  其余读取参数相同。共享 contract仅允许这种同实体同摘要的revision推进，任一路径、类型或hash变化
  仍fail closed。
- 数据库 `a0v_087`触发器复制了旧的全等判断，因此应用层通过后仍回滚。现有schema head为
  `a0v_089`，新增其直接后继 `a0v_090`仅同步上述
  两项契约，部署前生成独立备份并要求迁移前后四张 authority表指纹完全相同；禁止禁用约束或改写
  现有业务行。
- 首次 `a0v_090`部署在同一事务的函数文本读回阶段因验证marker空格格式不匹配而回滚，数据库仍为
  `a0v_089`；原backup/intent保留。修正marker后使用独立v2证据目录和新备份重试，不覆盖失败证据。
- 首次启动自然 worker 前的只读预检确认 BO attempt=0、Host=1、worker=0；通用
  `a0v_snapshot_product_api.py`仍固定 BL 的旧 lease/task 与状态目录，而当前 lease 清单已无该旧任务，
  因此子进程在创建 attempt 前按设计退出。不得伪造或复活 BL lease；新增 BO 薄封装，仅固定 BO task、
  BO 状态目录并加载现有 BO signed launcher，底层 worker 不改。共享 lease 清单只登记本波单一 worker、
  排除源读取、手工 run_definition、第二 worker/Host、dev-org mutation与push。
- BO worker启动后，第一次自然 tick于 `2026-09-20T10:28:12Z`生成 attempt
  `57881020-86fe-44cc-be3e-2cd90787205e`，第二次自然 tick于 `10:28:37Z`生成 attempt
  `9d1fc481-7eb2-426f-8b0b-65627f06ec97`；两者均以同一 request hash正式失败为
  `RECOVERABLE_EXECUTION_EXCEPTION / RuntimeConflict`，后者被50秒采样发现后 supervisor立即SIGTERM，
  未升级SIGKILL。十二Run仍running且全部业务副作用为零。该边界不得重跑BO；先修复两处共享缺陷，
  再stop-only关闭definition并进入正式退休/direct successor：其一，source claim successor校验也必须
  接受已经由 recovery authority验证过的同类型、同路径、同摘要 artifact alias revision；其二，worker
  一旦得到 `SNAPSHOT_EXECUTION_UNCONFIRMED`，必须退出本轮serve而非自动进入下一tick。当前波结论改为
  两个正式失败attempt的冻结完成，不得宣称“唯一attempt成功”。
