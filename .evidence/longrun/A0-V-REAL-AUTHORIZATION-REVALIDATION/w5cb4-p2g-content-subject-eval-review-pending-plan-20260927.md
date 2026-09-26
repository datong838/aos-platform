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

### P2g 第五增量：原 Artifact 的当前 Eval 权威与主体报告（2026-09-27，编码前）

- 只扩 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py` 的一次性正式 `a0v_105` 同库测试与必要 helper，不改生产合同/Runner 门。先依现有 `ecommerce_content_pre_review_eval.py`、pack、`AipEvalPackRegistry`、`LogicGraphStore`、`AipReleasePublicationService` 和 `AipProductionContractStore` 正式 API 注册 Graph、治理及主体 Suite、发布门/事件、冻结 READY 内容合同；当前 gate 必须在**原** Plan 创建前写入 `content_review.gateRefs`，不能事后改批准 Plan。
- 原内容结果、settled 预算、Provider/Usage Receipt、Artifact 与唯一 succeeded `content_generate` StepRun/checkpoint 保持同一对象。用 `AipEvalRunner.run_by_contract` 对该可读原 Artifact 和最新成功 attempt 跑主体结构 Eval，独立读回报告/EvalRun、exact 合同、Artifact、StepRun 和无正文泄漏；受控 Graph target/judge 是隔离测试执行接缝，不代表真实商品事实通过。首个 RED 先暴露正式 fixture 的最小缺口，禁止直写伪报告。
- 同库组合成本若超本增量，先落可验证的正式合同/Plan gate 子证明、列出缺口与下一步，不放宽 `ContentReviewPendingReader`。对失败/未知提交只读对账；不重复 Eval/Provider，不开放 GET/Issue/自然 worker。专项、累计、verification、m1 精确提交、AOS/Prime 同步后继续下一波候选读回。

### P2g 第六增量：原对象只读待办候选（2026-09-27，编码前）

- 只在同一 `test_ecommerce_content_review_pending_pg.py` 的第五增量原对象上扩断言，不另建报告或插入伪 Issue。以显式业务 context Source（其余查询正式）调用 `ContentReviewPendingReader.read_one` 两次，要求同一 `(Reservation,Run,Artifact,StepRun,Report@revision)` 候选，读取前后 EvalRun/Report/Issue/StepRun 计数不变；独立 SQL 核身份。
- 紧邻负例先限于不改不可变生产记录的错租户和错 reservation，及隔离事务内可回滚的当前 dispatch fence/合同撤销；任何 blocked/None 均不可写、不可重发。若读取器发现实际约束错配，先 RED，再对生产最小修复并覆盖旧单测；不通过猴补读取器/报告/合同过门。此波仍不开放 GET、Issue、Provider 或自然 Worker；后续单独波做更多多义/旧 attempt/人工 Issue。
- 专项、累计、浏览器不适用说明、verification、精确提交、AOS/Prime 同步之后才进入下一波。

### P2g 第七增量：同库候选→正式人工 Issue（2026-09-27，编码前）

- 依据 231-5 首链“可读产物→人工评审”和 231-9 BG-04，优先在同一原 TaskRun/Artifact/StepRun/Report 的隔离正式库，把第六增量只读候选交给 `AipProductionContractStore.register_review_rule_revision` 与 `create_review_issue` 的公共 API；不从候选读取器增加写入，也不直接 INSERT Issue。文件只扩 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py`，生产规则有真实 RED 缺陷才另列最小文件。
- `CreateReviewIssueRequest` 必须绑定候选 exact Artifact/hash、通过的主体 EvalReport/revision/hash、当前人工 Rule；明确 location/returnStage。RED→GREEN 后独立 SQL 读回唯一 Issue、原 Run/Artifact/Report refs；重复同 idempotency key 不产生第二 Issue，已有 Issue 时 `ContentReviewPendingReader.read_one` 返回 None。此段不自动 ACCEPT、不完成 review StepRun、不外发；正式人类决策与 Host Receipt 留下一波。
- 若公共 API 对同库原对象拒绝，先查完整错误/约束，禁止改库填伪 Report 或放宽 gate；可转做更直接的首链 review command 接线，但 verification 必须标出未通。错合同、旧 attempt、重复/失败报告等已有单测仍累计回归；其余同库负例作为待办，不压住主线。专项、累计、浏览器不适用、证据、m1 精确提交、AOS/Prime 更新后自动续波。

### P2g 第八增量：同库 exact 人工 ACCEPT 事件与 Host 读取（2026-09-27，编码前）

- 仅在第七增量原 Issue 测试上用 `AipProductionContractStore.resolve_review_issue` 的正式命令，传人类 reviewer actor、expected version、理由和原 Artifact exact resolutionRef；同幂等键 replay 无第二事件。隔离测试 reviewer 只是模拟一个真实 API 调用，不宣称栖月汇人已批准。独立读回 resolved Issue、序号 2 的不可变事件与 create/resolve Receipt；不直接 UPDATE Issue。
- 再用 `ContentReviewHostService._issue_authority` 与 `review_issue_exact_ref` 在同一库验证 Host 可读取 exact 已批准 Issue、通过的原 EvalReport/最新 StepRun 和人类事件；旧 open Issue、错 Artifact/Report 或无 resolutionRef fail closed。此波只证明 Host 的 Issue/Eval 子门，完整 `revalidate/execute/verify_receipt` 还需要合法 TaskBrief、ReviewerAuthority、九操作锁与当前安装，不用猴补称业务续跑。文件范围仍只扩同库 PG 测试；生产缺陷需 RED 后另列。
- 专项/累计、证据、m1 提交、AOS/Prime 更新后，下一波优先组成其余 Host 门和 receipt-first review→反馈自动续跑；生产默认关闭。

### P2g 第九增量：同库正式 Brief 与四个来源 Artifact（2026-09-27，编码前）

- 231-5 的产物不能只有技术 ID；当前同库夹具虽有可读受控内容、结算和人工 Issue，却从预算单测复用了占位 `briefRef`/四个 `sourceArtifactRefs`。这不是完整 Review Host 权威。只扩 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py`：在原 TaskRun 上由正式 `AipTaskStore.record_artifact` 创建四个唯一不可变来源 Artifact，由 `AipProductionContractStore.create_brief` 创建同 Task、同 GrowthPlanRef/四来源/禁止外发的 draft 内容 Brief。沿原 content.generate 命令替换 exact refs 后重新计算正式 command hash，再入 journal/runtime Receipt；不直接改已提交命令。
- 保持其余已证明的同一结果→settled→StepRun→Eval→Issue→模拟 reviewer 事件。随后用原已 resolved Issue 构造 content.review 所需 exact Artifact/Task/Brief/GrowthPlan/四来源片段，调用 `ContentReviewHostService._artifact_authority` 与 `_task_brief_authority` 的真实数据库读回；篡改 Brief/来源 ref 应 fail closed。只证明这两道 Host 子门；ReviewerAuthority、完整 review dispatch/Receipt、九操作锁、TaskRun 终态和反馈仍是独立未完成项。
- 先 RED 暴露最小约束，再改隔离 fixture；不放宽生产校验、不读商城源、不触当前实例。专项、累计、verification、m1 精确提交、AOS/Prime 更新后进入下一波 ReviewerAuthority/完整 Host；若注册正式 Brief/来源 fixture 过大，则记录具体缺口并转做 Review 终态 Owner，而非长期死磕夹具。

### P2g 第十增量：正式评审 Receipt → 原 Run 终态 Owner（2026-09-27，编码前）

- 上位 231-5 §1/4 明确 `content_review` 的 Artifact/ReviewDecision 后应先有 TaskRun 终态，`feedback_pending` 才接 EffectReview/总控/Wiki 候选。现有 `CurrentFeedbackConsumer` 正式筛选要求原 Run `succeeded` 且 Task `completed`；当前没有内容评审终态 Owner。因此不再把补齐隔离 ReviewerAuthority fixture 作为唯一主线，先实现这段缺失的消费端合同，但不得绕过完整 Host `revalidate/execute/verify_receipt`、当前安装和真人事件。
- 文件级范围：新增 `services/aos-api/aos_api/ecommerce_content_review_step_owner.py` 与 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_step_owner.py`；如需隔离 PG 正向，只扩 `test_ecommerce_content_review_pending_pg.py` 的原对象链。先写 RED：无 Receipt、只有 resolved Issue 无 Host Receipt、RETURN、旧/错 dispatch、错 Artifact/Brief/Issue、旧生成 attempt、重复/未知边界均不能创建 review StepRun 或完成 Run；同一正式 ACCEPT Receipt 的重读稳定且没有第二 attempt。
- Owner 的只读 source 必须从**当前 content.review runtime Receipt 和同 Receipt 的反馈 command**反查原 Artifact/Task/Brief、唯一原 running Run、最新 succeeded `content_generate` StepRun/checkpoint、原批准 Plan 的 `content_review` 与通过的主体 EvalReport、已 resolved 的 exact Issue/事件；Receipt body/hash、dispatch/runtime binding、安装代次、feedback 第一片段必须与 Host 写入相等。候选读取不是执行许可。
- 写事务在当前 Host 九操作锁下重新验证上述权威，使用 `AipTaskStore` 原公共 API 在同一事务写 `content_review` 的 think/act/verify/observe、完成 StepRun/checkpoint、`complete_run`；TAOR action pin 原 Receipt，observe pin 原 Artifact/Issue，不发 Provider、不创建外部效果。独立连接回读 StepRun/Checkpoint/TaskRun/Task/Receipt/反馈；任一提交边界未知只冻结并只读对账，不自动二次 claim。只允许现有确切 ACCEPT；RETURN 另波走新内部目标，不把原 Run 强行 succeeded。
- 先验证 isolated unit 的只读门与原子事务，再完整迁移一次性库组合 Host Receipt→终态→`CurrentFeedbackConsumer.list_pending`，不 monkeypatch 核心权威以伪造全链。若完整 Host/ReviewerAuthority/安装锁未组成，verification 明确只到子门，保持自然 worker 关闭；禁止把单独 Owner 测试称为真实用户评审或生产续跑。专项、累计、浏览器后端不适用说明、方案/代码一致性复审、verification、m1 精确提交及 AOS/Prime 同步后，进入完整 Host 与反馈自然消费波。
- 编码前安全审计发现 `ContentReviewHostService._reviewer_authority` 目前只匹配 current READY/COMPLETE 的 `content.review` slot，却没有把 slot 中的人类 assignee 与 exact ReviewIssue 第 2 号决定事件的 `actor` 相等；一个人的决定可借另一个人的责任计划过门。先在 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_authority_feedback.py` 加错 actor 的 RED，再仅修改 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py` 该函数：必须有第 2 号事件、human_principal 且 assignee.resourceId=event.actor，其他 Host 语义不动。该门修好再组正式 ReviewerAuthority/Receipt，否则 Owner 不能接收 Receipt。
- 完整 Host RED 又暴露 ReviewIssue ref 的 `receiptId:null` 语义错配：`_strict_content_review_command` 使用 `_content_exact_ref`，要求 canonical `exclude_none=True`；但 `_issue_authority` 内部 expected ref 曾保留 null，导致合法命令永远不能同时过两个门。仅把 Host 内 expected ref 规范为 `exclude_none=True`，测试采用同一 canonical ref；不放宽 ref 结构、hash、issue 状态或人工事件。
- 在一次性全迁移库用非超级 `aos_runtime` 和九操作 serializable 锁试 `run_one` 的新 RED：Host `_artifact_authority` 的 `SELECT ... FOR SHARE` 因 `aip_artifact` 只授 SELECT、刻意不授 UPDATE 而被数据库拒绝。不得为过测试给不可变 Artifact 表加 UPDATE；最小修复仅移除该 Artifact 查询的行锁，保留同事务 serializable、九操作锁与 exact 不可变 Artifact/hash/四来源复核。再跑同库公共 `run_one`，若下一权限门失败逐个查权限根因，不扩大表写权限。

### P2g 第十一增量：自然 review 终态拾取（2026-09-27，编码前）

- 上位 231-5 的“人工评审后系统自动续跑”不能靠开发者调用 `run_one`；第十增量已在一次性库证明同一原 Run 的 exact Receipt→正式终态→feedback 可选，但新 Owner 尚无自然轮询。文件级最小范围：`services/aos-api/aos_api/ecommerce_content_review_step_owner.py` 加有界 `run_once/serve`；`services/aos-api/aos_api/main.py` 增独立默认关闭的启动门；`services/aos-api/tests/extension_runtime/test_ecommerce_content_review_step_owner.py` 加 RED/单测，并复用同库 PG 用例证明 selector 只给唯一 pristine Receipt。`AOS_ECOM_CONTENT_REVIEW_STEP_WORKER_ENABLED=false` 为默认，不能沿用别的 worker 开关暗启。
- `run_once` 只在 `list_pending` 得到唯一 current ACCEPT Receipt 后调 `run_one`；当前 Host/权威冲突可报告 `BLOCKED_CURRENT_AUTHORITY` 且不创建新 attempt。`ContentReviewStepUnknown`、意外数据库/提交错误必须抛出让整个 worker FAILED_CLOSED，不自动重试。`serve` 固定正租户 `org-org/dev-project`，每轮须 Host task 仍 ACTIVE；启动先核独立 runtime DSN、Host 存活和 flag 合法，任何失败无任务遗留。不得在本波打开当前实例开关或调用真实 reviewer/Provider。
- RED→最小实现→专项/累计→后端浏览器不适用→方案/代码复审→verification→m1 精确提交→AOS/Prime 更新。之后下一波用同库 feedback 第一段正式 target Receipt/EffectReview 与总控/Wiki 候选读回；签名模板/当前真实安装仍单独验，不以模拟人工或受控商品文本宣布首链完成。

### P2g 第十二增量：同库自然反馈第一段 target Receipt（2026-09-27，编码前）

- 231-5 的 `feedback_pending` 必须由原 TaskRun 终态进入正式反馈接收端，不得仅凭选择器返回 command 就称复盘完成。文件级最小范围先只扩 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py`：在第十一增量同一 `a0v_105` 一次性库、同一原 Run/Review Receipt/反馈 command 上，以非超级 serializable `aos_runtime` 调用现有 `CurrentFeedbackConsumer.run_once`/`DailyReviewFeedbackWorker`，不造第二命令或直接 INSERT target。
- RED 首验运行身份能经 `claim_current → require_current_origin → BoundDailyReviewTarget.put → acknowledge` 原子形成唯一 `DailyReviewReceipt`；独立连接读回 target 行、Receipt/hash、反馈第一段 `acked`/attempt=1/checkpoint=1，第二、三段仍 pending/attempt=0。重复同 command 不新建 target、不推进到未接线片段；错安装/旧 Run/非当前 Receipt 必须无效。若数据库权限门拦截，查确切 RLS/函数授权并最小修复，不加宽全表写权限。
- 专项、累计、浏览器不适用、方案/代码复审、verification、m1 精确提交与 AOS/Prime 同步后，下一波优先拆清 improvement observation 与 memory candidate 的正式目标及总控/Wiki 治理门。当前实例仍不开 worker、不读商城源，不以隔离受控来源宣称经营闭环。

### P2g 第十三增量：第二段待观察目标与原命令回执（2026-09-27，编码前）

- 上位 231-5 §4/7 与 231-9 BG-04 要求原 TaskRun 终态后的总控复盘，且产品方案明确没有真实成交观察时不能声称增长。当前反馈第一段已有原命令的 `DailyReviewReceipt`；第二段 `improvement_observation` 仍是未接线片段。`AipEffectReviewStore.create_review` 自开事务，并要求独立效果输入，不能在反馈持锁事务中偷调后当作同一原子提交，也不能以 `sample_count=0` 冒充效果完成。
- 文件级范围：新增 `services/aos-api/alembic/versions/a0v_106_ecommerce_improvement_pending_target.py`、`services/aos-api/aos_api/ecommerce_growth_improvement_target.py`；最小修改 `services/aos-api/aos_api/ecommerce_growth_feedback_consumer.py` 增第二段有界 selector（或独立 consumer，选现有接口最小改动），`services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py` 延长同一原命令正向；新增 `services/aos-api/tests/extension_runtime/test_ecommerce_growth_improvement_target.py` 做输入/回放/错误边界。若实际迁移 head 已变化，先只读核对并换名，不造分叉。
- RED：第一段未 ack、原 Run 未 `succeeded`/Task 未 `completed`、旧安装/dispatch、错 `DailyReviewReceipt`、错原 review/artifact/task/brief、第二段旧 claim/多义目标均不能写目标或推进 checkpoint。正向在一次性正式迁移库、非超级 serializable `aos_runtime` 中以原 command/segment 2 经 `claim_current→require_current_origin→target.put→target.read_receipt→acknowledge`，形成唯一不可变 `ImprovementPendingReceipt`，checkpoint=2；重复读取只返回原回执，不新增 attempt/目标。
- 目标 body 只写原 exact refs、第一段 Receipt、业务标题/摘要、同一安装代次及 `effectStatus=AWAITING_COMPARABLE_EVIDENCE`；不写“效果改善”“成交增长”“Wiki 已入库”。数据库函数用当前 scope/RLS、原命令/Segment/Lease/Checkpoint、当前 dispatch/runtime、原 Run 终态及第一段已 ack 回执共同约束，并在同一事务内写唯一目标；不得借超级用户或跨连接提交绕门。未知提交只读对账，不重发。
- 本增量不调用 Provider、商城源、AIP 效果评估或 Wiki 发布；当前实例不开 worker。第三段 `memory_candidate` 及正式 EffectReview/总控投影在下一波。专项→累计→方案/代码一致性复审→verification→m1 精确提交→AOS/Prime 更新；纯后端且生产默认关闭，浏览器验收不适用。若受控同库证明缺门，记录具体失败并修最小权威，不放宽当前边界。
- RED 权限探针发现数据库对新表应用了 `aos_runtime=arwd` 默认授权，单纯 `REVOKE ... FROM PUBLIC` 后 `GRANT SELECT` 并不能收回该运行角色的直接 INSERT/UPDATE/DELETE。第十三增量迁移须显式撤销新目标表及同类第一段 `ecommerce_growth_daily_review_target` 的直接写权限，仅保留 SELECT 与受控函数 EXECUTE；同库以实际 `has_table_privilege` 和原第一段回归证明权限收紧不破坏合法消费。不能放宽 RLS 或给运行角色表级写权。

### P2g 第十四增量：正式 EffectReview 的不足证据状态先于 Wiki 候选（2026-09-27，编码前）

- 231-5 §4/7 明确反馈顺序是原 Run 终态→EffectReview→总控/WikiCandidate；231-9 首链与产品方案禁止把内容获批等同效果成熟。第十三增量第二段只是 `ImprovementPendingReceipt`，不能跳过正式 EffectReview 直接把第三段当已成立 Wiki 候选。先复核 `AipEffectReviewStore`/`CreateEffectReviewRequest`、AIP 记忆治理与总控投影的实际合同。`sample_count=0` 只能得 `insufficient`/`effect_completed=false`；不可编造销量、ROI 或可比较 cohort。
- 文件级第一切片：新增 `services/aos-api/aos_api/ecommerce_growth_effect_review_owner.py` 与 `services/aos-api/tests/extension_runtime/test_ecommerce_growth_effect_review_owner.py`；必要时最小扩展 `services/aos-api/aos_api/aip_effect_review_store.py` 以接收调用者已持有的受限事务，而不是让 Store 内部另开连接或提前 commit。原 `test_ecommerce_content_review_pending_pg.py` 继续同一原命令、同一第二段 Receipt，使用正式 AIP EffectReview 权威 API/表，不另造第二源权威或测试假评估。若需要新映射/回执迁移，先检唯一 head 与 ACL，并单列后续精确文件，禁止在此计划外直接 DDL。
- RED 顺序：无第二段 ack/Receipt、内容 Run 非终态、旧 dispatch/runtime、错租户/Artifact/Review Receipt、第二段 body/hash 漂移均无 EffectReview；现有不足证据评估的 `accepted` 与 `effect_completed` 两轴必须分开，首次写入后独立连接读回 subject/原回执/版本/hash，重复原 command 只回读同一版本。已提交结果未知只读对账，绝不自动再次创建修订。若现有 Store 不能在当前 Host/事务锁下安全组合，先修窄事务接口和测试，再接自然 Worker；不能先启进程后补锁。
- 只有正式不足证据 EffectReview 读回后，才在下一切片设计第三段 `memory_candidate` 为“待治理方法候选”：引用原 EffectReview 与原 exact 内容来源，不正式入库、不自动发布，不让 sample=0 被称作增长有效。总控显示复盘/未知效果/治理待办须有业务中文与来源可追。当前实例继续默认关闭，不触 Provider、微商城源、旧十二 Run 或 Wiki 发布。
- 每切片独立 RED→最小实现→专项/累计/隔离 PG→方案/代码一致性→verification→m1 提交→AOS/Prime 同步。纯后端切片浏览器不适用；总控页面切片必须浏览器验收。不得把 AIP Store 的单元 GREEN 当同一真实首链完成。

### P2g 第十五增量：第三段待治理方法候选的原子接收（2026-09-27，编码前）

- 复核 231-5 §4/7、231-6 AR2-7C 与 231-9 BG-04：第三段 `memory_candidate` 只能是原内容评审已接受、原 Run 已终态、第一/二段已 ack 且正式 EffectReview 为 `insufficient` 的方法候选。不得把 `sample_count=0` 写成增长有效，不自动批准、推广或发布 Wiki。当前生产仍默认关闭，不读商城源、不调用 Provider、不手工重放旧 Run。
- 现有 `AipMemoryStore.create_source_revision/submit_candidate` 各自开连接并提交，不能在反馈 claim/ack 已持有的 Host 事务中直接调用。文件级第一切片只改 `services/aos-api/aos_api/aip_memory_store.py` 以提供无内部 commit 的受限事务入口，并在 `services/aos-api/tests/extension_runtime/test_w_l20_memory.py`（若现有测试名不同，先只读核实）补原公共接口不回归及回滚测试。不得以跨连接“先写候选再 ack”制造未知提交边界；不得改审批/推广规则。
- 只读核实后现有归属测试实际为 `services/aos-api/tests/aip/test_aip_memory_store.py`；第一切片在该文件扩 RED，不新建近似的 `test_w_l20_memory.py`。
- 文件级第二切片拟新增 `services/aos-api/aos_api/ecommerce_growth_memory_candidate_target.py`、`services/aos-api/tests/extension_runtime/test_ecommerce_growth_memory_candidate_target.py`，并延伸原 `test_ecommerce_content_review_pending_pg.py` 的一次性完整迁移同库链；如正式候选与反馈 segment 之间缺少可证明的唯一映射，再新增单头 `a0v_107` 限制性回执/函数迁移，先检查实际 Alembic head/RLS/ACL。不得直接 INSERT 假候选或把反馈表冒充 AIP 目标权威。
- RED 需先证明：无原第三段 pristine claim、无正式 EffectReview、评估非 `insufficient`/`accepted=true`、第一/第二 Receipt 或原 Artifact/hash 漂移、旧安装/dispatch、非终态 Run、跨租户均不写 AIP source/candidate/第三段 ack。正向必须以原 Task/Run/Artifact 和正式 Review exact 来源创建唯一 `pending`、workspace、episodic 候选；source_revision 内容哈希绑定正式 EffectReview，payload exact 原 Artifact，marking 明示 `insufficient_evidence`。候选与第三段 ack 同事务提交，独立连接回读两个权威与 checkpoint=3；重复原 command 只读回，不新建候选/事件/attempt。
- 如果 AIP 公共表的当前 ACL/RLS 不容许非超级 Runtime 身份按上述原子路径写入，先记录 RED 与实际权限，最小收敛到受限 SECURITY DEFINER 函数；不可放开候选表直接写权限或绕开治理。未知提交只读对账且停止自动重试。专项、累计、浏览器不适用说明、方案/代码一致性复审、verification、m1 精确提交、AOS/Prime 同步后进入下一波自然启动与总控可读投影；不以隔离同库链宣布真实首链完成。

### P2g 第十六增量：反馈后半段默认关闭的自然消费者（2026-09-27，编码前）

- 231-5 的 `feedback_pending` 不能靠开发者逐段手工 `run_one`；第十五增量只证明隔离同库原子接收。先只读复核 `main.py` 第一段 worker 的启动/停止门、`CurrentImprovementConsumer.serve` 和第二/三段当前消费者：第二段已有有界 serve，正式 EffectReview 与第三段尚无 serve，三者都尚未进入 `main.py`。当前实例仍保持所有新 flag 默认 false，不做真实启动、来源读取、Provider 或旧 Run 重放。
- 文件级范围：`services/aos-api/aos_api/ecommerce_growth_effect_review_owner.py`、`ecommerce_growth_memory_candidate_target.py` 各补有界 `serve(stop,host_ready,interval_seconds)`，每轮固定正 scope `org-org/dev-project`、Host task 非 ACTIVE 即失败；`services/aos-api/aos_api/main.py` 增三个独立默认关闭 flag/启动状态/任务，复用共同的窄启动门核 Runtime Host 当前 ACTIVE、独立 runtime DSN 与合法 flag，异常及未知结果 `FAILED_CLOSED`，无隐式 Web 身份降级。第一段 worker、固定九 operation、HTTP 路由与现有开关保持原状。
- 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_growth_feedback_downstream_startup.py`，扩 `test_ecommerce_growth_effect_review_owner.py`、`test_ecommerce_growth_memory_candidate_target.py` 和必要的现有第二段专项。RED 先证明三个 flag 缺省均不建 task、invalid flag/无 ACTIVE Host/缺 runtime 身份不得启动、每个启用后可按 Host stop 停止，Host 失效或 owner `Unknown` 必须让该 task `FAILED_CLOSED`，且不重发、不自动创建第二 attempt。对当前实例实际状态只读核 flag/Host/DB migration；不通过修改环境配置开启。
- 专项/累计/compile/Alembic head、方案/代码复审和 verification 后精确提交，再更新 D-waves/AOS/Prime。纯后端 worker 门浏览器不适用；下一波总控中文回流才做浏览器验收。若运行中 Host/Runtime 身份不可用，当前实例保持 off，隔离测试可继续，不以测试 task 模拟真实自然周期。

### P2g 第十七增量：总控三段反馈只读权威视图（2026-09-27，编码前）

- 231-5 `feedback_pending→completed`、231-6 AR2-7C 的业务/审计投影分离及产品总控“今日复盘／AI 改进建议／经验沉淀 Wiki”要求：现有 `TaskCockpitPage` 只读取通用 TaskRun 与 AIP memory/improvement 列表，不能看到新第二段 `ImprovementPendingReceipt` 与原反馈 command 的完整三段，也容易把 pending 候选标题显示成技术 ID。先做只读、同一原命令的后端投影，再单独前端波做真实页面接线和浏览器验收；不把 `pending` 显示为已入库，不把 formal `insufficient` 显示为效果改善。
- 文件级后端切片拟新增 `services/aos-api/aos_api/ecommerce_workshop_feedback_read_model.py` 与 `..._contracts.py`、`services/aos-api/tests/extension_runtime/test_ecommerce_workshop_feedback_read_model.py`；`services/aos-api/aos_api/routers/ecommerce_workshop.py` 仅增加受现有 Task Cockpit 安装/权限门保护的 GET，现有 Core DTO、写命令和路由不变。必要时延伸原 `test_ecommerce_content_review_pending_pg.py` 同库链，对原 command 终态只读组合，不手工填假投影。返回每段中文业务标题/摘要/准确状态、正式 EffectReview 成熟度、候选治理状态和显式展开的 exact audit refs；默认业务层不漏 UUID/hash/技术波次，缺一段只能 pending/unknown，不能按 Task succeeded 补齐。
- RED：无当前租户授权或跨租户、原 Run 非终态、错误/漂移 Receipt、评估被篡改、候选非同源或部分 checkpoint，均不能伪造三段已完成；历史数据可按原安装代次回读但不得冒充当前可执行授权。首次 `limit<=20`、稳定 cutoff 与排序、无全表或商城源扫描。所有 SQL 使用同一 scoped read-only snapshot；调用现有 target/AIP 权威的严格读回函数，不复制哈希/审批规则。后端专项、同库、累计、类型/迁移检查、verification、m1 提交、AOS/Prime 同步后进入前端切片，后端纯 GET 本切片浏览器不适用。
- 前端后续切片范围预告：`apps/web/src/api/ecommerceWorkshop/{client,contracts,parser}.ts`、`apps/web/src/components/workshop/TaskCockpitPage.tsx` 与相应测试；只读追加三段来源卡，加载失败保持失败关闭，pending/正式入库严格分离。前端切片必须启动可用页面，经浏览器核三状态、折叠审计、租户和空/失败态；若当前 8080 不在线，先核真实进程与安全启动边界，不得用静态 fixture 冒充生产浏览器验收。

### P2g 第十八增量：总控三段反馈页面接线（2026-09-27，编码前）

- 上位复习：231-5 的 `feedback_pending→completed`、231-6 AR2-7C 的业务/审计分层、产品总控的“今日复盘／AI 改进建议／经验沉淀 Wiki”以及第十七增量 `m1@e7e65f0f` 的只读 API。页面当前三个通用 AIP 面板不等于原反馈命令三段，须另加一块明确标注“内容评审后的经营反馈”，不替换/重解释旧通用面板；`insufficient` 不能显示成改善，`pending` 候选不能显示已入库。
- 文件级清单：`apps/web/src/api/ecommerceWorkshop/contracts.ts` 加严格反馈 DTO，`parser.ts` 加 schema/租户/三段顺序/状态/Receipt/executionAuthorized=false 校验，`client.ts` 加只读 GET 且 limit 1–20；导出经 `index.ts`。`apps/web/src/components/workshop/TaskCockpitPage.tsx` 独立加载状态与只读三段业务卡，审计 exact refs 默认折叠，空态/租户切换/失败保持失败关闭；不加命令按钮、不改变既有任务、复盘、Wiki 页面语义。测试范围是 `apps/web/src/api/ecommerceWorkshop/{parser,client}.test.ts`、`apps/web/src/components/workshop/TaskCockpitPage.test.tsx`，必要时仅改邻近样式。
- 先 RED：后端三段状态与中文标题/摘要显示，effect “证据不足”、candidate “待治理” 与 promoted “已入库”分开；截断/错顺序/伪造执行授权/坏 exact ref/跨租户响应被拒；空态、403/503/网络失败不会用旧成功卡或 fixture 伪装；审计折叠不泄露在默认业务层。再最小实现、专项与累计前端回归、构建，检查对旧面板和数据的影响。
- 浏览器验收先核当前 8080、API 实例与可用签名安装；可用时在真实浏览器检查空/失败及有权三段。若没有真实当前业务反馈，只允许标记页面结构/空态验收，绝不以静态 fixture 称自然业务成功；无法安全启动时明确保留浏览器门待办，不阻塞随后独立后端主线。最后落 verification、m1 提交、AOS/Prime 同步，再进入签名安装/来源/审批/Host 的自然生产门。

### P2g 第十九增量：真实首链启用前只读权威清点（2026-09-27，执行前）

- 上位复习 231-5/231-6 AR2-7C、产品首链与第十六至十八增量证据：默认关闭的 worker 和隔离同库 GREEN 均不是当前实例自然运行许可。浏览器门因 8080 无 API 停在目录读取失败。此波只读清点，不为测试绿强启当前实例，不读取商城源或旧十二 Run 的 payload。
- 文件级范围仅本 plan、对应 `w5cb4-p2g-current-authority-preflight-verification-20260927.md`、D-waves/上下文/记忆；如发现明确的纯代码缺口，另立编码波方案，不在此波临时改生产文件。检查 m1 与 docs 精确 HEAD、工作树已有文件归属、8080/18181/5173 监听、当前进程/环境开关（只报状态不输出秘密）、单迁移头、当前签名 Bundle/安装/权限/来源/预算/真人审批与 Runtime Host 的可查询入口。
- 对第二段 `ImprovementPendingReceipt` 增加提交后独立读回的**测试/代码需求评估**；当前现成单元/同库证据若不足，则列为下一编码波优先项。对真实自然链只报告 `VERIFIED`/`NOT_VERIFIED`/`BLOCKED` 和具体证据，不把准备条件写成已满足。若生产 API 离线且恢复需要不明授权/安全边界，本波不启动；仍可继续独立代码安全门。
- 验证文件落盘并 m1 精确提交，再同步 AOS/Prime。随后自动进入可独立推进的最小代码波（优先第二段独立读回或真实启用前门）；真正启用须当前签名安装、当前 Host、来源/审批/预算与未知提交安全边界全部读回。

### P2g 第二十增量：第二段反馈提交后独立读回（2026-09-27，编码前）

- 复习 231-6 AR2-7C 的 receipt-first/未知提交冻结、原 `ImprovementFeedbackWorker.run_one`、第三段/EffectReview 已有的 postcommit Unknown 处理以及 P2g19 只读验证。第二段当前只在同事务内读回并 commit 后返回成功；必须补独立连接读原 command/第二目标/segment/checkpoint，不能靠下一段或测试 SQL 代替。默认 worker 继续 off。
- 文件级最小范围：`services/aos-api/aos_api/ecommerce_growth_improvement_target.py` 增独立 `connect_read_only` 依赖和 `ImprovementFeedbackUnknown`；在原事务 commit 后、返回成功前，用新连接核同一租户/command/targetId/Receipt、second ack/attempt=1/checkpoint=2、第一段仍 ack、原 ACCEPT 来源不漂移。提交或提交后读回未知/异常一律抛 `Unknown`，不自动重投，消费者不得吞成普通可跳过阻断；自然 serve 因 Unknown 停止并让 app 任务 FAILED_CLOSED。原前置拒绝继续保留 `Conflict`。
- RED 测试扩 `services/aos-api/tests/extension_runtime/test_ecommerce_growth_improvement_target.py` 的可注入连接，验证提交后第二次独立连接、丢失/漂移/读取异常、未知提交不得成功返回且没有第二次 claim；原 `test_ecommerce_content_review_pending_pg.py` 复用同一原命令及非超级运行身份做正向独立读回与重复稳定。若现有 clone connector 参数不兼容，先只改测试显式传同一 read-only connector，不改生产默认。
- 专项、原同库与相关累计、编译/迁移头、方案代码复审；纯后端浏览器不适用。verification 文件落盘、m1 精确提交、AOS/Prime 更新。下一波继续当前签名安装/运行入口的安全恢复或其他独立首链缺口，不触商城源、旧十二 Run、230 L0。

### P2g 第二十一增量：Mac/Colima 当前实例入口只读定位（2026-09-27，执行前）

- 先核 P2g19 的“8080 离线/开发默认空库”与当前 m1/docs HEAD，不将失效或空的开发默认库当生产权威。用户已说明执行部署仅当前 Mac/Colima；只在此范围用进程/容器/端口/配置键名和已有运行日志索引定位可验证入口，不读商城源、secret 值或旧十二 Run payload。
- 文件级范围仅本 plan 与 `w5cb4-p2g-local-runtime-entry-verification-20260927.md`，以及 D-waves/AOS/Prime 上下文；不改代码、服务配置或重启生产。只读检查 Colima/Docker 是否运行、容器清单、127.0.0.1:8080/18181 等监听、可识别 AOS API/DB 进程、受控启动脚本及当前 DB 连接配置是否有精确可用来源。每个候选入口先证归属和目标库再考虑下一波启动/读回。
- 若没有可信当前入口，明确 `NOT_VERIFIED` 并列出恢复所需的本地只读证据/命令，不创建替代实例或复制旧快照。若找到，仍只读核签名安装/Host/开关，后续启用需另波方案与安全门。验证落盘、m1 提交、文档/记忆同步后进入下一独立可做波；此波浏览器不适用。
