# b89 原批准消费与完整受限来源许可发行

基线m1 28468f7e / docs1e31ad43 / authority1329。b88四Task/Delivery已DONE，原批准代码及隔离验收成立，但license issuance0，当前135真库仍只读。本方案执行原b87 integrated-plan步骤3，不用更小的NO_START reader替换完整发行。

## 文件级施工库存
- services/aos-api/aos_api/aip_license_source_issuer_contracts.py：严格SourceLicenseIssuanceCommand，复用原SecretStr命令base与ExactRevisionRef。仅明确已批准ActionProposal ref（version>=2/hash）、tenant/idempotency key；无actor/roles/grant覆写。发行请求绑定scope、实际认证maker、完整approved ref；JWT/key不入hash或Receipt。DTO仅ISSUANCE_REQUEST_ONLY_NO_START。
- services/aos-api/aos_api/aip_license_source_issuer.py：独立aos_source_license_issuer身份与SCRAM/固定scope/SERIAL/schema/timeout连接、实际外部JWT adapter；与来源批准写者分离，不借Registry/BI/network身份。复用原Store Proposal/draft信封、原Approval event/eligibility、build provenance/Receipt、签名Policy及RegistryReceipt append/hash/readback，不造影子许可表或Receipt。命令actor必须原maker当前Owner；独立checker也仍当前Owner。先原issuer key lock→原Proposal共享锁→两Owner共享锁→installation共享锁→精确来源初始化独占锁（升锁前即独占，不能先share后升级）→当前release/Policy再核验。无withdraw/expired、唯一checker.1绑定审批、原snapshot/hash/Policy/rights用途/有效期全检；live DB clock每个阻塞锁之后和提交前复核。
- services/aos-api/alembic/versions/a0v_142_source_license_issuer_boundary.py：新NOLOGIN/NOINHERIT/无成员高权发行角色；只授scope SELECT、受保护共享锁列、source issuance/head及原source_license.issue RegistryReceipt INSERT。runtime和来源批准角色无发行写权；Receipt operation保留trigger拒其他身份，新issuer不能写其他operation，Source tables仅新issuer写。head首发不覆写旧head，重复不同key不再发行，原撤销共享初始化锁继续正确；不回填历史数据。
- services/aos-api/aos_api/aip_license_source_proposal.py、aip_license_source_approval.py：原事实/信封/认证基础按精确专用身份扩展与共享复用，不删现有角色检查，不给maker/checker发行权。必要的原RegistryStore调用保持单txn，response构造在唯一commit之前。
- services/aos-api/tests/aip/test_source_license_issuer_pg.py：先合同/身份RED，实际signed1.13.0当前安装+原build+真正独立原批准→专用发行→原source fact读取。原key replay仅对账，wrong actor/ref/key冲突；竞争first issue/revoke、current Owner移除、Policy/installation drift、撤回/expiry拒、响应/提交失败0 issuance/head/Receipt，canary0。真实test Owner/JWKS transport/SCRAM临时供给不称生产身份授权。
- services/aos-api/tests/aip/test_source_license_approval_pg.py：在原signed helper批准后新增独立发行验收入口，另登记hook Lease，避免把b88的issuance0旧断言直接改为假完成。各阶段source事件计数按真实步骤记录。
- services/aos-api/tests/aip/test_aip_license_source_proposal_pg.py：原signed请求helper外层保留b88发行0断言；独立hook Task只在b89显式opt-in且完整issuer helper通过后对账实际source唯一发行。默认b88仍发行0。首个实际signed测试已走完issuer正向/回放/失败rollback，但外层旧零断言使整体1failed/24.74s，不计整体GREEN。

## 当前性与锁复审必做项
原signed Policy事实是事务快照，不能把它直接当消费许可。发行前核对Registry release/signature/evidence是否可撤销/到期以及原revalidator实际时钟；需要时按已有owner算法增加精确共享锁/有效窗，不复制Registry验证器。记录锁顺序、确切PID竞争和SSI失败原类型。旧缺provenance/审批的source拒，不人工升权。

### 2026-10-05 07:35 源码复审后的实施约束
- 原 RuntimeReleaseRevalidator.revalidate_in_transaction 已取得 pg_advisory_xact_lock(228,1)，随后用 clock_timestamp 与新 ReleasePolicy.snapshot 验证全部 selected releases；228assetinvariants 对 artifact/dependency/evidence 三投影的直接SQL变更也有 statement trigger 取得该锁。不能另复制签名/证据选择算法。
- SERIAL 事务如果先读 Proposal/Owner，快照会先于 Registry 锁建立。单凭稍后拿到 advisory lock，不能声称快照已经刷新。发行消费必须在 Registry 原锁内对每个 selected version 及其证据做精确共享行锁，保证快照建立后已提交的相关修改触发原 SerializationFailure；再走原 revalidator。确切行锁列 ACL 必须有实际DML禁入，且不得扩大来源批准角色权利。此处是待验证的设计约束，尚无本轮PG竞争实证。
- ReleasePolicy 的签名证据 expires_at 必须等于 trust_root.not_after；必需证据可以各自到期。初始验证通过不能替代响应构造后、唯一commit前的最新数据库时钟重验。最终有效窗须保守限定到原许可/Proposal/Approval期限，且在同一Registry锁内重新调用原签名策略验证最新时钟；不能从静态DTO推断剩余有效性。
- 新发行合同不接受 grant/actor/roles；完整批准 ref 的 resourceType/resourceId/revision/hash、实际maker和tenant进入请求哈希。幂等key与SecretStr JWT不进入哈希。model_copy/construct输入必须重解析。本轮合同测试仅验证请求约束，不证明批准或发行。

## 正式完成条件与边界
完整命令及正向/竞争/回放/回滚/撤销验证后才b89 DONE/Delivery；合同GREEN中途不交付波次完成。许可证只限定内部分析/可追溯衍生，不能启动Host/worker/Provider、商城源或外部效果。当前135迁移仍独立正式门+备份完整恢复+零执行窗口；本波仅一次性测试库。m1单写、无push/其他分支、保护九用户M。整个Goal active，自然经营首链及八实际配置继续必须真实验收。

### a142 数据库边界落实清单
新增issuer仅NOLOGIN保留；已有同名危险属性/成员拒绝，不自动修复。发行表/Head仍是a136原表；授独立issuer scoped SELECT+INSERT，不授UPDATE/DELETE。Proposal/draft/approval只读及各一个受trigger保护UPDATE列用作FOR SHARE；这些实际DML全部拒。Registry version/evidence共享锁列同样只作锁定，原投影锁顺序继续使用。
原Receipt source_license.issue操作仅独立issuer或原tableowner维护身份可写；issuer写其他operation拒。tableowner既有隔离fixture维护不提升为合法授权，runtime与sourceApproval无发行ACL。发行记录owner_authorization_ref保存schema、原批准精确ref、maker/checker/原批准event id、原grantBindingHash与整份requestedGrant；policy_ref为原签名Policy精确ref。DB INSERT时共同检查scope/自身session=current角色/SERIAL、原approved Proposal/hash/version/独立event及两Owner/current installation/无withdraw或revoke/有效窗，Receipt actor/source/result严格对应；Head只能引用新issuer同scope精确原issuance并保持初始化epoch，不能覆写历史Head。原FenceOwner的撤销epoch更新保留。
source_license.issue Receipt增加原表上的延迟约束触发器：真实COMMIT前必须有同scope、同Receipt和result issuance id的原issuance及精确Head，防止专用发行角色只写applied Receipt后单独提交。普通Registry operation、b83.test-only维护夹具不受此约束；不创建第二Receipt权威。HEAD还复核原Receipt操作/结果id及授权schema，缺省/空值明确拒绝。
延迟约束还必须用clock_timestamp在真正COMMIT时确认issued_at<=当前时刻<expires_at。响应构造后的Python时间复核不能覆盖调用方持有事务至到期的间隙；增加真实短期原Proposal/独立Approval→发行响应已构造→等待DB到期→COMMIT拒绝且三记录回滚的验收，不能只模拟Python异常。
