# BudgetPolicy 续期真实身份、审核、低权消费完整实施方案

## 0. Rules、事实与退出条件
采用用户AGENTS、231完整Goal、AOS工程交付、唯一m1writer、原org-org/dev-project、原650表只读、Host/worker/Provider OFF。Authority AOS-002024，m1 78f3fb6f284431fdbd694fd6217d4ff69e91a549；API生产代码2d1cb0589仍最新。当前任务仅方案，不允许编码、迁移、改角色/ACL/服务或真人代签。原BudgetPolicyRenewalProposal和Preflight已交付，不重做；旧预检timeout r2不重发。

本方案整体退出不是合同或mock通过：需机器认证提案→原真人真实OIDC审阅并决定→独立发布者原锁内重新核current refs/CAS→原AIP策略authority新revision+唯一Receipt→未知只读对账→Model/runtime配置消费者继续按各自current门判断。隔离实现GREEN只是代码候选交付，真实原卷部署/机器身份登记/原真人批准未证明时保留待验。完整自然CaseRun、安装生命周期、八场景/Wiki/观察发布Goal不缩小；本方案不授任何真实源、Provider或外部动作。

## 1. 原Owner与必须保留的门
1. 原canonical BudgetRevision1有效至2027；同一预算policy当前head为13，lifecycle active但窗口已过。续期原policy id、revision14、expected head version从Owner读取，不新建替代policy、重置revision或修改BudgetRevision。
2. 原AipModelGovernancePolicyStore.publish_budget对ACTIVE输入无条件BudgetPolicyApprovalRequired；原接口/错误/一般写权限必须保持。新有界发布为原AIP authority的专门审核消费入口，不能删原guard或给通用连接table UPDATE。
3. 原Proposal保证sourceACTIVE/targetDRAFT、同Owner/policyId/budgetRef、revision+1、Provider/model不换、maker!=checker、不得借source历史approval/zero-price。其字符串并非身份或批准。本次不修改该合同的既有行为。
4. 原Preflight.inquire要求maker/checker人类OIDC/member，返回activationEligible=false/approvalVerified=false。机器maker不能用构造Principal或加admin membership调用这个人类预检；新机器生产者走真实服务身份，复用原纯hash/model验证函数与Owner事实，不将旧preflight扩权为批准。
5. 原Model依赖校验要求current BudgetPolicy、Budget、Provider/model及DevelopmentCostAuthorization精确范围；若ModelPriceSnapshot的developmentCostAuthorization与新policy不一致，原门继续拒绝。不得在预算续期后声称模型可用；价格/模型绑定的当前引用和必要同批准范围更新须独立登记，不伪造报价或价格为0。

## 2. 身份与可信边界
### 2.1 机器maker
独立服务DB登录角色aos_budget_renewal_maker_call，NOINHERIT、无SUPER/BYPASS/CREATE/REPLICATION，无任何角色成员关系；迁移默认NOLOGIN，无秘密或默认启用。正式启用须受控登记真实服务身份/凭据/进程来源，私有文件0700/0600，禁入通用API库身份、SET ROLE替身或用户JWT作maker。机器subject由可信函数根据实际session_user确定为固定服务标识，不能取请求makerSubject。机器不是第二真人，不给它meta_membership admin，不把已有其他管理员当checker。
机器只可EXECUTE bounded propose/reconcile功能，不能直接写表/审核/publish；typed proposal中的maker_subject必须与数据库认证派生服务subject一致。精确角色/函数ACL/禁止成员关系/profile漂移检查在每次进入事务时执行。

### 2.2 唯一真人checker
使用用户已经批准的原本机管理OIDC配置和真实subject，仍由原JWT resolver核签名/issuer/audience/exp/租户与当前membership。服务端ProtectedCheckerBinding固定这个真人subject和原配置摘要，不能从请求指定checker或从其他三成员选替身；原真实配置和绑定尚未在独立审核服务部署前保持不可用。
不修改aip_network_issuer_auth._require_external_oidc_config，不给旧external-only budget流程增加localhost fallback。续期新增独立明确的local-approved checker适配器，复用原load_management_oidc_config的严格路径/权限/精确loopback合同及原resolve_principal；服务启动必须验证绑定与配置摘要，配置/身份来源不明确就拒绝。配置不含用户密码副本，JWT仅内存SecretStr，不写日志/Receipt/命令参数/环境。核验不能仅信构造Principal对象或由调用方声明token_kind。
独立issuer登录角色仅可执行决定/撤销/对账功能；可信private gateway每次再核真人JWT，数据库信任该独立issuer边界但不能信公共请求actor字符串。数据库调用者凭据和gateway属于明确TCB：共享通用连接、任意SQL入口或凭据泄漏不计正式可用。原只读管理API的POST405保持。

### 2.3 发布与审阅不混用
独立consumer_call仅EXECUTE consume/reconcile，不能proposal或decide；三个caller默认NOLOGIN，不互相授role。SECURITY DEFINER函数由对应NOLOGIN无特权owner持有，search_path=pg_catalog、全qualified、REVOKE PUBLIC；角色、函数体hash、ACL、RLS/tenant/profile必须受启动与每调用检查。Prime只读PASS不是真人Decision或执行许可。

## 3. 服务端持久化与具体操作合同
新增三张AIP-owned ledger表：aip_budget_policy_renewal_proposal、aip_budget_policy_renewal_decision、aip_budget_policy_renewal_receipt。原policy/head/revision仍唯一BudgetPolicy authority，ledger只记录提案、真实审核和消费；不用BudgetRevision初始activation表，不复制Policy事实owner。
proposal：固定tenant、proposalId、机器subject、唯一checker、原sourcePolicy exact+headVersion、原Budget/Provider/model exact、目标draft canonical hash、active materialization hash、未来approval slot、限定窗口、idempotency key/request hash、server clock、状态/版本。数据库仅由machine function写入，原Owner scoped读取source payload并再算canonical hash；draft approval_ref是未来slot标识，明确approvalVerified=false，不因字符串存在点亮批准。
decision：proposalId/hash、targetActiveHash、issuer authenticated subject、approved/rejected/revoked、original issuer request hash/Receipt、decision id（与proposal未来approval slot匹配）、时间/期限、reason元数据。仅独立issuer可写，审核操作不可更改target body；拒绝/撤销不准消费，重复同key同hash返回原Receipt，不同hash conflict。
receipt：proposal+decision+consumer request hash、原policy id/newrevision/content hash/head CAS结果、publication time、exact returned ref。和policy INSERT/head UPDATE同一事务提交，immutable，唯一tenant/operation/key。可读历史Receipt不授新执行。

操作：
A prepare/propose：机器实际身份→同scope原heads/完整模型/hash→current Budget active/hardStop/unknown block/币种/窗口，Provider current active/hash/model scope→原policy owner/current head/hash/lifecycle，允许历史source窗口过期但不允许suspended/revoked/hash漂移→构造受限targetDRAFT→仅proposal及Receipt。目标除了窗口、revision、未来approval slot及对应DevelopmentCostAuthorization窗口/approval slot之外逐字段与source保持，不增加费用/范围/Provider/model/zero-price，任意其他更改拒绝并另新方案。有效窗口由真实待审请求输入，必须有时区、在Budget窗口内、晚于source窗口结束；不替用户批准默认时长。
B decide：唯一真人JWT→current member+CheckerBinding→proposal exact目标及source current head/Budget/Provider均复核→明确操作approved/rejected。只审批UI/请求中逐项展示的targetActiveHash及具体窗口，不接收修改目标的decision请求。机器subject与human subject必不同。撤销写immutable决策版本，消费以current decision且无后继撤销为准。
C consume：固定锁顺序proposal advisory→proposal row→decision/current revocation rows→source policy head→Budget head/revision→Provider head/revision→权限/member。使用read committed、短事务、lock_timeout/statement_timeout，最后一次clock_timestamp检查再进行原canonical policy/head/Receipt原子写。sourcecurrent headVersion/hash/lifecycle、Budget/Provider current exact与有效窗口、真人Decision/issuerReceipt完整重算与权限、targetdraft严格再parse、activebody/hash/approval slot一一对应；target revision source+1，CAS UPDATE头version/current_revision，rowcount必须1，否则整体rollback。immutable源/目标/receipt/hash任何漂移失败关闭。角色之外禁止任何DDL、源props读、网络/Provider调用、Schedule/Runtime激活。
同事务重算DevelopmentCostAuthorization，目标和授权窗口/approval slot完全一致；原其他金融字段原样。通过原materialize_policy与原canonical_hash合同对账，不写第二policy表。新增active发布函数仅接受可信已持久化/未撤销Decision，通用Store仍拒绝ACTIVE。
D reconcile：READ ONLY历史对账，精确actor/tenant/proposal/hash/decision/request key；已存在Receipt+canonical历史revision证明返回observed，不以当前head已推进否认历史结果，也不授permission；无结果返回unresolved，错hash/ref/多义返回conflict。不能把unresolved/timeout当无写入而重发；lost commit ack只能读，不换key/重造proposal。

## 4. IPC与浏览器/部署
独立脚本只用受保护配置文件指定专用角色连接，不从共享API DSN/环境凭据fallback；stdin一请求，bounded JSON schema，private Unix/loopback通道，单次写前durable AttemptReceipt，工具未知永不自动重发，stdout只metadata结果、stderr脱敏，父级deadline与原进程真实终态回读，原支持attempt机制复用但新的namespace不借旧记录。
新增BudgetPolicyRenewalReviewPanel及专用client，在现有s2预算页面独立节显示source13已过期/Budget1有效、机器身份来源、唯一真人身份、目标14的全部scope/窗口/新approval slot、unknown状态及原Receipt。现有BudgetRevisionSetup/Activation/Cost panel和流程不改变。服务未部署/角色NOLOGIN/身份未绑定时真实不可用，不mock成功。唯一真人审核只走受支持真实登录界面；工具不得代签、借安装批准或把聊天“继续”变成金额/窗口批准。
browser部署与UI路由需后续精确Task：原Web同origin专用proxy到private gateway，原tenant client标准headers在应用内部传递JWT，不让工具导出/复制token。原只读API禁止写保持；独立gateway写入通道启用须有明确真实部署授权，当前原卷READONLY状态不改变。先交付具体待审proposal，真实人的最后动作才是批准；没有实际通过不得claimApproved。

## 5. 文件级范围与分波
A（可信身份与持久化，独立codingTask登记后RED）：
- services/aos-api/aos_api/aip_budget_policy_renewal_contracts.py：机器入口、决定、Receipt typed contracts和严格hash；复用原Proposal/原BudgetPolicy模型。
- services/aos-api/aos_api/aip_budget_policy_renewal_identity.py：机器session profile与原真人OIDC CheckerBinding，不改generic auth/旧issuer。
- services/aos-api/aos_api/aip_budget_policy_renewal_store.py：原Owner读取/新ledger并发幂等，原canonical materialize/hash。
- services/aos-api/aos_api/aip_budget_policy_renewal_authority.sql：限定propose/decide/revoke/consume/reconcile函数/ACL，不dynamic schema/function或请求SQL。
- services/aos-api/alembic/versions/a0v_162_budget_policy_renewal.py：down161，仅隔离部署先验；若开工HEAD迁移已被别的正式任务推进，重新检查并改编号后新review，不建立并行head。三新ledger RLS FORCE；清理新表PUBLIC/runtime默认广权并验证exactgrants；原table仅对独立owner最小列/INSERT/headCAS权限，不给callers直接DML。所有caller默认NOLOGIN。downgrade禁止破坏已有历史Receipt；runtime rollback关闭caller入口，保留历史。
- services/aos-api/tests/aip/test_budget_policy_renewal_contracts.py、test_budget_policy_renewal_identity.py、test_budget_policy_renewal_pg.py：测试fixture仅隔离真实PG，禁止mock当真人或正式部署证据。
B（issuer/consumer端到端）：新增aip_budget_policy_renewal_service.py、aip_budget_policy_renewal_connection.py、aip_budget_policy_renewal_process.py、aip_budget_policy_renewal_schema.json，以及对应test_budget_policy_renewal_service.py/connection.py/process.py；原attempt Receipt和auth resolver复用，库identity profile再核。不修改用户dirty的aip_action_*、aip_budget_cost_runtime或capacity files。该波之后应有真实隔离PG完整非空propose→authenticated isolated actor→decide→consume→reconcile→currentread和负例，并明确不是原库真人验收。
C（真实入口与页面）：新增scripts/a0v_qyh_budget_policy_renewal.py、apps/web/src/api/aipBudgetPolicyRenewal.ts、apps/web/src/pages/s2/BudgetPolicyRenewalReviewPanel.tsx及其test；现有接入文件待原预算页面路由审计后精确列名再登记/复审，不预授权任何未列名共享文件。Gateway默认closed；完成真实部署配置/实际machine身份/实际真人未确认/令牌过期/unknown/error的验收与原卷只读边界后才讨论有界启用。C所需入口精确Scope未冻结时不得编码C；A/B不冒充整体完成。

## 6. 必须跑的验证矩阵
纯合同：bool/int混淆、未知字段、tenant、source及target/hash/ref/Provider/model/Owner/预算/币种/金融字段变化、source历史approval重复、zero-price、窗口越界、maker=checker拒绝。
真实隔离PG：非空合法链与唯一Receipt；当前源head并发CAS、Budget/Provider变更/撤销/到期、当前member撤销、决定后撤销、expiredtarget、wrongchecker、fakeactor字符串、通用API登录/SETROLE/额外membership/profile漂移、PUBLIC/column grants/RLS/cross-tenant拒绝；genericACTIVEpublish继续原422；rollback无半发布，commit ack丢失后只read，不重复写；重复同key同hash原Receipt、错hash conflict；newhead后历史reconcile依然准确；ROLE NOLOGIN默认保留。仅schema管理员用于隔离setup，不作为数据owner/actor正常通过证据。
IPC：写Attempt未知/部分文件/超时、真实进程句柄对账、伪造stdout/额外key/schema、issuer配置变更/过期JWT/错误issuer/audience/tenant拒绝。existing genericexternal-onlyauth tests原样通过，不把localhost普遍解封。
C browser：实际唯一真人登录、真实服务不可用/closed门、source expired/Budget有效分别显示、全部proposal字段/hash/窗口可审阅，未同意不出Decision、拒绝/撤销/unknown readonly对账无再提交；现有预算页面不回归。不得以UI按钮可点或tests当预算正式生效/经营首链。

## 7. 并列当前source准备缺口
原selected安装ab2fd72f-d81c-400d-bbbc-e1589a159d6b ACTIVE5及真实签名lock可读，不等configuration/gen/epoch合法。当前source selection/control/schedulebinding/definition exact0，所需strategy.plan.r2 binding0；原65ScheduleRun含12running，disabled12不启用。准备应逐项从Owner读取真实installation/configuration/package/sourceConfiguration/graph/hash/mapping/schema/mask/limit/generation/executionepoch；没有批准的binding/config/generation/epoch则列missing而非编UUID。existing compile_source_selection_candidate只在完整current输入成立时构造唯一fixedsnapshotdraft，不审批/持久化/sourcefetch。配置/预算/Price/InstanceToolBinding/currentHealth与新自然producer各门独立，后续sourceSelection→runtimeControl→scheduleDefinition新的自然触发再逐波受审。run_current*有trusted执行callback，不能作为只读探测调用。

## 8. 风险和交付门
身份TCB、权限登记、真实checker动作、迁移部署、ModelPrice/RuntimePolicy依赖更新仍需逐项实际证据。PlanPASS只允许对应已冻结codingTask，不授真实DML或预算批准。本Task完整方案与独立review交付后，立即登记A具体codingScope开始RED；B/C实际进展和未验项持续列账。每日aos最新m1/原命名卷完整重启不由本机制API-only替代，aos2不重启。原用户dirty/历史/650表不覆盖，当前不push、不发布、不读商城源、不运行Provider。

## 9. 自洽复核补充：锁、TCB与后继依赖
- propose/decide/revoke/consume全部取得同一tenant+proposal advisory lock，且决定/撤销和消费按相同proposal→decision→sourceHead→BudgetHead→ProviderHead→member锁序；禁止只有consumer加锁导致撤销phantom。原head CAS与actor绑定改变都失败关闭。写后/提交前再次核clock/window；Receipt只是策略发布事实，不是一张未来可复用执行permit，Runtime/Price/currentHealth在真正使用时另重新核。
- 人类OIDC认证和DB issuer调用者是明确TCB，SQL并非能自行验任何JWT：不能宣称掌握issuer凭据的任意直接SQL者也无法伪造人类决定。凭据只能在已验证/钉定private issuer进程，公共API无issuer连接入口；fakeactor负例针对不受信调用方和机器/consumer越权，不把TCB compromise算已被解决。未受控部署TCB保持activationEligible=false，运行不能开放。
- ProtectedCheckerBinding不从请求传入，机器proposal函数不授任意checker选择；独立issuer每次用原resolver重新验唯一subject+issuer/audience/JWKS/tenant，并核proposal checker与protected pin一致。修改binding/private源或新增真人均是新的真实授权变更，本波不自动做。不存在实际service身份时提出machine profile待部署，不构造假Principal满足旧人类preflight。
- publication owner所需FORCE RLS可见性必须在隔离测试核实；若旧canonical表RLS仅授权aos_runtime，新增只针对具体NoLOGIN owner的严格tenant政策并列于迁移审阅，不给owner/calleraos_runtime membership，不删除/放宽旧政策、不使用BYPASS。角色/profile/函数签名/column ACL/RLS白名单都在startup与entry核实。未明确任何既有表RLS/ACL影响前，不执行新迁移。
- 当前ModelPriceSnapshot如绑定旧developmentCostAuthorization，批准BudgetPolicy新窗口不会自动批准价格/模型引用更新；需要当前price/model精确依赖对账，保持原一致性拒绝门。该更新后继另明确同批准范围和独立Task，不能为本波PASS删除comparison或克隆价格事实。BudgetPolicy scopedReceipt交付不当成ProviderReady或自然首链完成。
