# W5CB4 P2g｜已结算内容→主体 Eval→人类待办的离线接线（施工前）

## 上位目标与边界

- 依据 231-5 §1/4/5/7、231-9 BG-04、栖月汇产品方案及 W5CB4 总方案：内容必须是同一安装代次、原 TaskRun/Plan/Brief、真实商品和来源下的可读 Artifact；经正式结构/来源 Eval 后进入人工 exact 评审。机器不替人判断事实/合规，不自动发布或触达。
- P2d 已有受控内容结果的正式生成 StepRun；P2e 有内容主体 Eval 输入与策略 ref；P2f-a 令原 Plan gate 必须 exact；P2f-b `b771dc66` 在新 Plan 创建前读唯一当前内容权威。当前实例 `a0v_092`，预审包未安装，运行时链仍默认关闭。P2f-b 安装 executor 的多提交/未知结果对账暂列恢复队列，不阻断本波隔离、无副作用的核心编码。

## 文件级顺序与失败关闭

1. 只读审 `ecommerce_content_result_consumer.py`、`ecommerce_content_step_owner.py`、`aip_eval_runner.py`、`aip_production_contract_store.py` 的 Artifact、最新生成 StepRun、EvalReport、ReviewIssue 字段和当前安装权威；选一个由原生产链持久对象组成的 exact 候选键。先不要从测试夹具的任意报告生成待办。
   - 先行安全断点：公共 `create_review_issue` 目前对内容报告只核存在、同主体/attempt/原 Plan，不核 `gate_passed`；`ContentReviewHostService._issue_eval_authority` 的 ACCEPT 也未核结构预审通过。P2g 第一小改动先 RED→GREEN 封住 ACCEPT：失败报告可保留人工 RETURN 处置，但不能作为通过结构门的 ACCEPT；不改媒体/文本旧路径，也不把结构通过写成事实/合规通过。
   - 第二安全断点：`AipEvalRunner._assert_media_subject` 对内容只验 StepRun 身份/最新 attempt，未要求 `content_generate` 已正式 `succeeded`；现有正向测试甚至在刚 claim 的 StepRun 上跑内容 Eval。先把该隔离测试修成真正四相 TAOR 完成，再加未完成 attempt 的 RED；仅内容主体新增 succeeded 门，媒体/文本旧语义不动。主体 Eval 不可抢在已结算生成步骤前。
   - 纵深防线：内容 `create_review_issue` 和 Host 读取历史报告时也必须核最新生成 StepRun 的 `succeeded`，防止绕过新版 Runner 的旧报告/直写报告进入人工路径；先改邻近测试 RED，再仅在内容分支核状态，不改其他领域的 StepRun 规则。
2. 第一段先加 RED，再做 `services/aos-api/aos_api/ecommerce_content_review_pending.py` 只读候选投影。只有**已结算** Artifact、原 TaskRun 的 `content_generate` 最新 succeeded StepRun、原批准 Plan exact EvalContract gate、同一当前安装/Task/Brief、同一 Artifact/attempt/合同的通过报告才返回一个待办候选；缺失、跨租户、旧 attempt、错合同/hash、旧安装、失败报告、已有决定均为零或明确 blocked。GET 不创建 EvalRun/ReviewIssue，不写库。
3. 第二段在单独方案/测试下接正式主体 `AipEvalRunner`，按持久 intent／唯一候选键先只读对账再调用；EvalRunner 内多提交发生未知时冻结，不自动重跑。正式报告独立读回后才走公共 `create_review_issue`，不能拿治理报告或空壳 Artifact 代替。人类 resolve/return 沿既有公共 API 和 Host exact Receipt；worker 无代批权限。
4. 后续 ACCEPT 完成 `content_review` StepRun/TaskRun 正式终态，RETURN 形成新内部生成目标；反馈读回总控/Wiki 候选。每段都先专项、累计、隔离 PG、方案/代码复审、verification、m1 commit、AOS/Prime 上下文。若涉及页面做真实浏览器验收；纯后端段标不适用。

## 本轮首段停线

- 在当前实例无正式内容预审包、无合法真实 Artifact/报告时，只能给出默认关闭的代码与隔离验证，不开放生产 GET 的虚假待办。任何未知提交/当前安装不明、Report/Plan/attempt 不一致都失败关闭。
- 不读商城源，不回放原 12 Run，不推进 230 L0；`dev-org/dev-project` 仅零 canary；m1 单写、不 push。

## P2g 待办候选第一子步文件级细化（2026-09-27）

- `services/aos-api/aos_api/ecommerce_content_review_pending.py` 先只提供内部 `read_one(scope,reservation_id)`，不加 GET 路由、不创建 Issue。复用 `ContentGenerationStepSource.read` 的已结算 Result/Provider/Usage/Artifact/Task/Brief 来源读回和 `ContentGenerationStepOwner._readback` 的 TAOR/checkpoint；另核原内容操作 Receipt 与当前 dispatch/runtime binding exact 相等。后续 Host 仍需完整安装锁，不把 GET 的只读快照当写授权。
- 同一只读事务读取唯一内容报告、EvalRun、最新生成 StepRun、原 Plan gate 和当前内容合同；要求 report canonical hash、gate_passed、同 Artifact/attempt/合同、EvalRun succeeded。无报告返回 `None`；任一多义/漂移/撤销/旧安装抛出 `ContentReviewPendingBlocked`，不能自动造报告或审批。候选身份用 `(scope,reservationId,runId,artifactId,stepRunId,reportId@revision)`；重复只读返回相同值。
- 测试先在 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending.py` 用无写连接验证无报告、错租户、旧 attempt、错合同/失败报告、重复读稳定；再用隔离 PG 组合真正 settled Artifact/StepRun/EvalReport 的正向证明。若本子步做不到同库正向，verification 必须标为部分代码门，不得暴露生产 GET。

## 下一子步：正式同库组合测试清单（2026-09-27，编码前）

- 新 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py`，仅用一次性 `disposable_database` 和正式迁移；可复用现有 `test_ecommerce_content_generation_step_owner.py` 的公共 Task/Run/四相 TAOR、`test_ecommerce_content_pre_review_eval.py` 的正式 Graph/两 Suite/Gate/Publication/冻结合同，以及 `test_aip_ecommerce_content_eval_input.py` 的主体 EvalRunner。不得将其中任一夹具单独当正向候选；必须是**同一**原 TaskRun、reservation/invocation、已结算预算与 Provider/Usage Receipt、可读 Artifact、succeeded StepRun/checkpoint 和主体报告。
- 首个 RED 应直调新的 `ContentReviewPendingReader.read_one` 且不 monkeypatch 来源、当前 dispatch、合同、报告或 Run 校验；在同一数据库里读回稳定候选。随后分别篡改/撤销当前合同或发布、换租户、换安装代次、旧 StepRun、失败/重复报告、已有 Issue，证明零候选或明确 blocked；测试对故障做回滚/独立作用域，不污染后续用例。
- 若真实 Provider 结果/预算结算 fixture 需要仍未定义的外部权威，不向当前实例调用 Provider；先在隔离库通过已存在 `ContentResultConsumer` 的受控持久结果/Usage Receipt 路径构造。若该路径无法在测试环境形成正式 Receipt，记录具体缺口并先补测试可复用的正式最小 fixture，不放宽读取器、不返回 mock 候选。当前实例 `a0v_092` 仍不迁移、不启 Worker。

### 分段验证入口

- 现有 `test_aip_ecommerce_content_eval_input.py` 的一次性完整迁移库已持久 Task/Plan/Run、四相成功 StepRun、可读 Artifact 与真实 EvalRunner 报告，但尚无预算结算/Provider/Usage/当前 dispatch。先在该测试内验证候选读取器对**真实报告/Run JSONB 和原 Plan gate**的兼容性；仅针对缺失的来源/dispatch/checkpoint 注入替身，明确只是一段组合子证据，不能取代上述全链 RED/正向。
- 同时审既有 `test_a0v_content_result_consumer_pg.py`：它确有预算/Provider/Usage/Artifact 的正式消费测试，却运行在精简临时 schema、需 `AOS_EXTENSION_PG_TEST=1` 且本机 18432 未监听。不得把两个不同数据库的绿色结果拼成“同一对象贯通”。后续必须在一个完整迁移的一次性库里组合，或记录正式 fixture 缺口。

### P2g 前半段同库 fixture 第一增量（2026-09-27）

- 在 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py` 新建只用于完整迁移一次性库的 fixture；第一 RED 仅证明**原公共 Task/Plan/Run 与正式 BudgetRevision、PriceSnapshot、ActionApprovalEvent 经 `AipBudgetReservationStore.reserve` 形成 held Reservation**。此步仍不声称 settled 内容或待办，不调用真实 Provider。
- Seed 仅限隔离库、显式列名、完整迁移约束；不得复制精简 schema 的位置型 INSERT，也不得改生产预算/审批规则让测试通过。失败时查确切缺失字段/权威并修 fixture；若必须修改公共生产规则，另起方案波次。
- 后续沿同一数据库和同一 Task/Run/Reservation 追加正式 journal、受控结果、Usage/Artifact/settlement、TAOR、主体 Eval 与候选读回；任何段落必须说明尚未覆盖的门。运行专项与内容累计后单独 verification/commit，防止把局部绿误称全链。

### P2g 前半段第二增量：正式 command 与 runtime Receipt（2026-09-27，编码前）

- 延伸同一 `test_ecommerce_content_review_pending_pg.py` 的完整迁移一次性库，不另起精简 schema。用正式 `ContentExecutionJournal.enqueue` 持久原 held Reservation 的 exact 内容命令；用隔离库合法 `bundle_installation`、当前 `extension_runtime_binding`、`extension_operation_dispatch_binding` 与 `BoundEcommerceGrowthRuntimeStore.put` 形成同一命令的 PENDING runtime Receipt。所有测试安装行仅在自动删除的克隆库中，不代表当前实例已启用。
- RED 首验 `ContentExecutionJournal.list_held` 只选这一条原 reservation；同命令 replay 不复制 journal 或 runtime Receipt，篡改 command/request hash 必须 fail closed。禁止直接插入 runtime Receipt 伪造成功；测试运行时不启 Worker/Provider。
- 专项、内容累计、verification 与精确提交后，再进入受控 Provider 结果/Usage 与预算 settled。若全库的约束要求额外正式安装权威，先记录确切缺口，不调整生产规则以迎合 fixture。

#### RED 发现：runtime Receipt 哈希语义错配

- 完整库通过正式 `BoundEcommerceGrowthRuntimeStore.put` 写入 PENDING Receipt 后，`ContentReviewPendingReader._current_dispatch` 仍拒绝：runtime Receipt 的 `request_hash` 是 `_request_hash(command)`（含内部 `requestHash` 的**全命令哈希**），而读取器错误地对比内部 `command['requestHash']`。`CurrentContentPreparation.__call__` 与 `ContentGenerationStepOwner._current_dispatch` 有同型比较，导致真实持久命令被误挡；不是权限/Provider 错误。
- 代码最小修复范围只含 `services/aos-api/aos_api/ecommerce_content_review_pending.py`、`ecommerce_content_execution_composition.py`、`ecommerce_content_step_owner.py`；统一复用正式 runtime writer 的 `_request_hash(command)`，不改 Receipt 格式/数据库/既有命令内部哈希。测试在完整库经正式 Store 写正向 Receipt、同命令 replay、篡改命令拒绝及 runtime fence 拒绝；其余现有 Worker/Owner/候选测试累计回归。未能完整通过真实安装链之前，不以本测试代表生产授权。

#### 迁移基线校正

- `disposable_database` 的模板经只读核对实际是 `a0v_011`，现有 `apply_migrations` 只手动补 `a0v_012/013` 而不推进 Alembic 版本；所以前一提交 `25e162bd` 所称“完整迁移库”应改为“旧模板加两项迁移的隔离库”。Budget held 的 API/重放证明有效，但**全迁移约束未证明**。
- 本波先在测试中只针对 `a0v_growth_graph_test_*` 精确克隆使用 Alembic 正式 upgrade head，核版本和 dispatch lock 函数；不接触 `aos_meta_head` 或真实安装。若升级失败，记录具体迁移缺口并停止“全迁移”称谓，不逐个补函数假造环境。升级后重跑预算与 runtime Receipt 测试，再决定后续受控结果路线。

### P2g 第三增量：同库受控结果与结算（2026-09-27，编码前）

- 继续只改 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py` 与必要的生产缺陷最小文件；仍用正式 Alembic head 的一次性克隆、同一原 Task/Run/Reservation/command/runtime Receipt。先读现有 `ContentExecutionWorker`、`ContentResultConsumer`、`ContentUsageRecorder` 与 ProviderInstanceRevision 权威，形成文件级测试夹具；需要的 Provider/route/price 必须经正式数据库约束和现有 Owner API，不以猴补 `_provider_authority` 过门。
- 在测试中使用受控本地响应，不做网络 Provider 外呼；`ContentExecutionWorker` 正式提交预算并先持久 Provider 请求 Receipt，随后持久结果；单独 `ContentResultConsumer` 记两条 measured Usage Receipt、可读 Artifact 和 settled 预算。受控 prepare/context 接缝必须逐项标注，不能写成当前真实方法/商品来源已验收；无结果/未知边界不重发。
- RED 先证明已持久结果能由原消费路径结算且同一 invocation 的 Receipt/Artifact/TaskRun 身份一致；负向注入结算失败应整个 Usage/Artifact 事务回滚并保留原结果供只读对账。若最小正式 Provider 权威 fixture 过大，列明 API/表/FK 缺口后转做不依赖它的首链 Review Owner 安全门，不把单一测试夹具无限延期。

### P2g 第四增量：同库生成 StepRun/checkpoint（2026-09-27，编码前）

- 仅延伸 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py`。在正式 `a0v_105` 一次性库中复用上段原 Task/Run/Reservation 的 settled Artifact/Provider+Usage refs；`ContentGenerationStepSource.read` 保留唯一显式业务 context 接缝，其余预算、journal、Artifact、Run 正式查询。RED 要求 `ContentGenerationStepOwner._complete_transaction` 经真实 AIP Store 写同一 `content_generate` 四相 TAOR 与 succeeded StepRun，再由独立连接 `_readback` 验 checkpoint、observe 中 exact Artifact/Reservation；重复原对象只回读，不新增 attempt。
- 由于完整九操作 Host 锁、非超级用户 serializable 隔离身份尚未组成，本段**不调用** `run_one`/自然 worker，也不猴补 `CurrentContentPreparation._lock_dispatch` 后声称运行授权。内部原子提交子证明与生产外层 Host 门分列；若 StepRun/Checkpoint 发生未知提交，停止重跑并只读对账。负例错 Artifact/ref 要 fail closed，不能靠手工构造第二 Run。
- 专项、累计、verification、m1 commit、AOS/Prime 同步后，下一段在同一原 Artifact 上接正式当前 EvalContract/Plan gate 和主体 EvalRunner；若合同注册 fixture 仍大，先明确缺口，不开放 GET/Issue。
