# b88 原 Owner 精确来源许可 Proposal / Approval

## 方案复习与基线
依231首链优先与栖月汇动作权威归属矩阵，继续b87 integrated-plan步骤2。基线m1 f7739544，authority AOS-001329，七强CURRENT/validate GREEN；当前135真库只读。已登记Task w5cb4-e17-s3owaob88-original-owner-source-license-proposal-20261005，唯一写者，08:00 Lease。

## 文件与执行顺序
1. `services/aos-api/aos_api/aip_license_source_proposal_contracts.py`：严格来源声明DTO及请求绑定。原ExactRevisionRef/VersionedAssetRef复用，资源域固定EvidenceBundleRevision/LicensePolicy revision1；sourceRequestHash绑定原canonical provenance。selected release含publisher/bundle/version/content/signature fingerprint/evidence revision全元组。installation UUID/etag/current revision准确，整数不接受bool；用途明确且许可只可请求内部分析或可追溯衍生产物，不请求任何外部发送/Provider/源读取权。licenseId、明确rightsAttestation、usagePurpose及aware UTC有效窗必填。此为拟议Owner声明，非license fact。
2. `aip_license_source_proposal.py`：输入从typed DTO重新验证（model_copy/construct不能绕过）。OIDC Principal外部adapter必须实际验证JWT，scope和actor不能来自payload；当前PG Owner exact row共同锁，OpenFGA模式缺current adapter拒。读取原frozen/current/未撤销Evidence与canonical provenance、当前签名Policy；共同installation/初始化锁保持到外层commit，DB clock检查freshness/有效期。专用metadata权威不能以裸摘要代替，若需要新metadata migration，先扩充方案与单独Task，再修改当前test schema。
3. 原 `aip_action_store.py` 仅增加exact typed producer/checker参数与前置分支，拒callback/subclass。复用Original Proposal/Draft/hash/Approval event/Receipt规则与TransactionBoundConnectFactory，不复制算法，不解除通用服务/执行器拦截。checker独立且再次读原Owner和源/current policy。approval writer须独立正式身份；不借guard/network/BI/Registry角色。身份/ACL需独立迁移Task；不可先用普通runtime签发正式许可。
4. `tests/aip/test_aip_license_source_proposal_pg.py`：先合同RED，拒model_construct/bool/noncanonical refs/错误域/未知用途/时窗；逐字段变更绑定。随后真正隔离PG Owner和独立checker +实际signed active安装/verified Policy +原Store build provenance正向Proposal/Approval；不mock正向SignedPolicy/Owner/issuer。若复用完整schema验收hook，先登记其file scope补充Task。

## 绑定及生命周期
binding schema aos-source-license-proposal/v1 包含scope、authenticated maker、固定Action ID及整份canonical requested grant。用途集合唯一且排序，时戳统一UTC，所有版本/hash准确。DTO/绑定只 REQUEST_ONLY_NO_START；生成不写数据库，不证明Owner身份、来源当前性、许可或审批。数据库写之前仍须步骤2/3；测试此纯函数不能记作正向批准完成。

原Approval消费需要Proposal version/hash/action binding/approval policy hash、原immutable draft、checker.1及eligibility、独立checker、无withdrawal、当前Owner和源/安装共同锁、数据库live clock最迟有效期。批准后的replay只能对账原event，不重复签发。下一独立issuer原子写issuance/head/RegistryReceipt仍属完整发行必做项。

## 本波退出及边界
Task只有完整typed maker/checker及隔离PG真实正向/拒绝通过才DONE；中间合同GREEN不提交Delivery冒充完工。当前135不迁移，不放开真实身份，不启动Host/worker/Provider/商城源或旧Run。保护9用户M，精确commit文件，不push。整个b88无页面则浏览器不适用，存在页面接线必须另验。长程Goal active，真实自然首链仍待证据。

## 实证接续：真实签名源请求事实
合同RED22项/4.71s→合同与入口45项/4.73s。Registry Release三个摘要沿用原sha256:域，Evidence/Policy仍原裸64hex，不混域。下一在新proposal模块实现同事务source request事实读取：SERIALIZABLE/aos_runtime/Scope一致；current PG Owner FOR SHARE；当前installation FOR SHARE；neutral initialization lock共享；原Store frozen build provenance及原Receipt/hash、coverage/freshness/撤销状态；原verified signed Policy全元组。结果仅SOURCE_REQUEST_FACTS_ONLY_NO_START，不写issuance/head/Approval。
通过现有full signed schema test的新增opt-in AOS_B88_SOURCE_REQUEST_TEST hook调用新测试helper；该helper仅一次性DB，使用原Store真正build原始EvidenceBundle，不用b83管理员假issuance来冒充许可源。Owner仅测试DBfixture，声明test-only，未验证外部JWT或正式issuer供给。该接续是typedproducer必要实证，b88 Task仍须后续原Proposal/独立批准才DONE。

## 2026-10-05 原审批接线补充：metadata / 批准写者保留
新增 a0v_140_source_license_action_metadata.py（down139）及 tests/aip/test_source_license_action_metadata_pg.py，另登记Task/Lease。原meta_object_type增加 SourceLicenseRequest（仅原Proposal内拟议声明的类型元数据，无新对象/审批/许可表），meta_action_type增加固定 aip_issue_source_license、名称申请精确来源许可、空参数/markings/criteria，前端/通用编辑继续拒。metadata exact冲突即拒不覆写；受原表owner只读冻结trigger保护普通runtime raw INSERT/UPDATE/DELETE。
保留独立 aos_source_license_approval_issuer，NOLOGIN/NOINHERIT/无高权/无成员，不授runtime成员、不供给凭据、不授业务写权。原approval_event新增invoker保护：若原proposal ID或snapshot任一匹配source action，仅完全匹配独立session/current角色及exact scope可写。当前NOLOGIN且无ACL故正常来源批准继续关闭；其他原动作原样。后续单独ACL/connection与typed checker Task才可以正向批准，不能借guard/network/BI/Registry角色。
此迁移不改历史Proposal/Approval、来源/hash、任何业务数据；缺角色允许新建NOLOGIN，既有危险attrs/members拒不repair。downgrade fail closed；真实135库不迁移。本补充先真实PG metadata缺失/身份缺失RED，再准确元数据、普通role修改拒绝、危险role/membership校验、PUBLIC/业务写零权限GREEN。仅前置，不等同b88 Delivery。

## typed maker 接线（仍未checker）
原aip_action_store.py增加exact SourceLicenseProposalGuard参数，只接受具体类；通用来源身份guard缺失仍拒，checker不能借maker guard。新proposal模块服务 propose_source_license_in_transaction 接收实际原生psycopg调用者SERIAL事务与已认证OIDC Principal；不公开HTTP，不接受client factory/callback，不自行commit。构造原TransactionBoundConnectFactory后guard固定绑定其同一个连接对象，原Store只使用该对象，所有事实读使用同一原生连接；避免现有窄proxy无info导致scope事实校验失效，不读取HostTransaction私有连接。
固定metadata必须与a140两条原metadata行一致且共享锁；请求绑定全部grant+scope+maker，原Core写Proposal/immutable draft/event/request hash。返回前DB live clock检查expiry，响应在外层唯一commit之前构造；maker replay仅同原请求/原hash且源和Owner仍当前，不新审批。测试在真实signed active/source事实验收中调用private maker service，Principal为隔离内部OIDC-context fixture（未验证外部JWT），不得称正式身份供给。先添加maker模块函数缺失RED，再实现同原PG真实Proposal/replay与0审批/0issuance；完整b88仍需真正独立signed checker及最小ACL后才能Delivery。

## 审批边界实际反例及最小修复
RLS隐藏Source Proposal没有形成成功写入：原a0v118 guard对所有不可见Proposal已fail closed。测试cleanup缺finally已修为unique policy+finally，不新增全局读取definer/额外角色。
真实RED：runtime能将来源Proposal ID与snapshot ID同时改成ordinary（1failed/19passed/24.47s）。a140仅对OLD/NEW任一来源身份冻结非生命周期字段，以to_jsonb差分排除status/version/updated_at；拒SOURCE_LICENSE_PROPOSAL_TERMS_IMMUTABLE。来源请求变更须新Proposal/new key，不能换标签走普通批准。Owner撤回、expiry与checker状态/CAS仍允许，其他动作不干预。先RED再GREEN及原审批/执行累计。


## 独立checker / a141最小ACL执行方案（2026-10-05）
新增文件：services/aos-api/alembic/versions/a0v_141_source_license_approval_acl.py；services/aos-api/aos_api/aip_license_source_approval.py；services/aos-api/tests/aip/test_source_license_approval_pg.py。原root Lease内修改proposal.py与ActionStore，原hook Lease内更新signed helper。
a141保持来源批准角色NOLOGIN/NOINHERIT/无任何成员/高权；未来实际LOGIN须独立正式供给。仅对原来源Proposal及关联draft/event授审批ACL，RLS exact双租户+固定Source身份。来源和Registry只读；Owner/安装/metadata共享锁所需UPDATE(subject/installation_id/id)以独立invoker触发器禁止此issuer实际DML。无新全局definer/无runtime成员/无issuance/head/RegistryReceipt写权。Proposal仅status/version/updated_at；draft仅status/updated_at；原approval_event和action_event仅INSERT。DB拒runtime把drafted直接变approved/rejected；源approve事件须original version/hash/action binding/policy/独立actor、当前Owner、有效窗、checker.1；原draft/event新ACL不能写其他动作或其他scope。
checker exact typed并绑定原native+TransactionBoundConnectFactory，同一SERIAL事务；读取原Proposal/immutable draft/metadata及原请求完整绑定，当前maker与checker都Owner、独立actor、未withdraw/expiry、安装与初始化共享锁、原build+Receipt与真实signedPolicy再次验证。保留原Store decide/CAS/idempotency/event算法；只返回真实当前角色owner，不信JWT roles/body。严格核验独立session=current角色及LOGIN/NOINHERIT/无成员/高权。原请求事实增加仅此正式角色的核验分支，runtime路径保留。
先PG/typed guard缺失RED，再metadata ACL、普通身份拒、当前Owner/条款/hash/expiry/replay和真实signed schema正向；隔离测试角色必须最终恢复NOLOGIN且只清本轮新角色。生产JWTadapter与exactcredential connection仍为完整b88必做项，未完成不可Delivery。提交前复审相邻原动作无回归；当前135真库不迁移不执行。


## b88 身份与连接adapter补充
在原proposal_contracts.py增加SourceLicenseMakerCommand/SourceLicenseApprovalCommand，SecretStr bearer、exact scope/key与原Decision DTO；approval.py增加外部OIDC adapter及独立SourceApprovalDatabaseConfig/connect_source_approval。复用原resolve_principal与共享external-only配置校验，不借network issuer身份/权限/命令。每次先重新解析合同与校验实际JWT签名/issuer/audience/expiry/tenant再打开独立连接；不收actor/roles/callback。连接固定来源批准角色、localhost精确数据库/私密0700目录0600 passfile、SERIAL/固定timeouts、自身RLS身份、无高权成员。保留原native caller-owned txn及唯一commit，异常rollback，不自动重试/重发。实际生产IdP/credential供给仍需正式授权；隔离测试RSA签名/JWKS字节+真实专用PG登录只是adapter验收，不构成生产身份供给。
真实签名链r1因installation row-lock policy仅SELECT产生drift拒；已仅对读锁两表补exactscope ALL policy，同时DML触发器仍禁写。r2原事件已返回但测试错误取actor_id导致rollback；修为原ActorRef，不修改生产DTO。

实证RED：原row字段正常但原immutable draft目的不同、两处hash一致的对抗记录仍可批准，1failed/17.23s。checker复用原Core._proposal_stable完整信封构造并适配原direct创建无sourceDraftRef字段，逐字段对账原draft；另核验原request_hash、action revision hash和draft policy/diff/evidence。此为原真源算法复用，不复制hash或审批算法。

审批回放新增实际RED：另一个当前Owner用相同审批key/body能返回原批准。该返回未新增事件，但不应被误读为新actor批准；1failed/19.02s。checker对已批准行再对账唯一原approved事件、原actor/checker.1/原version+1/hash/policy/binding/eligibility和live DB expiry，拒不同actor或失效证据。进一步验当前maker/checker角色撤回、跨tenant读取0及四真实PID竞争，仍不发行许可。

来源生命周期重置RED已确认：已批准原Proposal可被改回drafted（1failed），可能复活旧拒绝状态。a141只收原Source合法路径：drafted→approved/rejected/withdrawn/expired、approved→withdrawn/expired；原draft同步路径与原Proposal状态/hash绑定。已结束状态不复活；现有普通动作不干预。合法Owner原Store.withdraw与真实等待DB expiry均验证批准0，四PID竞争写者全部rollback。

最终ACL复审RED：issuer UPDATE(id)锁权限对普通metadata仍可实际UPDATE，2failed；扩展同一read-lock-only触发器到四个读锁表（Owner、安装、object/action metadata），全源metadata及普通metadata都拒此issuer实际DML。加入整个public列权限清单验收，仅9个预定UPDATE列，不授其他写权。

专用连接schema接续RED：临时schema优先的search_path仍能通过审批（1failed/18.27s），未证明临时表成功越权，属于明确身份/解析范围漂移。专用连接固定pg_catalog,public,pg_temp；每次checker身份复核精确path、scope与pg_catalog角色目录，拒漂移不repair。maker在exact类型校验后固定事务内同一路径；当前真库与其他普通服务路径不改。初次累计因三个文件名漏aip前缀退出4，无测试执行，不计GREEN；已用真实文件路径重新运行。
