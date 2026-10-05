# 容量 Source 专用独立批准方案

基线 m1 10471542、AOS-001349。Task gt-provider-capacity-source-approval-20261005。继承原首次 ModelEval/GT 总方案，当前原 allocation 批准不包含 token 计量模式、账户映射和新 basis，因此须独立批准完整 Source candidate；不能从当前候选 head 推导已批准条款。

## 文件级清单

- services/aos-api/aos_api/aip_provider_capacity_source_action.py：Source 专用 guard 与 OIDC 提案/决定入口。
- services/aos-api/aos_api/aip_provider_capacity_action.py：最小提取已有 guard 的 action/metadata 类属性，使专用 Source guard 复用原 draft/policy/binding/maker-checker 重验；旧默认常量与行为不变。
- services/aos-api/aos_api/aip_action_store.py：独立 exact Source guard 参数、generic 入口拒绝和专用 checker replay 身份核对。
- services/aos-api/aos_api/aip_action_policy.py：新 R2/makerChecker/executionAllowed=false 固定 policy。
- services/aos-api/alembic/versions/a0v_148_provider_capacity_source_action.py：独立保留 metadata，原 owner-only 变更保护，不新增批准权威表。
- services/aos-api/tests/aip/test_provider_capacity_source_action_pg.py：原真实候选+原 allocation 批准后 RED/独立 Source 批准/实际漂移与相邻。
- 本证据目录：方案、终结日志与验证记录。m1 单写/no push，仅 disposable PG。

## 输入、事务与身份

专用 Action aip_review_provider_capacity_source，purpose capacity-source-review，完整 payload 只有 sourceCandidate。SourceCandidate strict reparse，账户/basis仅 CandidateRevision；候选 tenant、ID/rev/hash、固定false模式、SQL canonical hash、server maker、完整 envelope 和 nested DTO 重验。basis.physicalAccountRef 必须等于 Source.accountRef；原 request exact/hash/expiry必须当前，request maker 必须等于提案者，account/basis maker 也同主体。账户 Provider 集合须含原 request 的完全相同 exact Provider，且所有 Provider 当前 head、账户/basis Evidence 同 caller 重验。

原 allocationApprovalRef revision1 必须定位唯一原 aip_request_provider_capacity 批准事件；读取原 proposal 与 draft，使用原 guard 核 metadata/policy/binding/maker/checker/当前 Owner，事件decision approved、proposal/version/hash/binding/policy/slot/eligibility一致且期限未过，proposal status approved。引用 contentHash 定义为原 ActionApprovalEventSnapshot 全部 by_alias JSON 的原 canonical_hash，使用原 bundle 转换器同 conn 构造，不复制时间/actor序列化规则；此 event hash 仅精确绑定原不可变记录，不声称 issuer 签名来源。reject/revoke/current漂移一律拒绝。

Source.validFrom/Until 必须当前，范围不超原 request、basis、旧批准期限；提案 expiry 不超这些期限。模式与限额由 exact basis hash 完整绑定，不跨计量维度取小或从旧 request 数字推断 token mode。源类型 supplier_limit_claim 仍是未核 claim，批准仅为 Owner 审查条款；Source issuer 另证明来源适用性、供应商事实、全域账户归一和时效。

所有决定沿用原 Action store 行锁、幂等事件、min expiry、policy eligibility、独立 Owner checker、同 caller guard 重验；当前 metadata/member/provider head 使用原锁，不新增运行入口。禁止 self approve；错 checker replay 不返回别人的成功事件。generic AipActionStore 不装 exact guard 必须拒绝。执行服务因 executionAllowed=false 无 lease；预算/容量/Source发行行均不增加。

## 退出与未完成

### 督导复审后的明确约束

本波不授权替换原配置：account.physicalAccountId 必须等于旧 request.physicalAccountId，basis.maxConcurrency 必须不超过旧 request.requestedMaxConcurrency。更换账户、同Provider提升并发均拒绝；新模式token仍不得与旧未知模式数字取min。账户ID相同仅条款一致，不证明真实归属或归一。

原 Action 支持追加审批，本波 Source前置只接受唯一原批准事件且无其它决定事件：原event.proposal_version=1、当前approved proposal.version=2，proposal hash和绑定相同。这是专用Source准入收紧，不改变原Action一般多批准规则；二次批准、后续拒绝或其它历史版本不自动选最新事件，必须拒绝并通过新正式提案重新审查。测试覆盖正常v1事件/currentv2正向、追加第二批准和后续拒绝负向；不把事件版本等于当前版本作为有效判断。

先 original signed Provider/Evidence、真实本地 HTTPS OIDC maker/checker、actual account/basis candidate 和原allocationapproval形成 RED。最小实现后验证正向与selfapproval、错hash/candidate映射/旧批准、Provider head/Evidence撤回/Owner角色/metadata实际漂移、expiry、wrong-checker replay、same-key重复、canary零效果、原执行拒绝。专项及原候选/申请/审批和原通用Action相邻串行验证，复审方案一致性后Delivery。

本波不签发Source，不证明元数据读与revoke提交的epoch竞争闭合，不建立正式物理账户映射或共享occupation。受限issuer须重新按DBnow重验所有来源/审批/epoch/私有身份及正式签名。当前142库、Host/worker/现实Provider/Secret/商城源/旧Run/manual/230L0/未知重发/外部效果不触碰。完整Source及b90 Task仍ACTIVE，自然首链/八工作台/观察/发布不作完成。
