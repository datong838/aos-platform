# SC4-3c 分析运行初始化：授权和执行边界

基线f7327f8d。本设计接原SC4清单，不另开业务目标。实际经营链仍是数据自然触发→有来源分析→exact方案评审→内容/能力→人工续跑→复盘/Wiki。本文仅解决既有CompileReceipt到可恢复TaskRun的初始化。

## 已核实的现有边界

- 事件enable有当前独立Action审批，并复验原策略、Case、安装、来源和领取；它不是本次Task的ActionProposal。
- 原AipProductionStartService检查本Task Plan/Context/Preview/approved Proposal/Logic；不能直接调用底层create_run来省略这些检查。
- 原通用R1默认draftOnly。不能通过给动作名称加read/query来把内部写操作误分类R0；新增初始化动作必须有明确内部风险规则，且同时完成专用守卫后才可启用。
- TaskRun初始化只产生暂停前的承接位置；首步not-started检查点已实现，不完成portrait、不执行模型或外部动作。

## 固定初始化合同

新增AnalysisBootstrapIntent：固定operation=ecommerce_analysis_bootstrap，mode=paused-before-first-step，businessExecutionAuthorized=false，externalEffectAuthorized=false；绑定tenant、installation/generation/epoch、原Occurrence、Case、Run、CompilationReceipt、Plan、Context及完整contentHash。Contract验证只证明一致性，不证明当前授权。不得接受调用者设置runImmediately、skipApproval、overrideBudget等字段。

启动前必须从原事件Owner当前事务派生此合同，核对claim/原来源、当前enable独立审批、编译回执与当前Task Plan；读取职责/技能/Logic和Context，拒绝跨租户、任意Plan、失效控制和过期依赖。使用当前真实执行身份，不借用原审批人的名字新增审批记录。

## 预览与审批

生成本Task的启动ImpactPreview，只评估初始化事务：对象为exact Case/Run/Task，渠道为内部AIP运行控制，provider调用和外部动作数为零，风险与可逆性引用固定初始化合同和实际编译回执，明确后续经营能力仍须独立权限/预算/审批。该零值只适用于未执行步骤的初始化，不能作为后续模型成本或经营预算承诺。

专用内部动作拟采用R1明确内部执行策略（非通用R1 draftOnly，也非假冒只读R0）。必须同步实现ActionStore和生产StartGate的专用guard：只准上述固定合同、真实当前源控制、匹配Task/Plan/Context/Preview；不能拿该动作审批启动任意Plan。实际审批身份必须在当前租户具备对应审批资格；配置中的独立事件enable审批仍复验。本次初始化审批与原审批分别留痕，不能伪造继承为同一Proposal。此规则尚未实现或无合格当前身份时保持不可执行。

## 原子执行

同一Host事务内原StartGate批准本Plan并创建TaskRun，随即通过原start_run及显式initial checkpoint暂停。提交前必须再次确认TaskRun=paused、无StepRun/Artifact/Usage、checkpoint not-started、所有exact及父控制仍有效。外界不应观察到本初始化事务中的queued/running中间态。任意失败全部回滚。完整START成功后依原Host Receipt重放，不重新造Task或换幂等键。

后续DataRequirement/画像工作才能恢复，继续使用现有真实指标、证据披露、预算与能力门禁。初始化Action不能被当成经营建议或外部行动审批。

## 串行文件与退出条件

1. SC4-3c1：services/aos-api/aos_api/ecommerce_analysis_bootstrap_contract.py及tests/extension_runtime/test_analysis_bootstrap_contract.py；严格合同与跨引用拒绝，仅合同不启用新风险规则。
2. SC4-3c2：本任务启动Preview准备服务和PG测试；原Store创建/冻结与当前依赖，拒绝失效、错接、下游回滚。
3. SC4-3c3：专用Action注册/风险/当前守卫及StartGate整合。拟aip_action_policy.py、aip_action_store.py、aip_production_start_service.py和ecommerce_analysis_bootstrap_authority.py。涉及包资产先开子Lease，新候选独立评审，不改旧签名内容。
4. SC4-3c4：实际TaskRun/initial checkpoint/binder全事务PG；直接通用API绕过、换Plan、父审批撤销、重复、跨租户、故障恢复均拒绝。
5. SC4-4：把blueprint IPC、编译和上述初始化接回ProductEventAnalysisService及sealed AnalysisAdvanceHostService；完整PG START原严格xfail真正通过后移除。之后新候选、主安装迁移/恢复及栖月汇真实首链/八场景/观察。

验收以当前实证为准，不按合同数量、测试数或页面数计完成。m1单写者，不push，230 L0挂起。

### SC4-3c2 预览准备细化

新增services/aos-api/aos_api/ecommerce_analysis_startup_preview.py及tests/extension_runtime/test_analysis_startup_preview_pg.py。构造必须为精确AnalysisCompilationPreparation；在其回调内再次进入原analysis._phase，使用当下request.occurrenceRef和source.controlReceipt生成BootstrapIntent。将完整意图保存为独立analysis-bootstrap-intent Evidence（run_id=NULL，实际业务Run subject，稳定身份和完整hash，撤销/内容不符拒绝），作为Impact各分区的可回读来源，不复用启动关联Evidence类型。

Preview精确绑定本Task/Plan/Context/Brief/Bundle/Eval/职责/Stage，绑定当前选中SkillBinding、归属AgentInstance及CapabilityBinding的真实版本；不存在/失效拒绝。初始化范围的object/channel/cost/budget/risk/reversibility/approvalChain/rateCapacityKill分区引用实际意图Evidence，明确未授权任何经营步骤；不把初始化零provider调用当商业成本。expiresAt固定为业务Run.createdAt+10分钟与当下来源审批/SkillBinding截止的最小值，过期拒绝，不以now滑动延长旧意图。

通过原create_impact_preview/freeze；同事务回读正文hash/生命周期/动态依赖；回调后核对意图Evidence、当前来源和Preview不变，错误回滚编译/上下文/预览。当前Source/selection/能力仍有测试fixture，测试改为真正存储的选中Binding行，让Preview不接受虚构ID。此波不创建或批准Action，不启动TaskRun。专用当前授权守卫仍为后续c3。

预览版本复核补充：同一AgentInstance在职责槽位必须只有一个配置版本，且与实际当前版本相等；禁止读取新版本并悄悄替代Plan已经绑定的旧版本。增加当前Agent版本漂移的隔离库拒绝验证。

### SC4-3c3 通用入口与专用入口隔离

先实现并验证通用生产启动入口对初始化动作/初始化预览的拒绝（c3a），再实现当前来源授权及专用原子暂停入口（c3b）。检查点完成前不得启用风险例外。通用入口须同时识别 action_type_id、Action快照id、Preview impact分区 details.purpose=analysis-bootstrap-only，避免换动作名复用初始化预览获得queued运行。修改 aip_production_start_service.py 与 tests/aip/test_w2d_start_gate.py；既有正常生产启动保留。

已复核原decide无条件禁止maker自批，初始化不得绕过。合格当前独立身份和实际审批记录仍为必要条件，后续专用入口必须验证而非虚构；独立源事件审批不能冒充本Task的审批。此波不注册Action、不启用R1例外、不授予任何当前身份权限。

### SC4-3c3b 当前审批身份子项

先补齐services/aos-api/aos_api/ecommerce_analysis_bootstrap_authority.py的当前身份读取器及tests/extension_runtime/test_analysis_bootstrap_authority_pg.py：只接受精确HostTransaction/TenantScope，核验事务租户、当前注册Action快照、maker与checker的当前唯一membership及全部marking。checker必须不同于maker并具有原ACTION_APPROVAL_ROLES资格，maker路径只允许原maker身份。不接受调用者提供roles，不写入或授予角色；远端OpenFGA缺当前适配器时拒绝。该读取器仅给后续ActionStore提供实时资格，不证明源事件/Task/Plan授权，也不启用执行。独立校验Action快照和事务scope避免使用他租户或陈旧角色投影。

### SC4-3c3c 当前初始化对象绑定

在ecommerce_analysis_bootstrap_authority.py增加AnalysisBootstrapCurrentBinding，构造仅接受精确ProductEventAnalysisService。run_current在原analysis._phase内复验claim/来源审批/安装；从存储读取实际Case、Run、CompilationReceipt、Task/Plan、冻结Preview与初始化Evidence。拒绝换Occurrence/控制回执、安装代次漂移、Receipt不等、非当前草稿Plan、已存在TaskRun、Preview不对应Context/Plan/职责/模板、Evidence被撤销或内容/来源不一致。同步回调前后重复读取并比较；本项仅用于尚未启动时的动作准备/审批，不允许回调启动或批准Plan。后续原子启动另以明确暂停后置条件承接，不能放宽本读取器来容忍任意Plan变更。新增test_analysis_bootstrap_binding_pg.py验证当前原事件和故障回滚。
