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
