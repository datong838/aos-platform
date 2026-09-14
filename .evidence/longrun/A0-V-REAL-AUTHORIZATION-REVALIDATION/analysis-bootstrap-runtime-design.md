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
