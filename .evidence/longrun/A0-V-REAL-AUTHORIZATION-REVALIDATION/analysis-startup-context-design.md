# 经营分析启动 Context 与分阶段经营证据

基线545cf043。此方案补足CF3；不是运行许可或业务验收结论。

## 目标及事实

经营分析需要先建立可恢复任务，随后完成画像取证、诊断、方案和评审。当前DataRequirementHostService.revalidate必须读取已有CompilationReceipt并经RuntimeBinder取得暂停Checkpoint，因此不能通过该服务反向准备首次编译依赖。现行Compilation又必须有冻结ProductionContext。原v1 Brief引用环已由v2意图简报解决；这里解决的是证据用途与执行顺序。

真实画像服务portrait_prompt并不是旧Logic dry-run：它要求当前method、指标定义、查询结果、完整披露EvidenceBundle及frozen/ready Eval，逐指标验证唯一来源，并保留生成产物。启动Context不能替代这些检查。

## 采用的顺序

1. 当前安装蓝图显式声明startupContextPolicy：用途仅为analysis-start；要求原事件与本次Case/Run的关联证明，业务事实尚未完成。
2. 事件分析Host保持现有领取锁、原来源SourceOwner、原journal证明、当前installation/generation/epoch、控制/配置和Case重验。蓝图IPC在事务外，写前后仍复验；不能以持有一个Python快照等同当前授权。
3. 在上述同一事务中创建本次Run、Task、frozen v2 Brief。依据原始事件/Occurrence及Case/Run exact引用生成启动Evidence。来源时间、身份和hash只能来自实际读取，禁止从测试fixture或调用者自由文本推断。
4. 启动Evidence明确purpose=analysis-start、factIds仅为固定启动关联事实；保留领域requiredFactProfiles作为尚待取证清单，不得发布为画像指标证据。证据run_id为NULL，因为AIP TaskRun尚未创建；payload保留业务Run exactRef，绝不虚构AIP运行记录。
5. 通过现有build_evidence_bundle给本次Brief构建启动包，requiredFactIds由受当前安装约束的蓝图声明且Host仅支持固定用途集合。complete仅指已声明的启动关联事实覆盖，不能作为任何经营结论、业务质量或经营阶段完成依据。
6. Context的Eval引用须由蓝图首阶段的实际已发布技能唯一解析其PublicationEvent/ReleaseGate/Suite，并通过当前有效状态、hash、TTL和依赖重验。该合同若是isolated_skill_contract，只证明启动技能契约；记录用途，不能当作经营分析的质量评估。缺失/失效形成可恢复不可执行结果，不挑任意旧Eval。
7. 冻结本任务Context，派生L2 Profile，经真实CompileSaga建立Plan/CompilationReceipt，并创建/绑定真实AIP TaskRun。各步以原事件幂等键组合，统一外层事务，失败不留下孤儿或假运行回执。
8. 后续业务阶段继续用真实指标查询、来源披露、method/Eval及业务产物协议；缺数进入既有暂停/数据请求/恢复流。评审、交接与EffectReview/Wiki不得接受启动包替代其业务资料。

## 串行开发清单

- SC1：包内蓝图追加显式启动上下文政策及Host严格验证。文件bundles/solutions/ecommerce-growth/backend/ecommerce_growth/analysis_compilation_blueprint.py、services/aos-api/aos_api/ecommerce_product_event_analysis_port.py及对应tests。需包路径子Lease；不改旧签名候选。政策字段版本化，非法目的/事实集合拒绝。
- SC2：Host启动证据合同与当前事件派生/存储，拟services/aos-api/aos_api/ecommerce_analysis_startup_evidence.py、tests/extension_runtime/test_analysis_startup_evidence_pg.py。事务内核对原事件来源与Case/Run，幂等重读、撤销/漂移拒绝；scope/actual evidence hash/无AIP run伪造。
- SC3：首阶段当前Eval选择与本任务Context准备，拟ecommerce_analysis_context_preparation.py及PG测试。验证Brief完整意图、Bundle完整请求hash及当前items、评估发布/门/TTL、职责profile，不以frozen标签代替当前有效性。
- SC4：组合CF3的Task/Brief/Context/L2/Saga及真实TaskRun，接回_start_lineage和事件Host。继续保留真实START严格xfail，只有实际表血缘通过才能移除。

## 验证与业务边界

SC1–SC3单项通过不计首链完成。必须SC4真实PG全链原子、同键重放、当前撤销和崩溃恢复通过，再新候选评审安装及主库迁移。之后以栖月汇真实数据自然事件执行黄埔0期销售武器包首链，审阅可读业务产物，再扩展八工作台和连续观察。

启动证据与经营证据的用途约束必须在代码里执行，不仅留在本文。若下游以“任意complete Bundle”放行经营结果，登记并修复该消费点；不能在入口换名称就宣称问题解决。不新增外发动作，不push，230 L0仍挂起。

## SC1 exact政策格式

蓝图schema升为aos.ecommerce.analysis-compilation-blueprint/v2，新增startupContextPolicy（必填）：schemaVersion=aos.ecommerce.analysis-startup-context-policy/v1；purpose=analysis-start；requiredFactIds=[analysis.original-event-case-run-lineage]；businessFactCoverage=not-evaluated；pendingFactProfilesSource=domain-profile.requiredFactProfiles；evalStageId等于首阶段portrait；evalPurpose=skill-publication-contract。Host按支持的完整规范对象比较，不接受附加授权字段、事实替换、阶段替换、业务完成声明或旧v1遗漏政策。原stageTemplateRequest和阶段技能选择不变，蓝图完整hash自然变化；旧候选保持不可变，不能被新Host当作支持新启动协议。新增回归对上述变体重新计算hash后仍须拒绝，避免仅靠hash捕捉篡改。
