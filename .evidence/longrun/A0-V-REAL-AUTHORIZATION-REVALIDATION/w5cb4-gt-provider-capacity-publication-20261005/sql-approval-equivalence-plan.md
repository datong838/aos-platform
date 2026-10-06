# 原批准到数据库发布入口的等价检查表

基线55194683/AOS-001375。本文是完整publication原Task内的实现合同草案，不是已存在SQL、不证明正向发布。原源码hash和调用链见publication-entry-audit.json。沿原Proposal/Approval/Candidate/Request表与canonical计算，不创建第二审批状态或接受Python PASS。

## SQL端不得省略的检查

| 编号 | 原入口与权威事实 | 数据库端接受条件 | 直接issuer负例 |
|---|---|---|---|
| S01 | formal_boundary.require_capacity_issuer_identity | 原session_user与native role均为issuer，正向双tenant、SERIALIZABLE、非autocommit、正常replication；固定实际owner/ACL/RLS/函数与trigger fence | SET ROLE、额外schema/helper/表/函数grant、错scope、非SERIAL |
| S02 | source_issuer.authenticate_capacity_issuance_command | 受控signer核原JWT的真实subject/issuer/audience/expiry；签名原文绑定主体、原command requestHash及DB实际prepare事务；SQL按原maker重算binding并验授权permit下的签名 | 自报maker、Python verified、任意bytes签名、授权上下文互换 |
| S03 | formal_boundary.read_capacity_approved_claims | Source proposal原actionType、approved状态、version=2、exact proposal_hash、maker真实主体、未到期 | 未批准、wrong action、ref/hash/version漂移 |
| S04 | 同入口approval_event | 该proposal恰一条approved checker.1 event；原proposal_version=1、proposal_hash/action_binding_hash/approval_policy_hash一致，expiry有效，exact event ID及模型规范body hash一致 | 双event、不同slot、任一hash/expiry漂移 |
| S05 | Source/Capacity guard read_metadata | 两专用Action及Object metadata逐字段与原固定snapshot一致，canonical metadata revisionHash正确；原FOR SHARE顺序 | metadata一个字段变异、换revisionHash |
| S06 | Capacity guard check_proposal | task/run/object/impact/client_risk_hint均无附加执行目标；diff={}、evidence_refs=[]；source/request各专用purpose与payload字段集合严格匹配 | 注入task/run/附加payload或effect字段 |
| S07 | 同guard check_request/risk | 固定专用R2风险与makerChecker/executionAllowed=false/draftOnly=false规则，policy_snapshot与原canonical policy hash、原actionBinding重算一致；不可自由接受risk/policy JSON | 篡改风险/审批策略/actionBinding |
| S08 | 同guard draft + ActionStore._bundle | 原draft snapshot canonical hash等于proposal_hash，payload/actionType/policy/actionBinding与proposal一致；draft.status=approved；event canonical格式复用原模型字段与时间表示 | snapshot/body/hash/status任一漂移 |
| S09 | Capacity guard._role / checker | 当前maker/checker各原meta_membership Owner记录持SHARE，maker≠checker；eligibility原tenant/actor/roles=['owner']/slot/policy hash重算一致 | checker等于maker、撤销任一Owner、资格hash漂移 |
| S10 | Source guard._allocation | 原allocation request/approval及proposal属于同maker、正向tenant和专用Action；唯一原批准、其binding/eligibility/body hash与source exactref匹配 | 换批准、不同maker、旧版本/多event |
| S11 | Capacity guard._request | request_json恰application/makerSubject；canonical原request hash一致；REQUEST_ONLY_NO_CAPACITY_NO_START、basis_verified=false、execution_allowed=false；expires_at与原proposalExpiresAt及validity一致 | 候选或测试pass冒充正式申请、bool/shape/hash漂移 |
| S12 | Source guard._candidate | 原account/basis候选exact ID/revision/kind/hash、candidateKind/makerSubject与原maker；CANDIDATE_ONLY_NO_CAPACITY_NO_START、basis_verified=false/execution_allowed=false；严格候选模型 | 自由DTO/alias、错maker、误标verified、额外字段 |
| S13 | Source guard account/basis/request组合 | basis.account exactref等于source.account；account alias等于原request alias仅用于匹配，不能作global ID；request Provider属于account全集，basis并发不超过原申请 | 拆账户、少Provider、超申请并发 |
| S14 | _current_revision/_account_dependencies | 原Provider head/current exactrevision/contentHash、状态与原模型要求一致；全部Provider exact集合，无重复或跨tenant；按现原guard持锁 | head换代、disabled、old ref、集合缩减 |
| S15 | Evidence/production contract与neutral fence | 三路原Evidence exacthash、frozen/nonrevoked、原build provenance/contract；原neutral epoch锁/fence必须有效；不得仅evidence存在 | revoke/build/contract drift、epoch或函数ACL/hash漂移 |
| S16 | Source guard151 withdrawal fence | Source与allocation两个proposal均无withdrawal；对应实际epoch锁及owner/ACL/trigger结构有效；保持原guard内部顺序 | 普通withdraw及直接INSERT，两方向竞争、epoch删除 |
| S17 | source_issuer.check_signed_capacity_documents | 原policy/attestation raw typed/canonical、独立trusted root/permit取钥、Ed25519、purpose、tenant、exactref与原raw SHA256；受控root/policy currentepoch | caller key、verified flag、重签重复字段、错purpose/rootref |
| S18 | check_native_capacity_supplier_inputs | policy指定attestation publisher/key/root/supplier；supplier/fingerprint和Provider全集等于原account，Evidence等于basis；token模式/unit/上界及fixed-window秒数/anchor精确相等 | 任一计量/供应商/窗口/集合变异 |
| S19 | 同入口窗口/observation | policy/attestation/basis/request/两proposal/两events/Source有效窗口交集；supplier_observed_at当前年龄/未来偏差满足policy，supplier_limit_claim observation等于basis | old/future observation、窗口越界、批准临界过期 |
| S20 | publication的新域 | 独立anchor/bootstrap/permit exactrefs与实际部署、签发主体授权；DB推导global稳定ID/Provider映射；同事务的精确待签bytes与完整Source签名绑定；全域唯一约束 | wrong DB/cluster/映射、自由stableID、跨tenant归属 |

S02不能由SQL解析自由maker或调用者JWT已验boolean满足。S05/S07/S08/S10/S11/S12/S14/S15必须进一步展开为原字段/公式/查询与native单项变异案例，本文不是穷尽的已冻结函数体。metadata/risk和各文档shape只实现专用合同，不向通用Action增设另一套批准引擎。

## 锁图与反例的证据要求

原guard完整检查后取新域；不能把原guard重新排序成“全部Provider先于neutral”。151 withdrawal函数现严格拒其owner额外权限，新publication owner不得直接获得epoch表权限或篡改既存owner审计。新增受控publication读取所需窄接口必须先登记、真实验证兼容原issuer/runtime与owner fence，不能偷偷GRANT后放宽原审计。

每个S项须登记SQL函数中的具体判断、原表/列及canonical计算、positive原事实、仅变一项的issuer原生拒绝。长窗口与真实阻塞必须在隔离完整151库验证；不存在a152或空库函数名称查询不算完整COMMIT RED。正式bootstrap来源与运行权限另门。

## 当前已证明与未证明

四项pg_temp原生实验仅证明延迟约束可以拒绝未finalized attempt、接受完成后提交、保存点恢复仍拒绝原pending，以及撤销prepare后提交无残留。psql在保存点恢复案例exit0并不意味着无错误，日志明确两次约束拒绝。

实际反例证明SET CONSTRAINTS ALL IMMEDIATE可提前执行时钟检查，随后等过expiry仍COMMIT成功。因此不把延迟trigger作为真正提交时TTL保证；时间合同仍须解决，并由每次consumer的当前性独立门保证任何过期Source不能授业务权限。暂不开放正式prepare/commit，不收口原Task、不停止其他安全施工。
