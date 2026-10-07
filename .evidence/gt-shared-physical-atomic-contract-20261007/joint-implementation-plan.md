# 全物理容量、原预算与唯一 Intent 联合实施计划

基线：m1 28f00da84f583559e94a2330a497f0af7ddf56d2 / AOS-001484，2026-10-08。依231与产品总纲及本目录joint-owner-contract；此文是父Task文件级施工准备，不宣布完整合同冻结，不授正式数据库或发送权限。父Task现有Lease仅覆盖本证据目录，以下产品文件必须另外登记精确Task/Lease；既有到期Scope须原owner对账，不能TTL夺锁。

## 1. 实际入口与不能省略的差异

| 现有入口 | 真实行为 | 联合接线要求 |
|---|---|---|
| occupation Source consumer | actual psycopg/SCRAM/SERIAL/runtime返回当前非执行Source，保留caller事务；返回后过期仍可COMMIT | 沿用原客户端JWT验证与原SQL原事实/签名检查；在joint实际提交阶段检查deadline/currentness；不增加发送许可 |
| pool reserve_pool_in_transaction | exact psycopg caller，旧pool/revision算法、旧TTL仍在 | 仅作为单池约束；同物理账户新ledger保留旧未决义务，不能以旧TTL解除 |
| ordinary reserve_in_transaction | exact psycopg caller，原Task/Price/checker/三预算桶；不结束caller | 直接复用算法，不能复制；借用Host wrapper不满足该native接口 |
| Eval hold | 同SER/runtime caller，原request/checker/预算桶；不结束caller | 与ordinary共享同physicalAccount；一等Eval request不能伪造普通Task |
| HostTransaction | 隐藏底层conn，但execute转发SQL；已有exact trusted Owner委托同conn与enqueue_content_command模式 | 新joint采用exact trusted Owner委托，不公开raw conn；数据库整体提交门必须核齐joint，不能仅隐藏commit() |
| ContentCapacityOwner | claim独立COMMIT→_transition AgentRun RUNNING/旧pool独立开始→ack独立COMMIT | 保留一次claim/unknown不重发；联合准入的实际开始事务必须包括budget/Intent，不能跨后续阶段拼接 |
| ContentBudgetCommandOwner/ContentGenerateHostService | 原预算reserve借用wrapper；Host journal+Receipt外层COMMIT，后续ack独立COMMIT | joint启用后消费/核对同次联合结果与原receipt；不得第二次持有或第二次派发未知Intent |
| AgentRunService.transition | capacity_gate.reserve原独立连接后AgentRun CAS/COMMIT，未知提交保留占用 | 联合模式必须借用caller，CAS/hold/budget/Intent整体提交；保留UNKNOWN及commit未知对账语义 |

源码已核：Host ports147/155/179/328，runtime adapters177/196/4452/5926，capacity owner65/102/129/186，budget command owner491/502/515，ordinary budget97，Eval45，pool44，AgentRun159。行号只是本基线位置，实施前核hash。

## 2. 同连接入口与数据库信任边界

新Python联合Owner处理actual psycopg connection；Host只新增类似现有run_current_source_snapshot的exact Owner委托方法，不返回conn、不允许任意callback进入新Owner。普通原生及Eval入口直接复用同Owner，同一个数据库事务且保留原主体/tenant/SERIAL约束。

资料必须由server推导：Source exact ref→原客户端JWT验证→原SourceOwner窄桥→原不可变签名/批准/Provider/Evidence/root/registry资料；新ledgerOwner不授Source private表/原issuer RPC/C verifier，不让caller DTO充作权威。原预算算法在原caller执行，联合finalize必须数据库核实际普通/Eval reservation及其原请求/审批/三桶ref，不能只信Python Receipt。该预算事实的精确读取权限/窄桥Owner和trusted ACL审计仍待文件级设计，禁止随意授新ledgerOwner所有原public表。

新private schema负责account guard、不可变联合申请、未决上界、窗口计额、唯一Intent绑定及reconcile事件。新Owner NOLOGIN/NOINHERIT/无membership/无特权；tenant FORCE RLS与trustedbody/ACL/trigger审计。账户键沿用server UUID及全局supplier/fingerprint映射，不按Provider或pool另起额度。

## 3. 事务顺序与提交状态机

精确发现→原currentness锁前缀→费用fence最终UPDATE强度→稳定物理account guard实际version写→旧pool约束（ordinary适用）→原普通/Eval预算内核→原AgentRun CAS（ordinary适用）→原业务Intent/journal及Receipt→private joint finalize→caller单次实际COMMIT。

所有预算/pool/Intent ref必须绑定同tenant、physicalAccount、Source exact hash、用途、真实业务申请/Actor、operation/idempotency、原native xid/pid/session。finalize未齐备、不同xid、伪Receipt、错用途/预算种类、重复Intent或变更payload均拒绝；任一步失败整体回滚，无外部发送。

同Source/account的新revision不能清零旧占用；inflight与fixed_window分别累计，unknown/submitted保留，不由JWT/Source/TTL到期返还。真正结算或正式不可变no-effect/reconcile Receipt方能幂等解除。跨tenant共享账户仍拒绝。

延期检查必须抵抗early SET CONSTRAINTS耗尽queue以及Host SQL COMMIT。current_query()='COMMIT'仅为已通过native primitive的候选，不是安全方案已验收：完整protocol/结束通道、后续trigger/锁等待跨期及原Source身份仍要证明。提交命令内最终检查不能虚称物理WAL flush完成时限。正式发送必须另走原当前身份/Owner/八配置/审批预算/效果门。

## 4. 内容链的具体协作决策点

当前收敛候选（2026-10-08原调用回读，细节见§11）：保留原capacity唯一durable claim；联合实际启动事务内复用原AgentRun transition/pool→原capacity ACK→原budget put→原budget claim→原命令构建与trusted Host校验/执行/Receipt→原budget ACK→joint finalize→唯一实际COMMIT。RUNNING、ACK、原预算及唯一Intent必须同事务提交；budget worker后续只读核同次结果，不再独立派发同一命令。候选尚未经过合法原生全链验证，不宣布实现或新执行权限。

这条路径不能直接编码：原ContentGenerateHostService的dispatch/claim权威以及command refs必须从原真实Task/Plan/Review/Logic/ModelRoute来源推导，确认capacity阶段是否已有全部审批及原Intent消费许可。若缺少，不得提前消费budget claim权限。需要原状态机资料证明后选择兼容扩展；不能以移到后面后仍提前RUNNING、伪造budget claimed状态、改用空permission来源等方式硬接。此项是实质实现合同缺口，限制相关动作，不阻止已批准隔离研究或其他安全代码步骤。

## 5. 精确产品文件包（尚未取得此父Task代码Lease）

| 文件（相对services/aos-api） | 计划职责 | 约束 |
|---|---|---|
| aos_api/aip_physical_capacity_occupation_contracts.py（新） | exact普通/Eval联合命令、状态/ref、不可变hash | 不接受外部override/伪Task，复用原contracts |
| aos_api/aip_physical_capacity_occupation.py（新） | 原caller编排Source/currentness/physical/原pool+预算/finalize | 不开第二连接、不复制预算/Source核心 |
| aos_api/aip_physical_capacity_occupation_boundary.py（新） | private schema/窄桥/原数据验证/整体提交门/可信安装审计 | 原Source ACL不扩，预算事实权限待细化 |
| alembic/versions/新增物理occupation迁移（编号在Lease时核分配） | additive新Owner/账本/审计/切换门 | 不重写已发布旧迁移；正式库仍不迁移 |
| aos_api/ecommerce_growth_host_ports.py | exact trusted Owner同conn入口 | 不导出conn，不破坏原source/journal接口 |
| aos_api/ecommerce_growth_runtime_adapters.py | Content真正joint执行/原Receipt核读 | 原可信SQL和既有normal/no-effect分支保留；不整体regex禁SQL |
| aos_api/ecommerce_content_capacity_owner.py | 原claim/启动joint/ack一致接续 | start必须真的包含joint，unknown不重发 |
| aos_api/ecommerce_content_budget_command_owner.py | 核读既有joint結果/受控后续阶段 | 不凭推荐路径提前取得claim权限 |
| aos_api/aip_agent_run_service.py | joint mode CAS和caller一致、旧unknown保护 | 未启用时保留兼容；不得全局静默降级 |
| aos_api/aip_model_capacity_reservation.py | 同caller旧pool约束与cutover后旧入口禁入 | 旧TTL不解除新ledger或unknown |
| aos_api/aip_budget_reservation_store.py | 原预算算法复用及all-entry gate协调 | 不复制三桶/审批/Price语义；旧fence后置混跑必须禁入 |
| aos_api/aip_model_eval_budget_reservation.py及其实际接续入口（待回读确定） | 真Eval request同物理account/预算/唯一Intent | 未找到实际接续入口不能把hold当整条Eval |
| tests/aip/test_physical_capacity_joint_pg.py（新） | 新157+additive、原真实创建/完整joint COMMIT矩阵 | 不用handinsert Task/AgentRun、mockReadyLogic或空治理resolver |
| 原AgentRun/Content/Eval相邻测试 | 原功能、claim/ack、未知状态兼容 | 保留旧正常功能与记录 |

文件清单不是开码授权凭证。旧Source/profile文件不纳入此包；旧有Task重叠必须原owner对账。现有Repo未取得新joint代码Lease，产品文件尚未创建/修改。

## 6. 全入口切换和旧义务

先完整登记普通、Eval、Content实际writer及直接SQL权限；启用新联合模式前必须原Owner签名资料/精确安装、零执行窗口和不可变切换Receipt。旧writer预算桶→fence顺序与新fence→physical→桶不能混跑；未切换完成、未知映射或旧未决义务缺失则该账户准入拒绝，不能绕过current guard或清空旧表。

合法历史须真实AgentRun/Attempt/原业务Receipt链，精确pool revision/hash+Source Providerrefs+全账户映射。当前retained native反例没有合法AgentRun，不能用作生产导入授权。不存在合法history positive时保留缺口，并实现/验证missing、unknown和冲突的fail-closed行为，不伪造完成。

## 7. 完整验收矩阵

- 原真实Skill/Logic/ModelRoute/Task→TaskRun→AgentRun与原一等Eval创建及独立checker；禁止手工run_definition或fake插入代替。
- 原signed Source两个Provider共同账户、ordinary/Eval/pool/revision混合并发；两token模式与窗口切换、不随新Source重置。
- 同caller/xid/pid/session的pool+physical+普通/Eval预算+唯一Intent实际COMMIT；每节点故障整体rollback、replay/hash漂移/重复/不同预算类拒绝。
- Source/current Owner/member/批准/Provider/Model/Price/健康/配置撤回writer-first与reader-first，费用fence/all-entry实际同序竞争。
- 锁前、等待后、实际提交阶段JWT/Source/approval deadline；early SQL COMMIT、SET/END/多语句/协议控制，后续触发等待跨期。
- 正式unknown、COMMIT结果未知只读对账；unknown在TTL/撤回/revision/窗口后保留，无重发或自动返额。
- 原budget/AgentRun/Content功能相邻、租户零副作用、exactOwner/ACL/RLS/未知函数/漂移拒绝。
- 完整当前schema安装和相邻累计；正式库迁移/PG→API→Web重启、八工作台、自然首链与连续观察/发布仍走231独立后续门。

## 8. 下一实际调查

优先原Content before_capacity授权资料与budget Intent claim可用时点；并查Eval hold的实际应用Owner/唯一Intent producer。目标是消除§4与§5的真实接线缺口，而非再重复已通过单个锁/延期primitive。第二安全候选为普通预算/费用fence all-entry禁入机制的原writer核查。两者在父证据Scope可继续；产品实施依完整文件包/准确Lease与上述合同核查推进，Goal保持active。

## 9. 本轮实际接线调查结论（未实施）

Content `_prepare_sources(before_capacity=True)`的docstring明确结果不是execution grant，不可跨事务缓存；从capacity intent核pending/claimed，额外禁止已有capacity尝试，仅产生preflight资料。`_prepare_approval_sources`可在capacity阶段准备审批，但 `_build_command`调用的是budget阶段来源，不能把before_capacity结果充作其授权。

原a0v_104的budget intent producer进一步要求capacity state='accepted'且该行xmin==当前xid，必须在capacity ack同事务产生。现有capacity start与ack分别COMMIT；因此§4推荐路径不能简单把原budget producer/Host dispatch提前到start。这项已由原SQL明确证明的依赖必须作为真实状态机设计输入。合法改造需要独立、明确受安装/当前身份/原审批约束的joint producer合同，或通过经方案核查的状态机接续协调；不能复制a104元数据、修改已发布迁移或伪造accepted/claimed。这里不把新的producer候选视为已获正式运行授权。

Eval：现有 `AipModelEvalRequestStore`持久化一等申请、`ModelEvalActionGuard`核原metadata/Owner/checker；预算hold目前仅在PG测试中静态调用。对当前aos_api Python范围未发现产品代码import/构造AipModelEvalBudgetReservationStore的consumer；aip_model_runtime router提供eval-candidates，不等于正式request/approval/hold/Intent执行入口。静态扫描无法排除动态外部加载，不能声称整个外部生态绝对无调用。

因此精确新增候选文件为aos_api/aip_model_eval_execution_contracts.py、aos_api/aip_model_eval_execution_owner.py及tests/aip/test_model_eval_execution_owner_pg.py；需复用原request/action/budget并接shared physical及一次真实Eval Intent，不把持久申请或hold helper当执行完成。若需公开HTTP/工作台接口，其路由/主app/页面另按实际依赖登记，不能从当前eval-candidates页面推断已接通。这些候选仍未取得代码Lease。

下一实际研发应优先解决受控joint producer的权威来源与合法创建fixture，再取完整代码Scope；不继续重复前轮已通过native primitives，不为维持进展制造无意义提交。formal Source/八facts/效果权限不足只关闭发送，隔离实施和负门仍继续。完整长程Goal不缩减。

## 10. 合法 Eval 前置资料审计（2026-10-08，源码证据）

原 seeded_approved_model_eval_request 并非完整合法创建链：直接 INSERT validated RegisteredModel/head version=7；默认 Provider/Price 直接插入，Quota 使用历史种子和合成 approvalRef。formal_sources 仅替换部分 budget/provider/price，仍保留合成 Quota 与直接写入 Model。原申请/审批测试的局部价值保留，不能据此宣称全部前置来源合法。精确源码 hash 见 legal-eval-fixture-source-audit.json；本次没有运行该 fixture 或访问数据库。

原 publish_model 会核当前 Price 与 exact active Quota/Budget，active Model 另需原已通过 Eval；不能通过绕过 Store 来消除依赖。通用 governance Store 明确拒绝直接发布 active Quota/Budget。已找到原 Quota 合法隔离路径 signed_quota_case/approved_quota：草稿发布→签名提案→独立 checker/Issuer→专用 QuotaPolicyConsumer→exact active 回读，不能复制历史种子代替。隔离身份/bootstrap 本身不授正式运行权。

下一验收资料应复用原 Quota 激活、真实 Budget/Provider/Price 来源，通过原 Store 发布 validated Model，再从实际 head 推导 expectedHeadVersion，创建原 Suite/Contract/Request/独立审批。最后联合 Owner/唯一 Intent 仍需完整新代码 Lease与文件方案；当前尚无整链正向运行证据。优先研究这条创建链，第二候选仍为费用 fence 全入口切换。

### §10 配额前置门原生验证计划

只新增本目录 run_legal_quota_preflight.py、legal-quota-preflight-r1.log/json。复用原 test_quota_policy_activation_pg 三项：signed消费与exact reader、文本审批拒绝、runtime直接active写入拒绝。使用原全迁移隔离fixture新建随机数据库，保留数据库；不改产品/原测试/正式身份，不运行Provider。脚本仅向精确实验admin连接提供现有passfile，禁止全局凭证变量；记录真实pytest终态与实验库名，失败保留并诊断，禁止冒称完整Eval创建链通过。

原配额前置门本次3 passed/7 warnings/7.02s，保留库 aos_test_421ea956ac61_ti4_test。独立SERIAL READ ONLY核唯一activation Receipt/审批事件、exact active revision2、原Consumer/Issuer角色恢复NOLOGIN、四业务表0及dev-org quota0。独立校验首轮角色名称猜错导致断言失败，回读原fixture后修正断言，无重跑审批/消费；详见legal-quota-preflight-independent.json。仍不宣称整条Eval合法创建或联合事务完成。

### 合法 Model 创建前缀验证计划

新增 test_legal_model_creation_prefix.py / run_legal_model_prefix.py / legal-model-prefix-r1.log/json（仅本证据scope）。在新全迁移保留实验库复用原正式Provider fixture、原签名费用提案/独立审批/consume/derive、原签名Quota审批/Consumer；显式构建模型DTO并使用原canonical hash与publish_model，不直接插入model/head/activepolicy。回读actual head/version、唯一publication Receipt与预算/配额exact绑定及canary0。只证明创建前缀；Suite/Contract治理来源及Eval执行Owner未覆盖。失败保持原记录，不重发未知结果。

Model前缀本次1 passed/7 warnings/13.59s，保留库 aos_test_ff3f78ea18d6_ti4_test。实际 original publish_model 输出validated revision1/head version1；独立只读核唯一publication Receipt、exact当前active quota/budget、角色恢复、四业务表0及canary model0。未创建Eval申请/hold/Intent；治理Suite/Contract来源继续待核。结果见legal-model-prefix-result-r1.json与legal-model-prefix-independent.json。

### 合法发布后的一等 Eval 申请与独立审批验证计划

新增 test_legal_eval_application_chain.py / run_legal_eval_application.py / legal-eval-application-r1.log/json/result。复用已验证Model前缀，在新随机保留库实际创建原Graph/Suite/Runner治理gate/Contract，再注册未执行的model-target Suite/冻结Contract；这个test-only数据集与治理结果不证明model质量。actual head1构造ModelEvalRequestCreate；原Store幂等create、错误head7负门、原Action签名身份提案、独立checker审批与self-check负门；明确executionAllowed=false、无模型gate/AgentRun/预算hold/Intent。绝不把治理布尔Graph的通过冒称Model评测。独立只读核精确来源/申请/审批与业务零行。下一实际Model执行Owner及真实数据集语义仍单独登记。

申请r1在治理helper短模块名导入处失败，库aos_test_33f4889645de_ti4_test保留，尚无申请/审批动作。原前缀helper硬编码输出文件导致本轮资料覆盖旧result-r1，已将新资料独立另存legal-model-prefix-application-r1.json并从精确HEAD还原已提交旧文件，未修改历史DB。r2仅新增独立helper副本/target/runner与独立输出文件，将原extension_runtime测试目录加入sys.path；新随机库重新执行新独立资料，不重发r1任何proposal。失败首轮脚本与日志保留。

r2仍在同helper import失败，库aos_test_0ee455a745a5_ti4_test保留；新增测试目录选错层级，rg定位依赖实际位于services/aos-api/tests。r3新增精确该目录，保留r2全部脚本/结果并使用独立r3输出与全新库；不动产品、不重放已有提案。

申请r3 1 passed/7 warnings/14.04s，保留aos_test_eb6ca3ed1d24_ti4_test。独立READ ONLY核request1/hash/actual head1/validated model、exact Suite target、approval1且独立checker、executionAllowed=false、model quality gate0及三业务表0/canary0；r1/r2申请0/业务0，各已提交前缀保留，不重放。结果仅原非执行申请接续，真实模型数据集、Model执行Owner、shared physical/budget/unique Intent尚未接通。

### 原Runner模型执行门只读核查

新增 probe_original_model_runner_gate.py与original-model-runner-gate.json。针对刚保留r3库，真实native SERIAL READ ONLY+aos_runtime租户连接，原AipEvalRunner两个入口分别使用真实Suite/Contract精确引用与计数callback；必须原formal Model executor unavailable拒绝、callback0，Eval run/report与预算/AgentRun/申请计数前后不变。不调用Provider，不解除原负门。若通过，在完整文件清单补aip_eval_runner.py与真正typed Model接续接口，不能仅删除两处拒绝或注入任意executor回调。

### 原预算hold在合法一等申请上的actual caller验证

新增 probe_legal_eval_budget_caller.py、legal-eval-budget-caller-attempt.json、legal-eval-budget-caller.json。仅针对保留r3申请库、原未到期精确申请/独立审批，先只读核reservation0。真实nativeSER+aos_runtime：错审批/canary拒绝；首次hold后读取同xid/pid并显式rollback，独立回读全预算桶快照与reservation/link0；第二次hold caller实际COMMIT（先落attempt，失败未知只读对账、不重发）；已知提交后合法幂等replay并回滚，只读核唯一hold/三桶reserved与held10、无AgentRun/ModelGate/canary。只验证原预算同事务foundation，无Source/physical/Intent，因此不得启动Model。脚本已有attempt一律拒绝重新执行。

原预算caller本次通过；独立SER READ ONLY核不可变hold hash、hold/3links/3实际预算桶xmin均等于确认COMMIT xid；FORCE RLS2表、held10/其他风险0、hold1/links3/AgentRun0/pool0。实际held义务保留，不因申请过期释放或重放；此前r3申请证据预算0是这一确认提交之前的历史观察，不改写历史。

完整joint文件包追加aos_api/aip_eval_runner.py与tests/aip/test_model_eval_execution_gate.py及真实原PG接续测试：原两个入口注册模型拒绝已native只读验证（2入口/callback0/写0），不能删除拒绝直接接受任意target executor。新typed exact应用Owner须验证当前申请/独立审批/预算同xid/Source/physical/唯一Intent/finalize与正式执行资格，生成绑定Suite/Contract/model-target的数据；旧通用run/run_by_contract保持无权拒绝。真实model-specific数据集、合法runtime及ModelQuality报告与Gate另验，不复用Boolean Graph结果冒称模型质量。

预算fact窄桥目录输入已独立只读落盘budget-fact-bridge-catalog.json：8表Owner均aos_app，34条policy包含runtime与若干特定Owner，以及PUBLIC策略；不能仅凭存在PUBLIC策略推断任意新NOLOGIN Owner可读，必须回读其USING表达式与角色门。下一结合精确column grants/租户RLS/实际xid及原hash/ref验证设计，无新role/function/grant创建。

补核polpermissive：本次PUBLIC策略全是restrictive，不授予新Owner行访问。窄fact Owner若新增，必须精确permissive tenant策略+最小列ACL或原角色trusted桥，不能以PUBLIC/角色membership/BYPASSRLS绕过。

### 原runtime窄预算fact桥原生候选验证

新增独立r4原合法申请fixture副本、test_budget_fact_owner_bridge.py、run_budget_fact_owner_bridge.py及r4结果。新随机全迁移保留库，新NOLOGIN/NOINHERIT/无membership/无特权ledger-probe Owner仅schema USAGE与固定函数EXECUTE；固定函数属于原aos_runtime，最小schema CREATE安装后撤销，PUBLIC EXECUTE撤销，不向ledger Owner授任何原预算/申请表权限，不用membership/BYPASSRLS。函数只核exact tenant/request/hash/原hold及3links+3桶actual current xid，返回数据库事实；原hold/审批先由原流程完成，不在桥内造审批。测试原DB表访问拒绝、exact同caller正向、bad hash/canary拒绝、COMMIT后新tx旧hold拒绝。所有caller为owned admin native SCRAM→LOCAL runtime/ledger，仅ACL/xid primitive，不是正式occupation身份/Source/执行权。只调用新临时函数，结束撤除函数及role/schema grants，角色/schema保留无权，hold保留。完整production桥仍需Source/session/安装/全Intent/finalizer trusted审计和普通预算分支。

窄桥候选本次1 passed/7 warnings/13.98s，保留库aos_test_bde66457881c_ti4_test；独立READ ONLY核新Owner7特权位全false、membership0、5原表table/column权限0、函数已撤且schema USAGE已撤、held义务1/3links/3桶同确认xid且held10、AgentRun0/pool0/canary0。新Owner没有原runtime membership，也不需要改原表RLS。固定函数原runtime Owner方案可继续细化，但本次是owned admin/session primitive，不是正式occupation/JWT/Source联动；普通预算分支及完整finalizer还pending。

普通预算核查（精确源hash见ordinary-eval-budget-fact-source-binding.json）：ordinary reservation/invocation是可变revision/state，而Eval是不可变held-only；原initial_hold_refs在后续转换后仍保留initial不可变引用。正式桥的普通分支必须核原invocation prepared/initial held ref、reservation held1、原sequence1 held事件、3links/3桶与同native xid，不将后续mutable hash当初始hold。后续submitted→unknown原算法将submitted余额移到unknown保留风险；release_no_effect在已提交/unknown时仍需原provider/reconcile证据。新physical obligation不能只凭bucket/status变化释放，必须exact对应结果证据。两种预算分支不可混用，仅有Eval primitive不算完整bridge。

### 后续延迟触发器等锁跨期限的原生验证计划

新增 deferred_later_wait_probe.py、deferred-later-wait-attempt.json、deferred-later-wait-verification.json、deferred-later-wait-r1.log。仅新随机保留实验库，克隆已核空业务模板。两张test-owned obligation表分别按名字排定 check→wait / wait→check 两个 AFTER ROW DEFERRABLE INITIALLY DEFERRED 触发器；检查实际current_query=COMMIT与clock_timestamp期限，等待独立连接已持有的advisory lock。native SCRAM admin→LOCAL runtime/SERIALIZABLE，单次真实COMMIT在线程中执行；独立observer读取pg_stat_activity/pg_locks及DB clock，确认COMMIT实际等待并自然跨期，再释放owned阻塞锁。记录attempt与已知终态，不重发未知COMMIT，所有线程有界join。预期check→wait可跨期提交（严格提交期限假设RED）；wait→check跨期23514整体rollback。独立READ ONLY核原业务四表0、模板和迁移头未变、精确trigger/function定义及真实audit时间，不将test-only合成触发器称作正式业务漏洞。方案必须明确final decision-check与实际commit完成的区别，仍需全触发器/lock/end-channel审计；不得声称COMMIT字符串门保证WAL持久化期限。

后续延迟等锁本次原生2case通过，保留库aos_test_later_wait_5014a31a1e51。check→wait在DB clock期限前检查，真实COMMIT advisory wait跨期限后释放，实际提交row1，audit检查时间<deadline<wait完成时间；wait→check实际23514 GT_TEST_DEADLINE_EXPIRED，row/audit0，整笔rollback。独立SER READ ONLY核exact4 deferred trigger/2函数、已提交xmin等于caller xid、原业务四表0、迁移头未变且剩余advisory lock0。两case均单次COMMIT，有attempt/已知终态，不重发。

方案修订：current_query=COMMIT只收紧结束命令入口，不保证实际完成期限。finalizer必须把必须等锁与所有可能等待的依赖核验放在最终期限决策之前；需审计完整deferred queue及后续SQL/锁，不能仅凭字母名最后触发器证明整个产品最后检查。严格定义当前候选为“最终决策点DB clock未过期”，实际COMMIT/WAL持久化/客户端确认仍不能由本primitive保证；如产品要求期限内完成实际提交，须另行完整协议和失败语义设计，不静默替换需求。Source/approval/budget当前性与唯一Intent仍需原可信入口完整联动，合成实验不证明产品可被调用或越权。

原保留Source实验库aos_test_fc2688b199ad_ti4_test后续READ ONLY核全部public/Source私有deferred目录：application 34，internal RI 105（见original-deferred-final-check-catalog.json，精确定义与function源hash）。每表trigger字母排序不是整个事务事件队列顺序，FK内部C触发器亦可能等待key-share/行锁。原a144 atomic_triple在function入口缓存live_now，随后读proof/binding/receipt/installation；最终方案需核这一取时点与实际调用/锁顺序，不把本目录推断当已原生证明的原产品跨期。完整finalizer不能仅加入一个名字排序最后的trigger就声称全事务最后检查。下一先列真实调用写入顺序、全部deferred event与FK锁依赖，再决定统一trusted结束入口的收敛设计；不改已发布迁移，不重跑已知提交。

## 11. Content原状态机同caller接续候选（AOS-001490之后，取代§4旧推荐与§9过强推断）

### 11.1 原源码证据与可复用路径

精确hash/类/方法/行范围见content-joint-original-call-binding.json。ContentCapacityOwner._transition实际将TransactionBoundConnectFactory传给AgentRunService；其默认CapacityReservationGate继承该factory，因此这一具体路径的旧reserve也在borrowed caller，内部commit被抑制。§1表内AgentRun通用独立连接描述不能机械套用到此Host-bound实例；严格native新接口仍不能接受borrowed wrapper。

原a103 ACK核真实AgentRun running与原live pool reservation；没有要求RUNNING已经独立COMMIT。原a104 put要求真实capacity accepted行xmin=current xid，这是ACK与put同事务要求，并不要求ACK处于后续单独事务。原a104 claim再核current+pending/attempt0/无runtime Receipt，实际推进一次claimed。故之前“必须独立新producer才可接”是未经完整顺序审查的过强推断；可优先验证原ACK/put/claim整体搬入同caller的候选，但不能把静态可行宣布已原生跑通。

候选严格顺序：
1. 原唯一capacity claim已durable；未知归属/attempt不得重领。
2. 新exact trusted联合Owner同native caller完成原Source/currentness/费用fence/account guard（全入口锁序另门）。
3. 原AgentRun transition逻辑与原pool算法同caller，得到真实RUNNING行和exact reservation（尚未提交），失败整笔回滚。
4. 原a103 ACK真实token/reservation→原a104 put→原a104 claim with server UUID，均同caller；不直接写accepted、不伪造claimed、不改旧迁移。
5. 原_build_command此时从真实budget claimed intent读取资料、原route/Task/Plan/Review/approval/Price/安装派发重核；before_capacity preflight不充作execute grant。
6. exact trusted Host同caller路径保留原_lock_and_revalidate→binding.revalidate→binding.execute→strict Receipt→binding.verify_receipt及原Adapter._verify_and_journal/BoundRuntimeStore.put；原ContentExecute持久原budget/journal一次，无Provider调用。joint预算阶段必须协调到此实际reserve点，禁止在step2先hold又在此reserve第二次或用replay掩盖不同xid。
7. 原a104 budget ACK核实际HELD/PENDING/runtime Receipt，与新private finalize核Source+physical+pool+ordinarybudget+AgentRun+唯一journal/Receipt同xid；未齐全不得实际COMMIT。
8. 统一trusted结束入口一次实际COMMIT，再独立只读查全链。任何提交未知保留原capacity durable claim及所有可能已提交义务，禁止重跑transition/claim/dispatch；known rollback也不擅自重置原一次attempt，走已授权恢复路径。

### 11.2 精确实现包与权限边界

新增/变更候选仍是§5精确联合包；补tests/aip/test_content_joint_transaction_pg.py（合法原Task/Run/AgentRun、原claim/ACK/put/claim/预算/journal/Receipt真实正向与逐节点故障），以及原Host port/Content capacity/budget worker相邻测试。Host ports新同caller入口仅exact trusted联合Owner允许，沿原固定registry选择唯一Content binding；不向可选package提供rawconn、任意callback/OperationBinding，也不允许其调用普通commit入口结束联合事务。旧commit分支保持原行为。新joint模式原budget worker在已accepted同次Receipt只读消费，pending/claimed/unknown旧记录按切换mapping门而不是自动补发。

原budget/pool接口native严格检查不放宽；可由exact trusted Owner原conn委托原算法，并保持原normal/no-effect版本兼容。新mode不可silent fallback或混用旧bucket→fence锁序。零执行/原Owner签名安装/cutover/历史unknown义务mapping齐全后才启用；当前只设计，不开启Host/Provider。

### 11.3 提交门的收敛约束

本轮原实验目录列34 application deferred与105 internal RI（包含非本联合路径，不能全部当实际队列）。必须以实际新joint写表事件闭包确定队列，而非目录总数或每表字母顺序。候选在trusted结束入口显式执行所有实际相关legacy deferred检查/RI，保证后续相关约束处于IMMEDIATE，再把所有必要锁/当前性核验置于final deadline决策前；仅新joint完整性guard保留COMMIT强制。细粒度constraints选择必须绑定精确catalog与所有可产生的新event，不能未审计直接SET ALL，也不能关trigger、改旧函数、用no-op消除RI等待。错误提前SET必须整体拒绝；任意SQL/结束通道仍须native负矩阵。

这是待验证方案，不声称可由SQL证明不存在后续触发器/等待或WAL时限；若legacy函数不容许提前检查，完整队列不能可靠收敛，则保持该路径拒绝并另设计协议，不降低期限要求。最终decision时间≠实际COMMIT完成时间，严格完成期限须完整业务协议裁决，不静默更换。

### 11.4 仍未收口的真实缺口与下一步

原合法普通Task/Plan/Review/Skill/Logic/ModelRoute/RUNNING positive、Source+八依赖正式来源、ordinary可信预算bridge完整hash/初始event、shared physical历史义务切换、Model typed Eval Owner与真实model-quality dataset仍未完成。无这些正向链，不得宣称fulljoint/首链，不能用fake ReadyResolver/handinsert AgentRun/旧12Run替代。下一从原自然Content TaskRun/AgentRun创建的方案与原fixture逐项核合法来源，列出必须复用的真实创建接口和未合法seed，确认candidate可原生验收资料后才取完整product Lease；第二候选typed Model Eval数据集/执行合同，保持同一完整joint目标，不另起平行任务分母。

Content验收源资料审计见content-full-chain-fixture-source-audit.json：旧extension_runtime TaskRun/AgentRun PG fixture手建缩减schema并直接insert Task/Plan/Run/AgentRun/Review runtime Receipt，teardown含DROP DATABASE；本轮未执行，原局部门价值保留，不改原fixture也不让其清理保留库。原真实Owner已定位create_plan/create_run/start_run与AgentRun创建/原registry Receipt/ACK。完整新测试必须新全迁移保留库，从真正Review/Task/Brief/production assignment/pre-review gate/Skill/Logic/ModelRoute来源走原创建，不能以本source audit算正向通过。
