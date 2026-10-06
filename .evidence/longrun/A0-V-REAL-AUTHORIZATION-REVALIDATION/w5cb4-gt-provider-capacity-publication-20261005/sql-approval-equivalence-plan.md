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

2026-10-06 S08只读边界续查：approval-time-invalid-native.sql/log在固定隔离r4 READ ONLY验证非有限±infinity、10000年及公元前1年。纯to_char对infinity返回NULL，公元前1年投影为0001-01-01T00:00:00，与公元1年的字串相同，不能省略有限/年份域检查。isfinite(value)且UTC extract(year) BETWEEN 1 AND 9999分别拒绝四错误样本，保留Python首/末年；这只是完整批准SQL所需拒绝条件的真实反例，不是批准函数或业务发行通过。后继原完整S08事件函数必须先拒NULL/非有限/UTC年域，再使用完整微秒规范格式及13字段原hash，不凭日期字符串重构更正历史批准。

S11下一合同调查已由原Python模型真实验证：request-account-shape-probe.json中的内部空格、零宽字符账户别名被原ProviderCapacityRequest接受，但_identifier拒绝；边缘空格和NBSP被原request拒绝。原physicalAccountId仅1..200/strip-only，不是公开签名publisher的printable/nonwhitespace；后继SQL必须冻结Python strip边界而保留原内部字符，不偷换已完成Unicode identifier门。原request存储makerSubject亦只1..200/strip-only。整份JSON哈希、strict application、proposalExpiresAt原行相等/current窗口与原Provider/Evidence锁仍须组合，不由本地模型probe授Source权限。

2026-10-06 S11存储门已于ac0399db接入原_request，444项真实隔离相邻通过；原模型/clock/Provider/Evidence检查全部保留，非全原生typed application完成。S12续查原a0v_147：candidate_kind仅account/basis且revision=1，固定mode/false flags与wrapper原CHECK存在；后继读取仍须独立核整份actual/stored/expected hash、三键、wrapper candidateKind=row kind、maker=row created_by=原Source maker，不能用CHECK存在代替当前精确行/引用。候选模型physicalAccountId/supplierId同为strip-only；唯一Provider mapping以asset_id唯一，并保留原exact Evidence及Source guard依赖锁序。此调查没有改历史147、创建SQL candidate入口或授供应商来源权。


## S12 文件级实施计划（2026-10-06）

在 publication_store 新增 CAPACITY_CANDIDATE_ROW_SQL，由原 source_action._candidate 直接调用。固定 public 原表与 pg_catalog 内建，按正向双租户、candidate ID/revision/kind、expected content hash 精确匹配；actual/stored/expected 三 hash 相等；原 mode、IS FALSE 两标记；request_json 恰三键、kind 与 maker 为 JSON string 且分别等于原行 kind/created_by 与原 Source maker。CASE 防止非 object object_keys 异常。不新增锁或调整原 lock-order，不改变原模型验证、租户错误语义、Provider/Evidence/currentness。

formal_boundary_pg 新增实际私有 SCRAM 账户/basis 双正向及 wrong ref/maker/kind/revision/tenant 负向；隔离 TEMP 原行形状单字段故障，JSON 故障重算 stored 与 expected hash 独立验证 structure 门，两类真实原模型重解析。专项 RED→GREEN 后运行原 Source/runtime/formal/publication 相邻。仅本 Task 文件和证据精确提交；此存储读取不证明供应商事实、完整 SQL typed candidate、签名发行 COMMIT 或自然首链，原 Task 不收口。

S12本轮验收：专项4 passed/10.00s，六模块相邻448 passed/196.91s，既有7warnings。实际原 Source consumer 已接入存储门；独立督导无新增重大问题。证据见 formal-boundary/candidate-storage-verification.md。完整typed candidate与组合发行未证明，下一步按S13–S19向完整入口收敛，原Task保留ACTIVE。


## S13 文件级组合读取计划（2026-10-06）

publication_store 新增 CAPACITY_SOURCE_COMBINATION_SQL，复用原 S11 request 与 S12 account/basis 精确存储查询，所有参数仅引用/原maker/tenant，kind分别固定account/basis。SQL读取真实原表而非调用者自由DTO：basis physicalAccountRef精确等于从原account ID/revision/hash构建的四字段ref；两个alias为string逐字相等；providerRefs必须array并逐元素JSONB完整相等于原request.providerRef；两个并发字段必须整数1..1000000且basis<=request。CASE防非array和非整数转换，固定schema。无新锁，保持原审批→组合→neutral Evidence→account dependencies→时钟/withdrawal顺序。

原 source_action 四条Python判断保留，并在其后/neutral锁前执行SQL组合门；拒绝仍SOURCE_ACCOUNT_OR_CONCURRENCY_DRIFTED。formal_boundary_pg覆盖真实私有完整Source读取以及detached三原表副本的单项反例；每次更改重算stored/expected hash，account变化同步basis账户ref，避免hash和ref错误遮蔽组合错误。原供应商验证、完整SQL typed模型、S14–S19发行及真正COMMIT TTL仍未完成；不创建发行权限或改历史迁移。


S12后继typed basis时间合同真实本地probe见basis-time-original-contract-probe.json：原ProviderCapacityBasisCandidate接受epoch秒、数字epoch字符串、小写t/z、空格分隔和+08时区（输出为原模型规范形式），拒naive observation及float/bool并发。正常CandidateStore存model_dump JSON会规范化，但原_candidate对原raw canonical hash校验后仍用model_validate读取；因此不能在“严格等价”名义下将所有历史raw候选都强行要求与SigningPermit相同RFC3339字节。必须先复核原INSERT路径/既存行约束并明确接受域：原普通Store规范输出、原读取接受域和未来发行合同各自取证；尚未批准的硬化不能隐式改变正常功能。本probe纯模型，不证明DB发行或业务权限。

S13最终验收：六模块450 passed/215.84s、7既有warnings，实际原consumer已接入三原行组合SQL，独立只读复审无重大问题；formal-boundary/combination-verification.md为证据入口。原typed模型/签名与完整prepare/commit均未收口。


## S13 原引用别名兼容调查与修复计划

原FormalExactRef继承populate_by_name=True，candidate147只限定顶层camelCase键，nested ref并未要求只camelCase；候选账户Provider refs或basis accountRef可能使用snake_case/混合别名，经原模型重解析与Python四条件成立，但新S13 raw JSONB相等潜在误拒。先通过实际原runtime INSERT/hash/CHECK和真实Source proposal入口复现，而非TEMP模型替代。若RED证实，在publication_store内部生成固定SQL引用规范表达式：精确4字段、允许每个字段camel或snake任选其一，禁止双别名/unknown字段和缺失；将basis accountRef及account Provider元素规范为原camel四字段后比较。S11/S12整份raw hash不改，Source引用仍指向原raw hash；不改模型或a147迁移。原consumer/_combination位置和原时间/当前性不变。专项真实别名正向+双别名/extra负向，完整相邻和独立复审后收口。

S13引用别名实际复现：ref-alias-red.log两项通过原runtime实际INSERT/CHECK，原模型/Python组合通过后在新增SQL处SOURCE_ACCOUNT_OR_CONCURRENCY_DRIFTED误拒，8.48s。第一修复ref-alias-green.log暴露箭头与减键运算优先级未加括号；修复后第二轮测试同时与尚未退出旧累计竞争全局隔离issuer角色，并且测试断言将proposal原drafted误写awaiting_approval。该轮失败不算逻辑通过。已结束旧轮(143)，只读核隔离aos-a0v-test-pg的aos_guard_approval_issuer为NOLOGIN且无password/活跃连接；不存在真库操作。最终串行ref-alias-green-r3.log 6 passed/14.03s，原native四种snake/mixed别名Source proposal均drafted、存储哈希未重写；原重hash负例扩展双别名/scalar拒绝。最终相邻ref-alias-adjacent-r2.log仍待终结，禁止将早期中止或状态断言失败作为完成证据。

最终串行相邻回归已终结：ref-alias-adjacent-r2.log 454 passed/207.14s，7既有warnings，exit0。自复审与限制见ref-alias-verification.md；独立督导自主复审本次修复尚无新结论，不宣称独立复审收口。

## S14 原完整 Provider 集合入口验收调查

候选一：S14–S15原完整Provider/Evidence当前性，有现formal-boundary Task/Lease授权，无真实Provider调用，先证明多Provider原实际入口。候选二：AIS-001的231摘要更新，需独立文档scope登记，先不越现租约写入。选择第一项。具体测试文件 services/aos-api/tests/aip/test_provider_capacity_formal_boundary_pg.py；证据同formal-boundary目录 provider-set-original*.log/md。用原Store真实建立两个Provider的account/basis，第二个不是request.providerRef；合法完整集合须原Source proposal成功。随后仅改变第二Provider head或payload，原入口须拒绝且proposal计数不增加；不改业务代码，不先复制Model解析进SQL。调查明确S14原模型、当前head和canonical payload的最低等价证据，后继原生SQL须核全部集合并保留原锁序；本调查不当完整发行通过。

S14完整Provider集合原入口实测：3 passed/10.61s，整formal-boundary文件80 passed/106.22s；证据见provider-set-original-verification.md和精确sources.json。追加Provider独立漂移拒绝且无新proposal。业务代码未改；下一实现必须保留allocation先Provider、neutral Evidence、account全部Provider的真实前缀锁序和typed canonical内容校验，不能只做集合存在/count。已消费独立督导RQ-02具体对象/connection锁图约束；完整native发行/consumer及实际COMMIT仍未证明。

## S16 两批准撤回的完整私有入口竞争验收

两个已登记候选：S14 Provider typed全原生接受域需先解决非strict原模型归一合同，不能用raw JSON hash偷偷收窄；S16已安装151 epoch与完整原read_capacity_approved_claims可独立实际竞争验收。选择S16：现formal-boundary Task/Lease授权测试文件 services/aos-api/tests/aip/test_provider_capacity_formal_boundary_pg.py 和同目录 formal-boundary 证据；不改迁移151、原Guard或真库。

目标是原Source批准和原allocation批准两项各覆盖reader-first/writer-first：原runtime直接INSERT withdrawal（不改proposal approved状态），实际private SCRAM reader运行完整原approved-claims入口并持有原conn到真正COMMIT。记录双方backend pid及pg_blocking_pids证明等待，不能用sleep成功代替互斥。reader-first允许先取得仅claims且writer等其COMMIT，之后新reader拒绝；writer-first持有原withdrawal epoch写锁，reader等待writer COMMIT后必须拒绝，不能让旧serializable快照漏看撤回。退出后核原status仍approved、原撤回真实持久及epoch=1；claims仍无supplier/execution授权。四项成功只证明此原生协调门，不是正式Source发行/实际COMMIT TTL/业务首链。专项后原formal-boundary+151 withdrawal suite相邻；保留自主督导复查与完整Task退出未完成。

S16原两批准完整private入口与runtime直接withdrawal竞争：专项4/15.04s，相邻108/148.70s；实际四组阻塞PID与双方真实COMMIT/拒绝/新reader拒绝/approved状态未改见formal-boundary approval-withdrawal-commit-proof.json。原claims协调成立，完整签名Source最终COMMIT TTL/consumer仍未证明，原Task不Delivery。

## S14 原Provider载荷版本身份缺口调查

原AipModelEvalRequestStore._current_revision先核原row id/revision/hash，再严格模型重解析/tenant/lifecycle/canonical业务内容；但业务hash明确排除revision等META字段，其返回校验未显式比较item.revision与row/ref。原ProviderPayload的revision允许>=1，改变它可能仍通过hash与全部原当前性检查。此为待实际原Source入口验证的假设，不先宣称事故。原source Task expired16:00已按官方renew_task用同owner/精确expected Task/Lease/无Delivery/无重叠恢复20:00，未删/夺Lease。

仅formal-boundary原多Provider实测新增second_payload_revision：原Store合法存两Provider account/basis后，仅隔离owner改变额外Provider payload.revision，row revision/hash/原Source refs不变，期望原Source入口拒绝且无新proposal。若真实RED证实，Source专用source_authority._account_dependencies沿原_current_revision后重解析同原模型并明确provider_instance_id/revision=每个原ref，不替换通用ModelEval语义，不改变原Provider排序、Evidence、SQL、RLS/ACL或迁移。source_authority.py由Source Task拥有，formal-boundary测试/证据由其原Task拥有；不修改非本scope ModelEval模块。保留原别名/默认/非strict字段归一接受域，正常typed exact identities不变。专项及全部Source/approval/formal/publication相邻后自复审；完整Source发行和真正COMMIT TTL仍未收口。

S14载荷版本实际RED：provider-payload-identity-red.log原完整Source proposal未拒绝（DID NOT RAISE，1 failed/8.47s）。实际只变额外Provider payload.revision，原业务hash排除META字段，证实缺口。最小修复仅source_authority._account_dependencies：沿原锁/原_current_revision获取实际row后，使用同ProviderInstanceRevision模型重解析，再要求payload provider_instance_id/revision与exactref一致；原typed alias/default/secret_ref规范化继续适用，未改全局ModelEval/SQL/迁移/权限。专项含合法双Provider与原嵌套别名共8 passed/18.52s；八模块相邻进行中，不提前计通过。

## AIS-005 自主督导要求的私有别名组合正向补验

已读reports/ais005-recheck-20261006.md：督导自主保留RESOLUTION_PROPOSED，缺四种snake/mixed原row别名在真实private批准消费者的组合正向。当前S14回归同handle终结后，先冻结其代码/日志快照，再仅扩展formal-boundary原alias测试：原runtime候选INSERT/hash/147 CHECK真实COMMIT→原Source proposal→独立原checker批准→新exact proposal/event native command（原JWT，同maker）→真实private SCRAM read_capacity_approved_claims，与changed Source exactrefs及alias原raw hash逐字一致。supplier_verified与execution_allowed必须False，无签名Source注册/容量激活。不能拼接原runtime alias正向与另一条private canonical正向；不修改督导finding状态，等其自主复核新证据。完整Task仍未交付。

S14版本身份最终八模块相邻520 passed/316.04s，8 warnings（7既有启动＋本轮扩充覆盖原source_pg故意bool序列化warning）。自复审/风险与原始日志hash见formal-boundary provider-payload-identity-verification.md/sources.json；Source局部身份缺口修复，未证明通用ModelEval所有资产或完整发行/consumer。
