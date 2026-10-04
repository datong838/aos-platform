# b88施工中检查点（非Delivery）

基线m1 f7739544，authority1329。本波Task及signed acceptance hook Task仍ACTIVE，08:00 Lease；未task-complete，不把部分事实读取交付成原Proposal/Approval。

已落工作树：严格原始来源许可请求合同/整份请求绑定；同事务Scope/SERIAL/runtime/当前Owner共享锁、安装共享锁、来源初始化协调共享锁、原Store构建存证与Receipt、真实当前签名Policy；测试hook只一次性测试库/opt-in。新文件aip_license_source_proposal_contracts.py、aip_license_source_proposal.py、test_aip_license_source_proposal_pg.py，以及原完整schema test hook。没有原ActionStore接线，没有正式Approval或issuer。

证据：合同模块缺失22failed/4.71s，合同/入口45passed/4.73s；签名实际active安装后缺请求事实模块1failed/15.05s；首次错误把state误读安装主表实际UndefinedColumn，1failed/15.65s保留，修为主表仅锁head、状态由原revision读取器验证。请求事实r2签名1passed/15.89s；最新r3真实签名1passed/16.12s，含missing Owner/admin非Owner、canary scope、构建hash、安装etag/revision、错误源hash和Policyhash拒绝；真实exact PID图验证Owner删除、安装FOR UPDATE、RC原始revoke等待主事务，所有writer及主事务rollback，事件/issuance0。合同每项源/Policy/release标识与三截止时间参与绑定，UTC/用途set等价编码同hash。最终七组累计114passed/11.92s，与旧b86的114范围不同，不混称同一全量；四文件编译/精确diff通过。测试数据库49，迁移夹具NOLOGIN角色attrs安全/成员0/依赖0后清，最终0。

下一实际施工：typed maker/checker复用原ActionStore/immutable draft和Approval event。必须先为专用metadata和独立Source Approval issuer、受限共享读锁/Scoped ACL及DB保护完善迁移方案并登记新file scope；不借guard/BI/Registry issuer，不把普通runtime请求事实当独立批准。当前asset_registry/tenant_transaction.py已经对无runtime成员的专用psycopg issuer保留其自身GRANT/RLS身份，因此无需伪造SET ROLE或复制Registry读取器；b88当前请求事实明确只收aos_runtime，后续需为已验证的专用连接增加严格身份分支及实PG RED。绝不能只删该角色检查来让测试绿。metadata须原meta_object_type/meta_action_type的冻结受保护对象，不另造Approval2/LicensePolicy2。

用途请求仅internal_business_analysis/traceable_derivation；rightsAttestation为明确拟议Owner声明，非外部权利证明。源freshness/coverage为原构建快照，不冒充八维实际最新Health/Capacity/evaluator。source_request_hash是provenance证据而非数据许可。三个结果REQUEST_ONLY_NO_START/SOURCE_REQUEST_FACTS_ONLY_NO_START/SIGNED_POLICY_EVIDENCE_ONLY_NO_START均不授权启动。

当前135真库未迁移/重启，Host/worker/Provider/商城源/旧Run/外部效果未执行，无页面改动/无浏览器验收需要，无真实模型调用；agnes r3 assessment6/7及O4限制保留。用户九M保护，当前新增代码未提交，未push或动其他分支。所有本波pytest session均terminal（49579/97610/50462/25818/47155/50715/74160），不可因为日志存在重启它们。整体Goal active，自然首链pending。


### 2026-10-05 06:35 b88 原Proposal接线与审批边界续证（仍施工中）

本节更新此前“没有原ActionStore接线”的施工状态：现已新增 exact typed maker，复用原AipActionStore创建原Proposal、immutable draft及同键回放；原生同一SERIAL事务核验当前Owner、安装、来源存证、真实签名Policy及冻结metadata。内部OIDC Principal仍为隔离测试fixture，尚未实现生产签名JWT adapter。批准0、issuance0，不能称合法来源许可或完整审批交付。

本轮具体代码目录：services/aos-api/aos_api/aip_license_source_proposal_contracts.py、aip_license_source_proposal.py、aip_action_store.py；services/aos-api/alembic/versions/a0v_140_source_license_action_metadata.py；services/aos-api/tests/aip/test_aip_license_source_proposal_pg.py、test_source_license_action_metadata_pg.py；services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py。a140冻结原SourceLicenseRequest/action metadata，保留NOLOGIN独立批准角色且不授业务ACL；冻结来源Proposal非生命周期字段，原status/version/updated_at仍可按原规则变化。

真实RED：runtime同时把来源action ID与snapshot ID改成普通动作未被拒绝，1failed/19passed/24.47s；最新冻结条款保护已修。RLS隐藏来源Proposal反例由既有a0v118保护拒绝，未写批准，不是越权实证。最终相邻累计150passed/7warnings/86.50s；最新a140完整签名安装+maker/replay验收1passed/7warnings/16.74s。七文件编译及已有修改精确diff检查通过。原49测试数据库保留；两本轮临时NOLOGIN角色安全属性、成员0、共享依赖0核验后删除，剩余0。证据在代码.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/w5cb4-e17-s3owaob88/green-maker-metadata-final-cumulative.log与green-signed-maker-metadata-final.log。

b88 root、signed hook及metadata三Task仍ACTIVE；代码未提交、无Delivery，整体Goal active。下一必做独立checker及正式连接/Scoped ACL、原Approval正向与竞争回滚验证，并完善真实OIDC身份adapter；不得借maker或其他issuer批准，不得移除事实读取角色检查。当前135真库只读且未迁移/重启，Host/worker/Provider/商城源/旧Run/外部效果关闭；用户九M保护、未push、不改其他分支，无真实模型调用，保留agnes r3 assessment6/7/O4限制。


### 2026-10-05 07:19 收口验收
本波typed maker/checker、外部签名JWT adapter及独立SCRAM连接代码已完成隔离验收：159项累计/86.99s、最新signed完整schema141 1项/21.59s。四PID竞争、原撤回/真实expiry、canary及原事件回放成立，issuance0。待精确commit及四Task/Delivery登记后交付此b88；完整来源发行仍下一b89，Goal active。详verification.md；此前本文件无接线/未有批准语句仅历史施工状态。
