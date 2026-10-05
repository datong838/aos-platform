# 完整评估命令的原消费者接线清单

2026-10-05，基线code461a84f8/Authority1334。沿完整Task ACTIVE；本清单补充主plan，不改变退出定义或授权当前142写入。

1. native evaluator实际SCRAM/SERIAL同caller事务，严格schema1与原signed Principal；Body不供给actor/roles/clock/facts。原幂等锁、原Receipt、Binding expectedVersion和实际scope先校验，不内部commit或retry。
2. 无效力发现Source原Proposal/Approval及Budget原activation/Proposal、全部Owner集合和Route全部候选；SourceProposal/Approval按ID排序预锁，原Budget advisory先预取，再合并Owner排序锁；Installation及Source init/head、Registry协调及signed request读取按原序，发现值须重核验。
3. 原TransactionBoundConnectFactory(HostTransaction(native),scope)只给原读者复用，不能以该wrapper代替native身份门；commit为noop、rollback拒绝，完整命令异常须向外传播让caller rollback。原ModelRuntime._get只返回payload，不证明row/hash/current head；须先排序共享锁全部provider_instance/registered_model/runtime_policy/model_route/model_price_snapshot heads并核验原行/hash/tenant/current/active。
4. 原Resolver AipModelRuntimeResolver.resolve保留候选阻塞累积语义；所有候选的实际Model/Provider/Price/Governance/Health依赖必须保护，选中结果与请求model/provider/price/route/policy exact refs逐项相同。禁止替换为自造选择器或仅锁最终Provider。Health用原provider-id fence；最新观测严格exact/ref/DBtime，无旧healthy回退。
5. 原BudgetPolicyRevision先原治理head共享锁/current active/hash/window，再取其BudgetRevision ref调用已验read_formal_budget_fact；model及runtime policy的Budget/Quota引用一致，实际原风险批准/Receipt/Price/Provider必须吻合。联合锁序尚须与所有治理激活writer继续对照。
6. Route/Model Eval各沿AipEvalAuthorityStore.require_exact_passed(expected_target=evaluation_candidate_ref(original DTO),now=DBtime)；不发明Evalhead、不把单status当通过。EvalContract原aip_eval_contract_revision必须frozen/exact。Capacity沿原pool head FOR UPDATE及原有效占用算法只判余一个原量子，不reserve/expire/consume。
7. 发布Capability及原required Data/Tool exact refs由实际Registry/EvalDataset/Evidence原authority核验；Source消费已签名安装和当前两Owner、原用途、来源签发Receipt及grant/批准/证据的最小期限。完整facts含八键及Source/Budget/Installation/Owners，实际DB最后时间与全部期限最小值。
8. 原Binding CAS version+1、原capability_binding.evaluate Receipt、原evaluation proof在同caller顶层事务直接写三行，不分SAVEPOINT。沿a144三个DEFERRABLE guard由actual COMMIT核验xmin/hash/时效/安装；禁止把SET CONSTRAINTS或rollback control当正向。原legacy snapshot hash与facts SQLcanonical hash用途不同，不复制hash权威。
9. 同key replay仍要重核当前依赖与proof期限，不能返回过期available；错误/并发/到期/commit失败三写全回滚。产品Service/router正式分支必须使用原signed身份和独立private evaluator配置，原preview兼容边界保留。

整体验收：原正式Store全signed安装与Source+HTTPS预算配置、真实非空八facts、实际native同事务三写COMMIT、samekey replay/冲突、各依赖缺失/撤回/漂移/竞争/到期/canary、产品API真实入口；不能用helper通过替代。当前已验Health/Source/Budget只降低组合实现风险，完整entry仍缺失。无Provider调用、商城源、旧Run或当前142迁移授权。

## 联合预锁复用实施

原read_formal_license_source_facts把发现和Proposal/Approval预锁、Owner锁连在一起；完整command若先调用该函数再首次Budget advisory会逆序。最小提取_private _prepare_formal_source_approvals，native admission+strict exact unique refs，原discovery/authorization/approvedRef/maker及全部Proposal→Approval/withdrawal校验逐语句保持，返回discovered+approvals，不取得Owner/Installation/Source锁，不产生权利。原Source reader保留私有安装/loader/release context校验，调用此helper后沿原Owner后续逻辑。完整command可先调用它，再原Budget advisory及合并Owner锁，后调用原正式Source reader重核。禁止fake Maker/回调/客户端锁开关；不完成整波。实际signed Source hook先调用新prelock helper核对原Owner集合/Approval证据，再原Source正向/负例/真实writer阻塞全复验。

## 实际签名来源与预算联合输入验收准备

2026-10-05，Authority1337/code a2f63331；沿完整实施Task及其18:00 Lease。路线独立审阅已消费，完整命令和自然首链仍未完成。本段不是新的helper交付，不改运行时逻辑。

文件仅三个既登记测试文件：tests/aip/test_binding_formal_evaluator_pg.py、tests/aip/test_aip_license_source_proposal_pg.py、tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py。签名安装原测试增加显式AOS_B90_JOINT_INPUT_TEST入口；原来源验收返回其实际原请求，默认原断言不变；按需获取原预算consumer/issuer/HTTPS签名fixture，在原Store完成预算批准、激活及价格/治理配置。禁止price_for触发器关闭路径、假Principal、伪造回执或callback权威。

先缺联合断言入口形成RED，再在测试函数中按原Source预锁→Budget advisory→两侧成员去重排序FOR SHARE→原正式Source读取→原Budget事实读取组合。同一真实SCRAM evaluator连接、同一顶层事务；核对来源与预算原审批身份、Receipt/Decision及DB时钟；前后三项业务行数、预算fence版本及占用不变。成功后仍只证明联合输入准备，不代表八facts或三写正向COMMIT。该数据必须在后续完整命令实测复用，不允许将此结果改名为整体GREEN。

风险：pytest fixture须在全schema隔离库设置后才按需启动；Source隔离OIDC上下文退出后再启动预算HTTPS fixture；临时LOGIN无论测试失败都恢复NOLOGIN。完整签名fixture独立测试会话，不能与新增安装的其他测试混跑。没有UI变化，浏览器不适用。

## Budget联合预锁复用

沿完整Task提取_private _prepare_formal_budget_approval：native事务门及strict BudgetRevision，原unique activation/advisory/重核/Proposal/view/DevelopmentRisk原块保持，返回receipt/row/p，不取得成员/fence/head锁。原正式读取再核成员及全部内容；完整command可先Source Proposal/Approval再Budget advisory、合并成员锁后读取全部facts。本提取不能完成整体任务。

## 15:55 Capacity / Budget 实际写者逆序补正

当前 code ea110644 / Authority1339。原 ContentBudgetCommandOwner._prepare_sources 在同一 HostTransaction 中锁原 Capacity pool head/revision FOR SHARE（before_capacity 分支亦然），随后 _build_command → _approved_bound → require_cost_risk 锁 Budget cost fence FOR UPDATE 并保持原 version 写语义。因此第5/6项中隐含的 Budget fence → Capacity head FOR UPDATE 顺序撤销，不能作为完整命令施工序。原业务 writer 不修改。

完整命令先原 Source Proposal/Approval → Budget advisory → 合并成员共享锁 → Installation/Source/Registry，再取得请求精确 Capacity pool head FOR UPDATE，随后 Budget fence/head、ModelRuntime/治理共享 heads、Eval/Health 和容量实际占用核验。Capacity 预锁仅协调原 pool；不得 reserve/expire/consume，也不能以取得 head 宣称池内容、八配置或业务权利合格。锁后必须以原 CapacityAuthorityStore.get 核验 immutable revision/hash/lifecycle/route-model-provider exact refs；占用沿原 reserved/consumed 且 expires_at>DBtime COUNT/SUM，保留一个原量子。多个资源必须稳定排序，锁序仍须与全部原 writer 逐一复审。

必要隔离反例：使用原 HTTPS 成本批准/激活/配置链取得真实 Budget 输入；另由一次性隔离 owner 创建仅用于协调探针的 Capacity head，不提供 fake READY/revision/proof。原预算 require_cost_risk 作为 writer 后半段；测试先持 Capacity SHARE，再调用它。旧顺序 evaluator 先真实 read_formal_budget_fact 持 Budget SHARE 再 Capacity UPDATE，读回双方 pg_blocking_pids 并由原 PostgreSQL 检出死锁；新顺序通过 evaluator 私有 Capacity head 预锁，让原 writer 在 Capacity 处等待，evaluator 能继续原 Budget 验证。两端 rollback，前后 Budget fence、六业务表计数与探针 head 不变。探针只证明锁图及 native ACL，不是实际正式 Capacity 正向或完整命令通过。

文件：services/aos-api/aos_api/aip_binding_formal_evaluator.py 的私有 native Capacity head 预锁；services/aos-api/tests/aip/test_binding_formal_evaluator_pg.py 的真实预算/容量两事务反例；本方案及 implementation 下日志。完整 Task 继续 ACTIVE；后续全命令必须调用该预锁并用实际正式 Capacity Store fixture 验证，不能把本反例独立交付为 b90 完成。

### 实际互斥边复核及本段验证

原 CapabilityBinding writer 搜索到 service.create/update/evaluate；update 在自身原命令 advisory 后读取旧 Binding 和重新评估，再原 UPDATE 取得 Binding 排他锁；内建 readiness 的治理 head 是共享锁，Source摘要读取不是原Source发行事务。完整命令明确：同 key 原 advisory → 原Receipt校验 → 原Binding行 FOR UPDATE 和版本/生命周期检查 → 原资源预锁 → 同行 CAS；现有内建 writer 的共享治理锁与新共享治理锁兼容，未发现其持 Capacity 排他锁后再更新 Binding 的原入口。自定义 connect/readiness 注入不视作正式原业务路径；完整命令不可接受可替换权威回调。仍须实际竞争验收，源码不存在匹配文本不是锁图完备证明。

ModelEval预算原入口为 ActionProposal UPDATE → 治理Budget head SHARE → Budget head SHARE → buckets排他 → cost fence UPDATE；evaluator不取得 buckets，治理/Budget head SHARE互相兼容，当前没有这条环的依据。原Budget配置/消费为 advisory → 成员 SHARE → Budget head UPDATE/SHARE → Provider/Price SHARE，不取得 Capacity；原Budget issuer为 reviewer SHARE → advisory → 成员 SHARE → fence相关撤回写。成员维护未见同事务请求此budget advisory；不能仅凭成员/advisory文字顺序称死锁。原Capacity reserve为 head UPDATE → reservation UPDATE；terminal只改单reservation，评估不锁reservation行。原Capacity publish只持自身head UPDATE，依赖验证另连接退出后才进入发布事务；原ModelRuntime publish只持自身head UPDATE，依赖普通读取。原Health append经epoch排他协调，无Capacity/Budget/Binding锁。完整评估保留这些共享/排他模式，不擅自扩大为EX。

本段 actual PG RED 10.02秒：旧逆序反例通过、新序缺私有预锁入口失败（ImportError），不是业务正向RED。最小实现后两个并发参数2通过9.40秒；扩展身份、canary、strict model_copy、缺失/旧head六负例，连原正式预算/来源/Health/ACL/连接与合同相邻累计111通过36.59秒。两参 actual pg_blocking_pids、DeadlockDetected及前后六表/fence/head在capacity-budget-lock-*.json。py_compile和精确diff whitespace检查通过。完整Source签名安装联合波此前证据不被本段替代。实际正式Capacity内容/全命令/三写COMMIT/API仍待实施；本段不完成完整Task、不提升last GREEN gate。

## 完整命令实施合同（code b1d64cc8 / Authority1340）

入口固定为 evaluate_binding_in_transaction(conn,scope,binding_id,request,principal,*,idempotency_key,loader,release_policy)。loader/ReleasePolicy只由server私有配置提供，原类型检查不能被回调代替；API body没有这些字段。先重新解析完整strict request，要求实际native evaluator/SCRAM/SERIAL、原resolve_principal得到OIDC主体同tenant、canonical binding/key/subject；原aip6 advisory和Receipt校验，Binding原行FOR UPDATE，缺行/撤回/版本冲突拒绝。请求hash复用原Registry canonical hash并绑定bindingId、actor和domain，禁止跨binding同key重放。原CapabilityCatalog经aip6_004 append-only UPDATE/DELETE/TRUNCATE触发器保护，原publish只INSERT，不扩大锁列UPDATE权；使用原AipCapabilityRegistry exact读者及原required Data/Tool覆盖验证。

无权发现请求BudgetPolicy的原BudgetRevision；原Source Proposal/Approval prep→原Budget advisory prep→Source两Owner、Budget两成员和API actor合并排序共享锁，所有当前角色由DB核验。原signed Source与安装消费后先Capacity预锁，再原Budget fact，再按类型/id排序保护五类ModelRuntime heads和全部候选原治理/Guard/Network heads。发现的DTO在锁后由原Store重读并与current head/tenant/hash/lifecycle核验，不将无锁getter当权威。原Resolver保留原选择语义；每个Provider原Health epoch保护，最新exact/time由已验reader核验，选中Healthy与请求一致。Route/Model分别原require_exact_passed及original candidate ref；原EvalContract Store读取frozen/current exact，在其head共享锁下保护。Capacity由原Store/materialize核验hash、active、route/model/provider和原COUNT/SUM有效占用，不reserve。

事实包含八键+Source/Budget/Installation/Owners及实际引用/原Receipt/decision/fence；不写Secret字段、不写任意raw业务payload。最终DB时钟和全部Source/Budget/Eval/Health/Guard/Network/Governance期限最小值，TTL最大15分钟。旧snapshot hash由原AipBindingReadinessService.snapshot_hash计算，facts hash仅调用原SQL canonical_asset_registry_jsonb+digest。新命令原Binding CAS+原Registry Receipt+proof同native顶层事务三写；函数不commit、不savepoint、不retry，所有异常由caller完整rollback，实际COMMIT仍执行a144三约束。返回原Binding/Readiness/Receipt类型，产品Service/router仅在实际正向/负向/COMMIT验证后接入。

同key回放先校验hash/target/result version/oldproof，重新验证全部当前原资源与期限；fresh事实内容hash必须与旧proof相等，旧有效期仍未到期、Binding当前版本和snapshot匹配才返回原记录，绝不补写、续期或回放过期available。因为此路径不消费费用/容量且事实不包含变化的checked_at，未变资源能回放；预算fence、占用、Owner、安装或Health等变化需要新评估key。actual原库缺完整配置时只能形成拒绝，不能造Gate/Health/READY来凑正向。

本实现先完整entry缺失RED及实际HTTPS OIDC/native事务拒绝矩阵；完整signed八facts正向与真实COMMIT不能由这些拒绝或ImportError代替。新增/修改仍为原登记evaluator/contracts/PG tests/API tests/Service/router/a144及implementation文档；发现额外权限需求先以实际PG失败证明，不盲增ACL。本波无当前库/Provider/自然首链动作，整体Task保持ACTIVE。

### 独立审查修订：Source 代际与授权哈希

Source proof 必须保存原正式读者返回的 epoch、installation_id/etag、owner_authorization_ref、policy_ref 和 source_request_hash，连同既有发行、Receipt、Approval、期限字段由原 SQL canonical/hash 统一计算。只做原事实序列化，不另造许可权威。先在实际 signed Source PG 测试增加原事实字段断言及逐字段变化后的 SQL 哈希差异验证；人工变更副本仅证明哈希敏感性，不代表正式 epoch 更新或完整命令回放验收。完整命令真实回放拒绝、八事实正向及 COMMIT 仍待验证。

### 原 EvalContract 读依赖 ACL 验证

原 get_eval_contract 经 _eval_blockers 读取 aip_eval_suite_revision 与 aip_publication_event；现 a144 清单未含这两表。先实际 native SCRAM 调用原 blocker 读者（不存在的套件/发布引用仅为拒绝夹具，不伪造 frozen/READY），预期原业务 missing blockers，确认是否被权限错误中断。实际确认后，仅将两原 scoped 表加入 SELECT/RLS 清单，复用同租户 restrictive 策略与锁列 DML 拒绝，不授写/锁/启动权；正向缺依赖仍 BLOCKED，canary 空结果和 UPDATE 拒绝须实测。这不证明完整 EvalContract 正向或完整命令验收。

独立复审新增业务合同：current/hash/frozen 只保护合同版本，不能替代原动态 readiness。完整命令须同时要求原 ContractReadiness.READY 且 blockers 为空，任何 missing/revoked/drifted 均在三写前拒绝。原 Publication latest append 的并发撤销尚缺保护闭环：必须回到原权威设计可保留至 COMMIT 的协调机制，不能用一次提前查询代替提交时当前性；此项保留完整 Task 风险，不接正式 Service/API。须原 frozen 合同缺依赖/撤销负例和完整命令三写零增量、撤销竞争证明后验收。

本轮先把既有 EvalContract 读取和拒绝条件原样集中为私有同事务消费者，由完整命令直接调用，禁止可替换判断回调。实际一次性 PG 维护故障夹具使用原 _insert_eval 写 frozen 但不存在 Suite/Publication/Gate；它是负向损坏注入，绝不作为合法 freeze 或 READY 正向。原动态 reader 必须 BLOCKED，正式消费者须拒绝且 Binding/Receipt/proof 无变化。先缺消费者 RED 再最小移动既有读取与拒绝逻辑。此负例不替代完整八事实调用、合法原 freeze、发布撤销竞争或真正 COMMIT 验收。

### 合法 freeze 与 Publication 撤销实测入口

复用原内容预审 Graph、实际确定性 EvalRunner、derive_gate/publish、create/freeze 原合同链（test_ecommerce_content_review_pending_pg._register_current_content_eval_gate），不使用 ReadyStore、不直接写 PASSED 或 frozen。合法内容合同只证明原 EvalContract 依赖生产链，不替代目标 Model/Route 八事实。先 native 消费读取 READY，再持原合同 head SHARE 期间从第二连接调用原 revoke，记录是否可以提交、旧 SERIAL 读者是否仍 READY，最后 fresh native 必须拒绝。三评估业务表全内容不得变化。若发现旧 snapshot 可继续读 READY，则仅作为实际协调缺口反证，不将读者锁宣称提交安全；后续设计覆盖原 publish/revoke/append 路径的最小代际协调。

### Publication 提交当前性修订方案（待实际 RED/实施）

实际原合法 freeze/revoke 反证已成立，不能仅追加 published 行 SHARE：原 revoke 只锁旧 published 行，再插新 revoked 行，旧行版本不变；写者先提交后的旧 SERIAL snapshot 不会因锁旧行自动看到新撤销，Authority append 与直接 INSERT 也可绕过这种锁。

在已登记 a0v_144/evaluator/PG tests 范围内拟加入按 org/project/publication_id 的中性 epoch。它只记录协调代际，原 PublicationEvent 仍是唯一发布状态来源，不 backfill、不复制状态、不授业务启动。独立默认 NOLOGIN/NOINHERIT/无高权/成员0 fence owner，仅管理该中性表和固定 SECURITY DEFINER 函数；固定 evaluator 只可执行共享读锁接口，无 epoch 表读写权、无 published 行 UPDATE 权。函数必须在任何中性初始化前核对固定正向scope/调用身份，canary不得产生中性行。

原事件表 BEFORE INSERT 精确tenant/pub-id初始化及排他协调；AFTER INSERT 才推进代际，实际 ON CONFLICT DO NOTHING 不推进、失败/rollback 不遗留推进。原 UPDATE/DELETE/TRUNCATE append-only 拒绝保留。触发器覆盖原 publish/revoke/Authority.append/raw INSERT，不要求复制或改写原消费者选择逻辑；既有 scoped 原写者不新增业务授权。读者保持原合同 head SHARE，先无权发现原 publication_id，再共享 epoch、原 get_eval_contract 同native重读和 READY/blockers校验；epoch、原精确事件/门引用纳入 Eval facts/hash并持锁至原三写 COMMIT。禁止新增 published 行 SHARE，避免 reader fence→published 与 revoke published UPDATE→fence 的反向等待。

必验：合法原内容 freeze持续可读；读者先持共享fence时原 revoke真实阻塞，读者rollback/commit释放后原撤销提交且fresh拒绝；native SERIAL snapshot建立后原撤销先提交，随后消费者拒绝/40001而非旧READY；原Authority/raw INSERT/ON CONFLICT/rollback、wrongscope/canary、Owner保留身份漂移、最小ACL/RLS与普通原角色相邻。资源锁图及Source/Budget/Capacity/Binding组合仍须核验。此是完整命令内实质时效修复，不创建孤立 helper 完成Task、不提升整体业务GREEN；真正八事实正向/COMMIT/API仍是同完整Task退出。

独立复审要求 Owner 预存在身份门同时拒绝当前目标数据库的业务对象所有权与显式 table/column/schema/function ACL，不能只看角色属性/成员。在另一个5433一次性空测试库分别注入低属性同名Owner的五种授权/所有权，用实际原 migration 子步骤证明其拒绝且原权限保留，finally只DROP该精确测试库、不DROP OWNED/撤权或修改现有对象。迁移前允许跨测试库同名安全角色，但本目标库不得预有身份对象或ACL；不声称全服务器其他数据库授权已审计。

Publication gate 的期限沿原产品语义：原 publish 在发行时校验 gate 当前有效，原 EvalContract 动态读者此后校验不可变历史 gate 的 exact/status/hash及发布 latest 状态，不把 gate 到期自动转换为已发布事件撤销。本 epoch 修订保留该语义，Publication gateRef 是历史发布证据，不授当前执行权；当前运行模型/路线的两项正式 Eval 准入仍由原 require_exact_passed(DB now)和最终 expires min独立强制。当前正式 Source、预算、Price、Health等期限不能借该历史引用放宽。未来若产品要求发布自动到期，须作为独立可审阅生命周期方案，不在本修复隐性改变已有发布功能。
