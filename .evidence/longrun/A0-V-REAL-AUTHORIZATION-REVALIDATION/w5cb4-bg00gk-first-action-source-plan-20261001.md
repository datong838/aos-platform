# BG00GK 首次内容动作来源与下一波文件计划

基线AOS-001051/m1 c7b670af。复习231-5 §1/4/5/6，225/P2g30b RETURN边界、443/444及当前TaskRun/AgentRun/Budget Owner与Action/ProductionContract Store。本波只读源码审计和方案，不改业务代码、不造正向fixture。

## 已证实的接入错误

自然ContentTaskRunOwner在同事务创建Plan/批准/Run/start，risk仅reviewReceiptRef、responsibilityPlanRef、externalPublicationAllowed、providerInvocationAuthorized，没有productionContract.productionContextRef。通用create_impact_preview的_require_task_plan必须有该exact Context且与Plan固定值一致。当前自然Plan不具备它；不能用W2-D直接seed多个冻结合同的fixture冒充生产链，不能改已经executing的Plan或删Context门。

ActionStore已支持internal_binding→不可变Draft→checker→ApprovalEvent；预算要求非空action_binding_hash，不要求一定存在通用ImpactPreview。首次内容可沿既有内部动作绑定机制承载当前原始来源，但必须同事务重验与可见预览，不能生成任意hash。RETURN继续独立六字段门，禁止将初生生产者用于返工。

## BG00GL 单一纵向实施清单（先RED，不开平行主线）

### 1. 复用来源，避免复制两个执行状态机

文件services/aos-api/aos_api/ecommerce_content_budget_command_owner.py：将_build_command内业务审批之前的既有来源核验提取为一个内部受控准备函数/类型。它负责原budget intent状态、a0v104 current、Review origin、安装/dispatch、ContentAgentRunOwner._build_request、当前AgentRun/assignment、ModelResolver、Quota/BudgetPolicy/Price/Capacity。返回精确来源截面，不产生claim、hold、Provider动作。原_build_command复用同函数并继续_approved_action→GJ_approved_bound→Host revalidate，旧输出必须保持一致。不得复制这些规则到Action生产者。

### 2. 首生Action精确绑定与可见来源

候选新文件services/aos-api/aos_api/ecommerce_content_first_action_binding.py；现有aip_action_store.py最小接线。显式首生标记/请求合同与RETURN字段分离：reviewKey、预算上限、服务端预览返回的精确source envelope；只允许ecommerce_growth_content_generate。源引用不能由用户任意传入即信任：maker提交和checker决定都在原Action事务内重新准备并比较完整来源。

来源至少包含tenant、reviewKey、原Review Receipt/hash、Task/原Plan/原Run、Brief/有来源Artifact、当前安装generation/epoch/dispatch/group/runtime版本、AgentRun/assignment/Skill/Capability、resolved Model/Provider/model ID/Price/Budget/Quota、Capacity reservation、批准金额与有效期。仅采用既有Owner核验可返回的字段；若某项没有合法来源，明确拒绝该实例，不能硬填hash或加额外特权。

binding domain固定版本且canonical，覆盖请求action metadata/tenant/task/run/完整来源/金额/期限；来源预览必须在动作详情可见，并以现有不可变ActionDraft/Proposal持久化。检验ActionType当前metadata，至少R2、makerChecker、executionAllowed、非draftOnly；当前成员/角色与maker/checker分离、到期、撤销、scope都沿既有合法读者复验。客户端risk hint或roles不得成为权威。

_internal_request_binding只对显式首生合同接新门，旧普通草稿及RETURN行为保留；_internal_proposal_guard对相同合同重验来源及binding、Draft canonical/Proposal匹配。重放必须先核当前来源，再返回原Receipt；失败零提案/批准。预算_approval_authority不放宽。

### 3. 产品入口与读写分工

候选services/aos-api/aos_api/routers/aip_actions.py及aip_action_service.py：优先复用现有Proposal/decision接口和服务端Principal，不另建审批体系。必要的首生来源预览只展示候选，不授权、不claim；写入前同事务重验。预览不得调用会修改cost fence的require_cost_risk；真正maker/checker写事务才核GJ当前额度门。冻结请求前先确认既有Action UI是否完整展示来源/金额/期限；若缺，列具体前端文件先方案后编码与browser验收，不让用户审批技术空壳。

### 4. 证明要求

- 原数字/风险预算Owner输出不回归，claim/unknown保持一次性。
- 标准完整迁移隔离PG，合法Store/来源生产流程→首生Proposal→独立checker→GE预算价格→held，回读单一不可变Draft/Approval/Receipt；无直接INSERT审批、无固定binding hash、不关guard。
- 缺任一来源/多义review/跨scope/task/run/安装换代/容量过期/模型价格换版/批准撤销/金额漂移/旧SERIALIZABLE快照拒绝，maker自批、旧RETURN、unknown重发均拒。
- 如果完整来源生产尚缺，记录具体缺的producer并直接施工该依赖；只能声明已验证子链，不将mock/替身正向冒首链。

测试候选tests/aip/test_content_first_action_budget_pg.py、tests/aip/test_content_first_action_binding_pg.py、tests/extension_runtime/test_ecommerce_content_budget_command_owner.py及既有ActionService/RETURN回归；最终文件范围按实际读回后登记Lease。

## 本波边界

源码审计发现足以改变下一动作，无业务代码变化，RED/累计/browser不适用；不重复跑与本波无关的80项。真实库未连接、Host/worker/Provider关闭、无源码读取商城/旧12Run/手工run_definition/230L0。当前自然首链未完成；正式恢复仍独立备份恢复/克隆全链/零执行窗口。后续实现逐步验证，不能用本计划当交付事实。
