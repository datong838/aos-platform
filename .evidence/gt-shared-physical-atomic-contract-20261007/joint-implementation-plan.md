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

推荐研究路径：保持原capacity claim与ack，扩展其实际启动事务，使Source/physical/pool/原budget/AgentRun CAS/唯一Intent在同caller齐备后才RUNNING；后续budget command阶段只核读同一次联合结果，沿原幂等Receipt完成受控接续，不能重新持有预算或派发未知结果。

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
