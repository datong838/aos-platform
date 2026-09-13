# 事件首链的正式分析编译桥接技术方案

基线7be853c4。目标是经营参谋从原始事件自然创建具有真实执行血缘的分析任务。当前新Run→CompilationReceipt之间缺调用，真实PG复现BusinessInvestigationCompileConflict: exact Run must resolve one compilation Receipt。旧Host单测替换_start_lineage，不能作为完成证据。

## 权威关系

1. Case/Run中的领域InvestigationProfileRevision（aos.ecommerce.investigation-profile/v1）是L1分析意图，不能强转成AIP编译Profile（aos.aip.business-investigation-profile/v1）。二者必须以显式exact绑定关联。
2. 安装包提供受版本控制的分析编译模板：领域profile、三阶段portrait/diagnosis/solution-design及所需能力意图。租户配置提供真实已安装/已冻结Logic、StageTemplate、SkillBindingSet、ResponsibilityPlan及能力角色引用；当前读取逐一校验租户、版本、内容hash、安装代次和权限。
3. ProductionContext与TaskBrief绑定具体task/run，不能复用其他任务的context。由确定性桥接创建本次Task/TaskBrief/ProductionContext，并按现有冻结/就绪协议验证；不直接标READY或伪造冻结。
4. 运行编译Profile由模板与本次当前配置组合，保存可追溯到L1意图及原Case/Run的桥接证据；不得让任意同analysisType的Profile替代。
5. 通过BusinessInvestigationCompileSaga→BusinessInvestigationProfileCompiler→AipProductionContractStore.compile_stage_template产生真实Plan和CompilationReceipt，再由现有RuntimeBinder绑定TaskRun。所有数据库写入共用外层事务和确定性幂等键。
6. receipt-first：已有一致编译回执精确回读；有记录但不一致拒绝，不能新建另一个Plan掩盖。尚未编译时才执行桥接；不允许get_for_run缺失就构造假Receipt。

## 串行实现清单

- CF1：桥接exact输入合同及来源关联验证。文件拟定services/aos-api/aos_api/ecommerce_analysis_compilation_binding.py、对应tests；明确L1/L2字段和Run/Task/context一致性。
- CF2：当前安装配置与真实冻结依赖读取器；缺失依赖形成明确不可执行结果，产品配置入口可补齐，不靠开发者手工插表。编码前复核现有配置和AIP实体API，登记具体目录。
- CF3：确定性Task/Brief/Context准备及CompileSaga事务组合，创建或读取真正的CompilationReceipt；不绕过freeze/readiness/role/capability门。
- CF4：接入AnalysisAdvanceHostService._start_lineage，保留旧Receipt回读；真实PG验证Run/Task/Plan/Compilation/TaskRun/RuntimeReceipt原子与同键幂等，撤销/漂移全回滚。
- CF5：完整worker真实集成与失败恢复，消除已知严格xfail；新候选签名/独立评审/安装迁移验证，旧候选不改。
- CF6：栖月汇黄埔0期销售武器包真实首链贯通，然后八场景和连续观察。

## 退出条件与边界

CF4须让本次真实PG复现用例从已知失败转为成功，并读取实际表血缘，不能仅mock编译器。CF5仍需要新签名候选和独立真实发布账号；尚未部署。当前主库未039–043迁移，不push，230 L0挂起。任何缺失角色或配置不能用测试替身/全true resolver/假批准补齐。真实业务目标仍未完成。

## CF2-2 合同复核修正

已有 ecommerce_business_investigation_aip_authority 定义职责模板 ecommerce.business-investigation.readonly，槽位运行能力为 strategy.plan/material.collect/content.review；L1 profile 的 frame-problem 等是分析意图，两者不能按同一命名空间做集合包含。CF2-1 的该比较会误拒绝真实职责，必须修正。

修改 services/aos-api/aos_api/ecommerce_analysis_compilation_roles.py 与 services/aos-api/tests/test_ecommerce_analysis_compilation_roles.py：按领域 responsibilityTemplateCode 约束 compiler_profile 与职责 templateRef；复用现有模板解析器验证 exact templateRef，继续要求配置内唯一、hash 一致、frozen/ready/complete，并在同一 Owner 回调后重读。不得用角色读取成功代替 Logic/Skill 对分析意图的覆盖，后者仍属 CF2 后续退出条件。

测试用现有 build_responsibility_plan_request 构建真实合同形状的职责输入，覆盖错误模板、错误 profile、状态不足、配置漂移。此波不执行 materializer，不创造角色/冻结，不改主库。

## CF2-3 当前 exact 阶段读取

在 services/aos-api/aos_api/ecommerce_analysis_compilation_roles.py 添加 run_with_stage，复用 run_current 的安装配置职责与SourceOwner边界。调用者给定阶段exactRef，不枚举租户模板；读取该template当前head，要求ref/version/hash匹配、租户一致、frozen/ready、sourceBundleRef等于当前L1 profile，复用既有来源解析器。三阶段顺序与L1一致，阶段所需slot均由当前职责提供；重算模板正文hash，回调后重读拒绝漂移与deferred。对应 tests/test_ecommerce_analysis_compilation_stages.py。此API是依赖读取器，不是安装模板选择器或执行许可。受安装约束的模板选择及Logic/Skill仍未完成。

## CF2-4 实库依赖与编译兼容性

2026-09-14 07:20 CST只读主恢复库：D01/D02/D03发布技能均r2，对应Logic r1；active绑定TTL均已过期。stage-template-ea53ff98fc1644c392ff@2 frozen使用profile ecommerce.business-investigation；职责方案responsibility-plan-63c82d2a75614e1b95f1@2 frozen使用ecommerce.business-investigation.readonly。正式compile_stage_template要求模板、职责、context、请求profile相同。CF2-3应补拒绝旧不一致模板，修改run_with_stage按compiler_profile检验，测试补legacy-profile拒绝。保留旧冻结记录，后续通过产品准备API创建受治理的新模板，不做原记录改写。

此外SkillBindingSetRevision目前只有编译合同引用，没有实体Store/生产resolver；37技能拆分映射明确planned_not_published，不能作为覆盖证明。CF2后续必须补版本化L1-L2技能映射与绑定集合权威，再进入CF3；不能伪造exact resolver成功。

## CF2-5 派生技能集合合同

新增 services/aos-api/aos_api/ecommerce_analysis_skill_set.py、tests/test_ecommerce_analysis_skill_set.py。SkillBindingSetRevision采用当前SkillBinding权威行的内容寻址派生快照，含tenant、installation/generation/epoch、exact职责方案与稳定按binding_id排序的完整绑定。集合ref用内容hash寻址、revision固定1，不另建可写权限表。合法性检查租户一致、唯一binding/skill、SkillTemplate类型、正文hash；validate_current对当前重读行和当前安装/职责exact比较，校验active/available、无阻断原因、已评估、依赖快照存在及TTL未过期。此合同不证明Logic发布或能力可执行；后续读取器须在原Owner回调内读真实绑定与发布，并保存集合正文到编译桥证据。无DDL/主库写。
