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


## S05/S07/S08 原字段与计算细化

approval-static-contract.json从原两guard的固定snapshot与原classify_action_risk专用分支实际生成，源码hash绑定31488428。payload的None值仅用于选择原静态分支，不是合法申请或批准。Source与allocation均R2、floor R2、makerChecker=true、minimumApprovals=1、executionAllowed=false、draftOnly=false；reason分别formal_provider_capacity_source_review与formal_provider_allocation_application，不能偷换通用R2理由。policy_snapshot精确等于floor/reasons加完整原approval_policy，hash原canonical(policy)，额外字段也拒绝。

S05原Object查询的精确列：id/name/description/published/properties/required_markings，分别映射原object_snapshot的snake_case列；必须仅一原行且逐字段一致。Action查询id/name/object_type/parameters/required_markings/submission_criteria，生成原camelCase objectType/requiredMarkings/submissionCriteria，精确与原action_snapshot匹配；revisionHash=canonical(actionSnapshot但不含revisionHash)的SHA256。SQL不能拿包含数据库其他列的row_to_json做该hash；Source metadata为baedab1f0b8e77224e7e969978ac306f34eeec41cd014013d2bbf9dada8e1028，allocation为9f64ba00ef5a85d203c82c45afaa1eb25c000162e9e5b2405614a7aa7ae295e9。固定字节存档不是live metadata通过证据。

S07 Source actionBinding=canonical({sourceCandidate:原严格模型JSON,actionTypeRevisionHash:Source metadata revisionHash})；allocation binding=canonical({requestId:原request ID,requestHash:原request hash,actionTypeRevisionHash:allocation metadata revisionHash})。eligibility=canonical({tenant:{orgId,projectId},actorId:原批准event.actor_id,roles:['owner'],slotId:'checker.1',approvalPolicyHash:对应proposal原policy hash})。Owner原角色判断lower(role)='owner'且唯一；不能用caller提供roles或makerSubject重算资格而省当前membership锁。

S08批准event canonical body精确字段来自原ActionApprovalEventSnapshot：id/proposalId/proposalVersion/proposalHash/decision/actor/reason/expiresAt/createdAt/actionBindingHash/approvalPolicyHash/slotId/eligibilitySnapshotHash。actor恰{actorType:'user',actorId:原actor_id}，reason保留原字符串（模型缺值默认''不可借此覆盖原SQL NULL不合法字段），可空model字段保持null，不exclude_none；批准入口另必须要求expiresAt非NULL且当前。完整draft模型默认字段、status及原snapshot hash同样不能以事件存在替代。

approval-time-format-readonly.sql/log/json在隔离r4 READ ONLY、SET LOCAL TimeZone UTC实测0/1/100000/999999微秒。PostgreSQL to_jsonb(timestamptz)四例均与原模型字符串不同（UTC偏移及尾零表现）；显式to_char(ts AT TIME ZONE 'UTC','YYYY-MM-DD"T"HH24:MI:SS')，微秒为0不带小数，否则'.'+US六位，再加'Z'与四例原模型精确匹配。后继SQL批准事件格式必须规范UTC和六位微秒，拒绝infinity/超出Python可表达年范围；不得直接用timestamptz::text/hash。新完整入口的TimeZone及原ref构建需共同冻结：现private connection未固定TimeZone，当前原guard并未审计它；不能凭本四例宣称全部历史时区ref兼容，需要真实原批准UTC与合法改时区拒绝/兼容矩阵。此实验只证明格式机制，没有新事件/metadata/body函数或原生publication。

## AOS-001379 S10–S19动态事实精确展开

本节按原source_action._allocation/check_request、capacity_action._request、source_issuer.check_signed_capacity_documents/check_native_capacity_supplier_inputs源码展开，不是已实现SQL许可函数。

- S10：由allocation exact event ID取唯一原event，再按其proposal_id锁原proposal。request.created_by、proposal.created_by必须等于原Source maker；action_type_id=aip_request_provider_capacity；payload恰{requestId,requestHash}；proposal approved/version=2，原event decision=approved/proposal_version=1/slot=checker.1，三hash与proposal一致，expiry非NULL且>DB now。该proposal全event计数=1；不能只数approved事件。保留原withdrawal检查、原Capacity guard全检查、eligibility和完整event模型hash核对。
- S11：原request_json仅application/makerSubject；makerSubject=created_by；整份request_json的原canonical hash=stored hash=Source exactref hash。authorization_mode固定REQUEST_ONLY_NO_CAPACITY_NO_START，basis_verified和execution_allowed必须IS FALSE，不能将NULL当false。严格application模型与双tenant成立；proposalExpiresAt=原row.expires_at；validFrom<=DB now<proposalExpiresAt<=validUntil。Provider当前版本与原basis Evidence均独立复核。
- S12：按tenant/id/revision/candidate_kind精确取account或basis；stored content_hash=整份request_json的原canonical hash=exactref hash；request_json键恰candidateKind/candidate/makerSubject，candidateKind=查询kind，makerSubject=created_by=原maker。authorization_mode固定CANDIDATE_ONLY_NO_CAPACITY_NO_START，两boolean IS FALSE；candidate严格模型和双tenant再核。原候选没有签发authority，不以正确hash推导供应商已验证。
- S13–S15：basis.physicalAccountRef=Source account ref；account.physicalAccountId=request alias，仅作原申请匹配；request.providerRef属于完整account.providerRefs；basis.maxConcurrency<=request.requestedMaxConcurrency。先沿原guard完整执行其Evidence/Provider锁序，不重排：neutral epoch涉及request basis Evidence、account Evidence、basis Evidence三路；随后原account dependencies及basis Evidence。完整原production provenance、frozen/nonrevoked和head/current revision不能由新SQL粗略存在查询代替。
- S16：原完整Source check_proposal结束前，Source和allocation withdrawal epoch已锁；新域只能后缀加入。直接INSERT撤回无需改proposal.status亦必须拒绝。S10提前普通SELECT不是竞态完成证明，正式验证必须覆盖writer-first和reader-first及实际阻塞。
- S17：两原签名payload类型/algorithm/purpose、tenant、asset ID/revision/canonical raw hash与command exactrefs严格一致；各validFrom<=DB now<validUntil，Ed25519密钥从独立受控root取得。attestation root存在且revision=policy.attestationRootRevision；不能issuer自给key或只靠Python验签结果授SQL发布权限。
- S18：attestation.publisher/keyId/supplierId精确等于policy允许三元组；supplierId/fingerprint精确等于account；Provider集合按(type,id,revision,hash)排序后精确相同（不能只比较一个Provider或count）；attestation.evidenceRef=basis.evidenceRef。attestation.maxConcurrency>=basis.maxConcurrency，token mode/unit必须相同且maxTokens>=basis.maxTokens；fixed_window_rate额外windowSeconds/windowAnchor精确相同，不作单位换算。最终Source计量不得偷偷升级到供应商上限，仍按原批准basis条款推导。
- S19：attestation token mode在policy允许集合中，observedAt<=DB now+maxFutureSkewSeconds，DB now-observedAt<=maxObservationAgeSeconds；attestation窗口整体在policy窗口内。Source窗口分别被policy、attestation、basis覆盖；source-action另要求max(request.validFrom,basis.validFrom)<=Source.validFrom<=DB now<Source.validUntil，Source.validUntil<=min(request.validUntil,request.proposalExpiresAt,basis.validUntil,allocation event expiry)，Source proposal effectiveExpiry<=Source.validUntil。supplier_limit_claim要求attestation.observedAt=basis.observedAt。最终核JWT主体仍为原maker，再读两原proposal和event截止（恰两个精确event ID，期限全部非NULL且>当前DB now），再验签名当前性。真正COMMIT前TTL问题仍待裁决，不把本组计算当其解决。

S08整份事件原生计算新增证据位于formal-boundary Task的approval-event-native-probe-r1.log：真实原Source及allocation批准13字段投影与原模型/refs精确一致，默认SQL时间投影hash不同，26次单字段改变hash。私有连接UTC/drift门已于m1@9c1af075实现；前节“现连接未固定”仅描述旧基线。实验未核所有NULL、infinity/超范围年负例，未证明完整SQL批准/Owner/撤回/发布和历史非UTC兼容。
