# BG00FR 费用提议持久化与原请求查询

基线AOS-001032/955f5b37；复习231-5§5/6/7、231-9、424/425、FQ、预算Store及network独立签发边界。Task W5CB4-BG00FR-20261001。

## 本波生产者与独立审批边界
提供正式OIDC当前maker的提议生产接口，当前独立checker必须存在且owner/admin；两人能只读完整提议。此记录状态恒proposed、sourceVerification=pending、activationEligible=false，不生成approved Decision，不接预算激活。aos_runtime仅能写这种未批准输入，不能通过它获得任何consumer执行权。独立预算签发者及受限consumer需专域ACL，不能借network issuer、通用approvalRef或此提议替代；BG00FS接专域审批。external reconciliation尚无正式Owner，create明确SOURCE_AUTHORITY_UNWIRED，未知费用不写0。development Provider/model是待审核精确候选，本波不宣称已通过Provider来源/可执行性核验。

## 文件级计划
1. aip_budget_cost_basis.py增加from_canonical_payload：重建DTO、精确比较派生账户/币种/期间与规范内容，hash envelope读回不信任冗余字段。
2. aip_budget_activation_store.py仅抽取既有空账本/精确draft→target检查为require_initial_budget_target，共用于旧preview和新提议，旧hash/返回不变。新来源重算target时使用原预算canonical语义，避免新hash与旧hash混用。
3. a0v_124_budget_cost_proposals.py新建proposal及receipt两表，scope FK/RLS FORCE/不可变触发器、SELECT/INSERT给runtime，不改变旧预算active门。Proposal状态只能proposed、不可执行；Receipt按scope/actor/key唯一并外键proposal。无history backfill、no worker、downgrade拒绝。只在隔离库验证；当前实例迁移必须独立一致备份/全链克隆/零执行窗口波。
4. aip_budget_cost_proposal_store.py：SERIALIZABLE、oidc/current两member、原maker匹配、scope、same-key advisory lock；replay必须原hash一致，历史返回不变。新写精确head/draft/target、空账本、DB时效；proposal+Receipt同事务。read用READ ONLY/repeatable-read/aos_runtime双scope，canonical重建/hash/主体/budget关联校验；GET仅maker/checker当前成员，Inquiry仅原maker/key/hash，缺失unresolved、漂移conflict、DB异常503不伪装missing。全程不启Provider。
5. routers/aip_budgets.py新增POST /cost-proposals，GET /cost-proposals/{id}，POST /cost-proposals/inquiry，响应no-store；现有require_principal校验真实OIDC，dev拒绝。body含expectedHeadVersion，无另猜ETag。旧路径不改。
6. test_budget_cost_proposal_pg.py：隔离PG、真实TLS签名JWT HTTP、生成/响应丢失后的Inquiry/并发key/不同body/当前成员撤销/错scope/target/head/派生字段篡改/表不可变/事务失败无部分写/原预算preview回归。独立checker只能读，不冒充批准。无UI改动，浏览器不适用。

## 验收和下一波
RED→实现→专项与预算相邻→方案/代码复审→verification→m1精确提交→Delivery/CAS/426/D-waves/Prime。生产当前库只读且旧live版本需下一安全波实测，不能宣称每日最新。BG00FS建立预算域独立签发者、exact提议checker决定/撤销及Inquiry，之后受限原子consumer激活+Receipt、产品表单/恢复、真实身份与首链验收。暂不扩37Skill/旧Run/商城源/230L0。

复审：提取的公共函数实际名read_initial_budget_target，返回锁定账本与原始候选payload；旧preview继续原canonical hash比较，新提议比较复用DTO（日期等价语义）并另以新域hash绑定。回读检查createdAt在目标有效期内，expiresAt严格等于min(created+30min,target.until)。补DB三种伪授权字段拒绝及read故障503测试。
