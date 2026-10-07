# 全物理账户、原预算与一次 Intent 联合合同入口

基线 m1 e5bc1999 / AOS-001471，唯一施工者。此 Task 先核合同与原生反例，不修改已到期 Source/Profile Lease 的文件。已提交预算和 pool caller 内核均不是完整物理账本。

## 当前源码事实

签名 Source 的 physical_account_id 是规范 server UUID。私有 global_account 对 supplier_id/fingerprint 全局唯一，global_provider 将 Provider 映射到同一账户；多个 Provider、Source revision 或 pool revision 不能分别享用同一账户全部额度。当前映射有明确 org/project 所有者，不能自行开放跨租户共用。Source execution_allowed=false 不授发送权。

occupation Source 要求独立真实 SCRAM session、aos_runtime、SERIAL/readwrite 与精确租户，并在原完整 currentness 检查中持 epoch SHARE。原预算 reserve_in_transaction 与 Eval hold 已支持同 caller。旧 pool 内核按 pool/revision 计数，且到期会排除 reserved/consumed；必须保留兼容事实，不能拿它作 unknown 物理义务释放。

## 联合锁图候选，逐 writer 复核后才能冻结

Source／Model／批准／配置 currentness → 稳定 physicalAccount mutex → 普通 Route/pool 约束（如适用）→ 原三预算桶稳定排序 → operation/invocation/Intent 幂等账本。旧预算先于 physical 的草案不能直接实施；需核对现存全部 writer，不在持预算锁后反向等待 physical。

锁前、锁等待后与实际 COMMIT 前的 JWT／Source TTL／批准和配置再验分别证明；函数返回前校验不能冒充实际 COMMIT 证明。原普通入口在联合切换启用后也必须接线，不能只给 Eval 加共享门。正式身份不足仅限制发送，继续隔离实现与负门。

## 完整额度与旧义务切换

必须覆盖 Source 签名的 inflight_upper_bound 与 fixed_window_rate 两种 token_limit。单账户并发合计普通／Eval／不同 Provider 和池，不随 Source revision 重置。窗口滚动不解除 inflight 义务；held/prepared、submitted、unknown、settled/reconciled 的账本、上界、窗口计额与幂等释放须完整规定。

unknown 不因 TTL、撤销或 Price 漂移释放或重发。完整映射旧 pool reserved/consumed/released/expired 与 ContentCapacityOwner start/unknown 历史；旧 expired 不自动证明外部零效果。零执行切换、旧入口接线／拒绝、旧新共同计数及完整账户映射缺一时禁新启用，不能清零既有义务。

## 下一实际调查与文件级实施准备

1. 复核 ecommerce_content_capacity_owner 和 capacity consume/release/expiry writer，产出锁图与旧 unknown 来源清单。
2. 在原完整 signed Source 的两个 Provider 映同 physicalAccount 上建立原生反例。拟议 tests/aip/test_physical_capacity_joint_pg.py 尚未登记代码 Lease，先固定合法资料与验收合同。
3. 新 joint owner 候选 aos_api/aip_physical_capacity_occupation.py 与 additive migration 必须另登记精确范围，FORCE RLS、不可变身份／事件、真实申请与原 approval、原预算 ref、一 Intent 唯一性同时落地。原普通／Eval预算内核不复制，不造假 Task/AgentRun。
4. 验证 actual caller COMMIT／rollback、不同用途与 revision 并发、unknown 保留、两种 Token 模式及等待后权限／TTL，不以容易通过的单池测试替代全物理联合目标。

独立候选为旧 API 测试元数据清理隔离契约与 Source/Profile 未覆盖权限 catalog。当前合同尚未冻结，尚无新 ledger 代码、业务执行或整体完成；完整 Goal 保持 active。

## 本轮原生 TTL 反例步骤

文件限定本 Task 的 legacy_ttl_probe.py、legacy-ttl-r1.log、legacy-ttl-r1.json。使用已登记隔离容器及现有0600 passfile；只从前轮保留的空完整迁移库复制新实验库，原模板只读且保持不变，新库永久保留。本轮不改 API，也不插入伪造 Task/AgentRun 以声称合法业务启动。

复用旧池测试构造的两个独立 max_concurrency=1 池，将实验池 lease_seconds 配为合法1秒。分别以原 Gate reserve 和 reserve→consume 建立占用；先证明第二笔被并发上限拒绝，再以新只读事务轮询真实 DB clock 等待自然到期（单例最多5秒）。不修改 expires_at。第二笔若成功、旧状态变 expired，则记录旧原子算法确会凭 TTL 恢复额度；这是未知义务切换所需的负向依据，不证明真实 unknown AgentRun 历史。另记录 Source 缺失、canary0、事件和实际已提交行。原 AgentRun unknown 自动释放继续列为源码确认、PG合法历史反例待补。

### 原生结果与准备阶段失败

首轮在新库 aos_test_legacy_ttl_ae6edba4017f 中试图修改已插入的池版本租约，被 AIP4_APPEND_ONLY 拒绝，未建立容量申请；失败库和 legacy-ttl-r1.log 保留。这属于准备脚本错误，不算目标行为 RED。修正为首次 INSERT 时写合法1秒租约，无禁用 trigger、改 expires_at 或清库。

第二轮新库及基线绑定见 legacy-ttl-r2.json：两个 case 的第二笔在到期前均因 capacity_concurrency_exhausted 拒绝，真实 DB clock 超过原 expires_at 后，原 Gate 将首笔 reserved/consumed 改为 expired 并为第二笔写 reserved。独立 SERIAL READ ONLY 回读验证4 reservation／7 event、AgentRun0、dev-org0、模板仍零行，迁移头一致。验证见 legacy-ttl-independent-verification.json。产品代码未变；这证明 legacy TTL 回收路径，不证明 unknown AgentRun 的合法 PG 历史或 signed Source 联合账本。

## 旧义务导入与释放合同（切换前必须满足）

| 旧池状态／关联事实 | 物理义务切换判定 | 释放条件 |
| --- | --- | --- |
| reserved + 未提交外部 Intent | 默认保留 held，并核全部提交结果 | 当前不可变取消／回滚 Receipt 证明未提交，且无未知发送 |
| consumed 或已提交 Intent | 保留 submitted 上界 | 对应结算或正式 reconcile Receipt，不能由 TTL 代替 |
| 任意旧状态 + AgentRun/Attempt unknown 或 COMMIT 结果未知 | 保留 unknown；禁止重发 | 独立只读对账证明实际结果，并产生可验证结算／reconcile |
| released/expired 但缺少对应结果 Receipt | 不视为零占用；列待对账义务 | 原 event 仅证明池状态改变，仍需上列结果证据 |
| settled/reconciled | 校验精确 operation、invocation、account、tenant、上界与结果绑定 | 幂等一次释放并保留不可变事件，不能删记录 |

旧状态不能单独决定物理余额。Source 撤销、窗口滚动、模型／Price 漂移均不得解除 unknown inflight；fixed_window_rate 还需保留已计窗口支出，释放 inflight 不等于返还已发生 rate 用量。未能映射的旧行列入保守义务或禁止该账户新准入，不能丢弃行后初始化满额度。

## 已确认 writer 差异和冻结前剩余验证

原 AgentRun transition 当前在 RUNNING/PAUSED 离开且目标非 RUNNING 时调用 release_for_run，包含 UNKNOWN；进入 RUNNING 后 commit 报错也会 release 新 reservation。UNKNOWN 无外部零效果证明，这两者均须正式接线时改为可对账的保留义务；目前只读核到源代码，后者未伪称真实 PG COMMIT-unknown。

ContentCapacityOwner 先独立 claim COMMIT，再借用 HostTransaction 启动并 COMMIT，最后独立 ack；异常保留 claimed、禁止第二启动。ContentBudgetCommandOwner 再独立 claim／dispatch／ack。不能把这些独立事务与已完成 caller 预算内核顺序拼接称为一次 capacity+budget+Intent COMMIT。

原池依次 pool_head UPDATE→reservation replay UPDATE→过期行 UPDATE；原预算 invocation advisory→三桶排序 UPDATE；Eval 原 proposal UPDATE 与 policy/budget head SHARE。联合 Owner 必须避免在持原桶/operation 锁后反向请求 physicalAccount；沿 currentness→physical→pool→原桶→Intent 的候选顺序逐入口检验，旧 writer 在零执行切换前禁入或完整接线。仍待真实相反 writer 等待／死锁反例、完整 signed Source 两 Provider 共同计数、合法 AgentRun unknown PG 历史与一次 Intent 实际提交回滚。这些未完成，不冻结合同、不关闭 Task，不称物理联合容量 GREEN。

### 合法 unknown 资料核查与下一步

test_aip6_capability_run_handoff.ids 直接插入 Task/Plan/Run；同组 AgentRun 测试猴补 _require_logic，Skill fixture 直接写发布行。test_ecommerce_content_agentrun_owner_pg 创建简化表并直接写 AgentRun／Receipt，不能用于本合同的合法创建链正向证明。不得用这些夹具消除目前缺口。

本轮新增 authority_inventory.py／authority-inventory.json：只读核已登记 retained signed Source 三实验库的原完整表、global_account/global_provider 映射规模、AgentRun/Task/Receipt/容量状态；同时产出实际文件 hash 与 AST writer 调用行号。输出不含签名、JWT、凭证或原业务 payload。目标是核对现有真实历史能否复用，而非重发旧 Source attempt。后续合法 PG fixture 需通过当前签名 Eval→gate→publication→Skill、原 Logic、真实 Task Owner 与实例/binding/ModelRoute currentness 共同构造；Source/profile过期 Lease 文件本轮仍不改。

只读结果：aos_test_5555333a8a3a_ti4_test 的 Source1／账户关联Provider1；aos_test_76dab8183c82_ti4_test 的 Source1／账户关联Provider3；aos_test_66ef56c3d543_ti4_test 的 Source0。三个库 AgentRun 均0。多 Provider 的实际账户映射资料已存在，但原 origin 已撤销，不能拿历史 Source 行作为当前准入或重发依据。此结果不授旧 attempt 重试权。

### 锁图修订（取代首段简写的 operation 后置候选）

普通 reserve_in_transaction 实际先 invocation advisory→reservation replay UPDATE，随后检查原 Task/Budget/Price/Approval，然后原三桶排序 UPDATE。不能改写成预算桶先于 invocation；联合 Owner 候选为完整 currentness锁前缀→稳定 physical mutex→pool_head→原 invocation/replay→已持 currentness复验→原排序预算桶→physical义务与一次Intent INSERT。上述仍只是候选：Eval 先锁 proposal UPDATE，再 policy/budget head SHARE，需要提前锁住其完整 currentness，保证持 physical 后不会再引入反向等待。

| 入口／writer | 实际锁或事务顺序 | 联合接线必须证明 |
| --- | --- | --- |
| Source prepare/finalize | 原 signed facts lock前缀→排序 account/provider/attempt/request advisory→global映射 SHARE→pending UPDATE；finalize仅原xid/pid/session复用 | 不把 pending先锁后回到原currentness；新 physical mutex与发布身份锁的协调须单独验证 |
| 普通池 | pool_head UPDATE→旧reservation UPDATE→TTL清理 | 新旧共同计额与unknown保留，不能只调用旧 reserve即称全账户准入 |
| 普通预算 | invocation advisory→已有reservation UPDATE→原authority→三桶 UPDATE | prehold重入不新增反向锁；全部currentness过等待和实际COMMIT前再验 |
| Eval预算 | proposal UPDATE→policy/head SHARE→原authority→原桶 | 与普通入口同账户/桶顺序，无对向等待；两种token模式不省略 |
| Content | admitted currentness→独立claim COMMIT→start COMMIT→ack/nextIntent COMMIT | 既有sole-claim未知不重发保留；完整联合切换不能声称旧多事务已是一次COMMIT |

核查输出源hash绑定当前文件，包括未提交Source/profile文件；后者只读，未夺到期Lease。AST只枚举静态execute，动态SQL、完整传递锁以及实际PG并发仍待补。Task继续ACTIVE，当前结果为合同调查检查点，未完成Delivery、未冻结全部锁图、未取得正式业务授权。

## 后续基线更新：两处主动释放已局部修复

上文“unknown会release”和“启动commit报错release”是e5bc1999时的历史源码事实，不再作为最新HEAD行为。60480bcc已取消目标UNKNOWN主动release；edf71ef8已将启动COMMIT异常release改为保留并抛回原异常、记录静态warning。分别65PASS与66PASS单元相邻验收，精确AST范围核对，独立Delivery已完成；没有合法PG创建链或真实COMMIT故障注入。父联合合同Task仍ACTIVE。

旧池TTL反例和发布历史映射证据仍有效：本两修复未改aip_model_capacity_reservation。下一主步骤须current signed Source真实专用身份消费→跨Provider同account占用→两token模式→原ordinary/Eval预算+一次Intent全量联合验证，不能因为主动release修复就省略旧expired/unknown对账与零执行切换。合法AgentRun夹具需真实Logic publication和当前ModelRoute Eval，现ReadyRuntimeStore.require_model_governance空实现、Skill测试注入ReadyRoute/PublishedLogicAuthority仅unit，不可借来冒充完整合法前置。

## 当前 Source + caller 池内核原生反例实施

本目录新增 source_pool_probe.py、run_source_pool_probe.py、source-pool-r1.log、source-pool-counterexample.json。不改旧Source/Profile租约文件；原完整test_occupation_source_consumption_uses_actual_business_caller[distinct]原样执行，插件只在已建立独立SCRAM/SERIAL/runtime Source caller时插入额外反例，然后继续原epoch并发／独立Owner／撤回负门。禁重发历史attempt，所有Source由此次保留随机数据库中的原fixture新建。

Source中三个Provider共用physicalAccount，选两个真实签名Provider refs，各首次插入一个旧pool，pool上限均为Source.max_concurrency，token quantum=1（确认不超过Source上界）。Route/Model DTO仅旧池算法合法输入、无发布权威，因此仅作反例，不造Task/AgentRun或宣称业务READY。调用当前Source完整consumer及原reserve_pool_in_transaction，精确同xid/pid；第一池申请至账户上限，第二Provider再申请1。若成功，则原Source+caller池内核组合仍超出共享账户，证明必须新增联合Owner。独立observer在COMMIT前看0、COMMIT后看上限+1预留与events并确认canary0；全部库保留。此轮仅覆盖inflight Source的跨Provider并发反例，固定窗口计量、合法业务、预算/一次Intent和完整联合Gate仍pending。

## 独立持久回读计划

新增 verify_source_pool.py 与 source-pool-independent-verification.json。只连接原r3保留库，SERIALIZABLE READ ONLY，核原Source签名/哈希、真实账户Provider映射、两池三笔持久预留与事件、AgentRun/canary零行、origin撤销和专用角色归还；仅输出布尔与计数，不输出签名/JWT/原资料。此为反例复核，不能称当前Source可准入或合法业务GREEN。准备r1凭证环境门失败、r2DTO转换失败均保留，不计行为RED。完整联合锁图、固定窗口与原预算/Intent仍未完成，父Task不得关闭。

### 独立回读结果

verify_source_pool.py 原生只读回读成功：Source签名和SHA256有效，3个真实签名Provider映同一个物理账户；两个旧池共3笔reserved／3事件，超过签名上限2；AgentRun0、canary0，专用occupation角色NOLOGIN且零membership，registry epoch2/origin已撤回。证据绑定edf71ef8及原r3日志/探针hash。原同caller xid/pid和提交前不可见由原探针证明，回读不重构或冒称重验。整个检查未发业务请求、未修改数据库。

原test完整1PASS只是Source原控制继续通过，跨池全账户计额仍缺失；两个token模式、完整联合锁顺序、旧未知义务切换、原预算与一次Intent仍pending。本次仅完成当前反例的持久独立核实，父Task保持ACTIVE，不作Delivery或整体GREEN。

## SERIAL 快照与共同账户锁原生验证

新增 snapshot_lock_probe.py、snapshot-lock-r1.log、snapshot-lock-verification.json。只从已登记空完整迁移bootstrap库复制新的保留实验库，建立独立test-only probe schema，不造Task/AgentRun、无Source授权重放。三case分别advisory-only、共同guard FOR UPDATE不修改、共同guard UPDATE版本；两个实际原生SER/readwrite/runtime/精确tenant连接，在第二连接已建立旧快照后证明真实锁等待，用独立pg_blocking_pids观测，再提交第一连接。记录第二连接计数是否过时、40001发生于锁/INSERT/COMMIT哪个阶段及最终持久行。目标是确定联合Owner必须更新共同序列行并在提交前拒绝过时快照，而非依赖锁后普通SELECT自动刷新。所有DDL仅隔离实验schema，保留库和原模板，模板/AgentRun/canary需独立回读。该primitive证据不是签名Source联合Owner实现或业务完成。

### 共同账户快照结果及费用锁升级补验

advisory_only与row_lock_unchanged都实际等待第一caller，锁后snapshot_count仍0，第二INSERT被SSI40001拒绝；versioned_row_update在锁阶段40001，未到计数。三case最终各1持久义务，模板空、AgentRun0、canary0，仅native primitive，非joint实现。

新增upgrade_lock_probe.py／upgrade-lock-r1.log／upgrade-lock-verification.json。在同一保留probe库新增test-onlyguard，两个原生SER/runtimecaller先共享锁再各UPDATE，观察40P01锁升级循环。read_formal_budget_fact对原费用fence取SHARE，require_cost_risk取UPDATE并version+1，ordinary/Eval在桶锁后调用后者；未来联合合同须避免先SHARE后UPDATE或持预算桶回physical。本实验不调用合法预算申请，不声称产品已发生此死锁，只验证拟议复用锁组合风险。追加方案首次系统python解释器报编码错误、未写文件，本次使用已登记Python3.11完成。

### 本轮锁合同修订与限制

SHARE→UPDATE试验原生40P01，一方rollback另一方commit，独立回读epoch1；共同快照试验最终3case各1义务，原产品AgentRun/容量/事件均0，模板未新增probe schema。verify_lock_probes.py明确区分即时等待/SQLSTATE证据与独立持久状态证据。

联合锁前缀必须按最终强度预锁原费用fence UPDATE，避免read_formal_budget_fact SHARE再升级；同预算多account共同fence须在physicalAccount之前统一取，普通/Eval原内核后续重入不得反向取得新锁。还须完整预锁原head/member/proposal/Price/currentness并核发布/撤回writer一致顺序。共同physical guard每次申请/释放/导入写version，不能仅advisory或不更新FOR UPDATE当快照刷新。此为需原入口实测的设计约束，不宣称所有writer已冻结。

剩余交付：完整传递锁图/对向writer、两token模式、零执行旧义务导入与完整映射、合法Skill/Logic/ModelRoute/Task、ordinary/Eval+Source+预算+一次Intent实际COMMIT/rollback。本证据检查点不关闭父Task、不改变业务gate、无正式数据库/服务/外部执行。

旧ordinary/Eval仍在桶后取fence UPDATE。新入口若先fence再桶，与未切换旧writer会形成相反顺序。因此fence前置不可单独上线：全入口共同切换或明确禁入旧writer必须先在零执行窗口完成，并真实并发证明。未完成前新joint入口保持禁入；不改变旧正常算法以伪造共同合同通过。

## 固定窗口完整新Source原生反例

新增fixed_window_probe.py、run_fixed_window_probe.py、fixed-window-r1.log、fixed-window-counterexample.json。插件在原fixture前包裹_distinct_native_fact_material，原API新create_basis→propose→原checker decide，更新待签资料的token模式/窗口/anchor并由原actual_command签出；不改已存批准payload，不伪造批准hash，不重发旧attempt。接续原完整prepare/commit/current Source consumer，再在同真实SCRAM/SERIAL/runtime caller调用旧池内核。两个真实Provider池各1预留，token quantum取签名maxTokens//2+1，合计超上限而concurrency2不超过签名上限2，DB clock开始结束确认处于同anchor/window。观察提交前0、实际COMMIT后2rows/2events及AgentRun0/canary0，再继续原epoch/Owner/撤回负门，所有实验库保留。Route/Model DTO仍synthetic，不能称合法业务运行或已发生实际token支出，仅证明固定窗口预留联合上界缺口。独立回读原签名窗口/hash/physicalProvider映射和持久预留必需；窗口滚动/释放/unknown语义还需未来账本完整验证。

### 固定窗口结果与共同账本约束

完整原Source/occupation原test1PASS/8warnings50.90s；通过新basis/source原maker/checkerAPI与原签名生产链签出fixed_window_rate Source。两真实Provider旧pool在同一实际caller/同DB clock窗口预留20002token，签名上限20000，request2未超并发2；未提交observer0、提交后2rows/2events。原epoch/独立Owner/撤回负门继续通过。独立只读verify_fixed_window.py复核签名/hash/窗口参数/账户3Provider/两池每10001/持久计数/角色归还/epoch2撤回，AgentRun0/canary0。原实验两个随机完整迁移数据库保留；Source已撤回，不重新准入或重发。

计額模型不得混同：inflight_upper_bound累计未settled/reconciled义务，与deadline/Source撤回/窗口滚动无关；fixed_window_rate同时保留并发inflight义务与以签名anchor/seconds、DB clock计算的窗口token上界。prepared/held必须按窗口预留，submitted/unknown不得回退已计rate；取消仅能凭未提交不可变Receipt释放该prepared预留。旧pool release/expired事件不是未发送证明。signedSource revision变更或anchor/seconds变化必须有完整旧窗口/未决义务映射与零执行切换，不可借新revision初始化满额度。实际Usage未知保留upper bound，settlement/reconcile是否返还rate须正式语义和Receipt，不靠经验猜测。

当前两种模式的原生反例已齐，未实现joint writer/窗口滚动/全入口并发或合法业务；下一完整共同账本仍须Source currentness+shared account版本序列+原budget+一次Intent，并在过时快照时整事务终止/结果对账后重建全部校验，不透明重发。父合同尚待完整传递锁图及旧active/unknown切换权威，不关闭。

## 下一步：旧义务精确映射只读盘点

新增cutover_inventory.py／cutover-inventory.json。只读三个已登记保留反例库（Source并发、固定窗口、legacyTTL），按原reservation.pool_revision连接精确旧pool Provider id/revision/hash，再与真实global_provider/global_account及签名Source完整Provider refs匹配；检查实际AgentRun是否存在、native clock已到期与event状态。Provider id映射不是精确revision/hash权威，需signedSource原引用共同匹配。输出只为保守导入合同：撤回Source、TTL或expired不产生零效果Receipt，未映射或无真实运行来源不能清零。实验本身没有合法AgentRun，不拿这些行伪称真实业务unknown历史。所有连接SER READ ONLY、无角色/数据/效果更改。

## 共同账本独立Owner的原Source窄桥权限验证

新增owner_bridge_probe.py、run_owner_bridge_probe.py、owner-bridge-r1.log、owner-bridge-verification.json。仅完整原Source测试的新保留随机库中，由已登记隔离admin安装随机test-owned桥函数与NOLOGIN/NOINHERIT/无membership专用ledger-probeOwner。新桥函数由原SourceOwner持有，只调用原public.read_capacity_source_for_occupation，仅grant新probeOwner；新Owner持有的外层test入口只grant aos_runtime。不改变原reader/auditor/privateSource/41表ACL、旧Owner权限或角色成员关系。专用occupation SCRAM/SERIAL/runtime实际caller→probeOwner外层→SourceOwner窄桥→原完整reader，相同xid/pid，正向解析exact signed Source并继续原epoch/Owner/撤回测试。新Owner无Sourceprivate/table/C verifier/direct originalSourceRPC权限，正常admin/runtime但非专用session调用与错误JWT/ref拒绝。最后仅DROP此次test-owned函数，保留NOLOGIN无权限角色、所有库数据/备份；不能称joint ledger实现/正式权限批准。完整native验证后才能冻结此候选角色桥，不照客户端DTO转授Source当前性。

首轮r1正向读已完成，负JWT在原_consumpion_packet客户端verify阶段ApiError，探针错误把它期待为SQL失败，整体1FAIL/7warnings37.93s。原Source调用ACL未改，test-owned函数finally清理；独立只读核失败库bridge/entry0、probeRole惰性，库保留。原consumer packet只含已核JWT claims、无签名，因此未来联合client必须原样保留客户端JWTverify，不能声称SQL单独验证JWT。修正记录client JWT负门，并额外把已验证packet的authenticationExpiresAt置1970直接核native桥TTL负门，再新库运行完整r2；不重发旧Sourceattempt。

### 独立Owner窄桥r2结果

完整原Source distinct test1PASS/7warnings50.07s；实际专用SCRAM/SER/runtime caller→独立NOLOGIN ledger-probeOwner→原SourceOwner窄桥→未改原reader，positive解析Source一致、同xid/pid；原reader/auditor定义及ACL before/after完全一致。独立Owner无Sourceprivate USAGE/SELECT、原RPC EXECUTE、C verifier EXECUTE和membership。原client坏JWT提前拒绝；native过期authentication packet、错误source ref和普通admin/runtime非专用session拒绝，随后原epoch并发/独立Owner/撤回负门继续通过。测试函数finally只删本次owned probe函数，角色REVOKE额外USAGE并保持NOLOGIN、库数据保留。独立回读Source签名hash、epoch2撤回、probe函数0/角色额外grant0/AgentRun0/容量0/canary0，bootstrapSource0。

窄桥解决新Owner不能扩授原Source reader精确ACL的接线问题；它没有实现physical ledger/budget/Intent，不授正式配置/服务/Provider启动权。将来生产桥须固定trusted DDL/hash/SECURITY DEFINER/search_path/完整角色ACL表审计，客户端_consumpion_packet验签前后原样保持。父合同full传递锁/旧义务零执行切换与合法业务链仍pending。旧cutover盘点同时留下5笔精确签名历史映射、4笔无映射旧行，其中2expired仍无零效果证明；均测试行而非合法AgentRun unknown历史。

## 下一步：原生数据库隐式触发器锁边盘点

新增catalog_lock_inventory.py／catalog-lock-inventory.json。仅只读已登记owner-bridge r2保留库aos_test_fc2688b199ad_ti4_test及完整157空模板aos_test_f2ef54f0da1d_ti4_test，核cluster/READ ONLY/迁移头。从实际pg_trigger/pg_proc收集Source私有表、原public预算/费用/Model/Provider/审批与成员表及其递归静态触发依赖；记录函数hash、触发时机/延期属性、静态关系及词法锁事件。动态EXECUTE/控制流/间接function调用均标剩余，词法顺序不称真实运行顺序；不输出函数全文、签名、JWT或业务payload，不产生DDL/数据写入。实际Source reader若原fixture已清理只标缺失，不重装或重发attempt。与当前源hash共同绑定，明确trusted定义比对和原生完整writer竞争仍须后续，不因catalog清单冻结完整锁图。所有库卷备份原样保留。

### 原费用撤回隐式 fence 原生等待验证

新增cost_revoke_lock_probe.py／run_cost_revoke_lock_probe.py／cost-revoke-lock-r1.log／cost-revoke-lock-verification.json。完整原test_real_caller_consumes_once_and_legacy_store_reads的新随机保留库，由原prepared→签名checker decide→专用consumer consume→原store get全部通过后，用同批准的原签名maker revoke经原Issuer执行；另一个实际SER/runtimecaller仅锁原费用fence、不写version或hold，observer核真实pg_blocking_pids。rollback该caller后撤回成功实际COMMIT，独立查看revocation1/fence version+1/issuer receipt，费用/AgentRun/canary零新增。fixture仅原历史Provider producer，无Price bypass/伪造Task/hold，不能称合法完整业务或联合ledger。不得未知结果重发，先核清理/角色/结果。此步骤补实际原隐式writer锁，不改源代码/正式库。

首轮原测试正向已通过，但探针导入包模块与pytest实际模块不同，未捕获approved资料，1FAIL/7warnings7.74s；未进入新撤回，非产品拒绝。仅修正为pyfuncitem.module，失败库ee694e57dab4保留，不对旧批准重发撤回，第二轮新库验证。

独立核验首次把旧费用Issuer误当Source独立Owner而期待membership0；a0v_125原迁移明确GRANT aos_runtime TO aos_budget_cost_issuer，当前原生membership严格NOADMIN/NOINHERIT/SET true，consumer无membership。仅纠正verifier按原角色精确合同核验，数据库不改；不是新增授权。

### 实际触发器和原费用撤回结果

两份完整157库原生只读目录各97相关表/488触发器/94函数；包含Source私有边界动态EXECUTE与原runtime/审批触发器，词法事件仅候选，未覆盖动态完整closure。原reader已由Source fixture清理，目录不重建。费用撤回AFTER INSERT函数aip_budget_cost_revoke_fence_a0v_126原生body与a0v_126 trusted迁移完全一致，SECURITY INVOKER/search_path=pg_catalog，原触发器AFTER ROW INSERT/nondeferrable。

第二轮完整原test1PASS/7warnings7.63s，原checker签名→consumerconsume→storeget后，maker签名原Issuer撤回实际等待SER/runtimecaller持原fence；observer pg_blocking_pids精确证明，未提交revocation0，caller只rollback锁后Issuer实际COMMIT、revocation1/fence1→2/revokeReceipt1。独立只读两个保留库（失败r1 revocation0；r2 revocation1）回读通过，issuer/consumer NOLOGIN，issuer仅原runtime SET membership，hold/AgentRun/capacity/canary0。没有Price bypass/Task伪造/Provider发送/Source重放。记录证明原隐式writer锁边，未证明全joint无循环或完整业务；费用review/member先锁再到fence与未来联合前缀需共同排序。

## 下一步：原 Source 活跃安装的 PostgreSQL AST helper 闭包

新增source_lock_closure_probe.py／run_source_lock_closure_probe.py／source-lock-closure-r1.log／source-lock-closure.json。复用完整原distinct Source测试新随机保留库，在其真实SCRAM/SER/runtimecaller已消费Source后、原epoch/Owner并发负门前，只读admin读actual pg_proc定义，pglast解析PLpgSQL控制流及嵌入SQL AST，递归显式schema函数调用、关系与锁子句，另记动态EXECUTE模板及未解析/多重候选。原compiled reader/auditor expectedbody与当前live匹配；private helper由原Source实际完整auditor校验，不把targetcatalog当期待值。仅结构/hash输出，无函数全文/JWT/签名/参数/业务payload，不执行动态SQL；parse失败和opaque函数明列，不声称全writer无循环。随后原完整epoch/独立Owner/撤回测试原样继续。所有库卷备份保留，不改变Source/Profile产品文件。补本合同动态helper资料，以据实收窄剩余开码条件，不能靠部分parse数量宣布冻结。

AST首轮完整原测试1PASS/7warnings53.38s，调查仅43函数/414嵌入SQL解析失败，主要因为PLpgSQL_expr.parseMode=3赋值表达式含target:=RHS。首轮JSON归档source-lock-closure-r1.json，不拿不完整数据冒称闭包。按libPG解析出的mode仅处理受限固定简单赋值target，0原SQL、2表达式、3严格匹配target:=RHS，其他保留failure。第二轮仍新Source/随机保留库，不改或重放旧attempt。

### AST 独立回读失败诊断与最小修复方案

原完整test已PASS，但verify_source_lock_closure.py期待三个legacy helper均保留，实际exact_public_source_caller外层fixture finally会在内层恢复之后DROP require_current_source_installation()。只修证据verifier：通过原fixture AST确认精确DROP常量，活跃installation定义与occupation可信编译匹配，结束后要求public两个入口及private安装audit三者均不存在；另两个legacy helper按可信恢复编译hash匹配、54其余helper原hash一致。保留全部原测试库/卷，不执行DDL或重发Source。错误属于复核生命周期期待，不认定原产品失败，不放宽任意缺失helper；原完整r2无需因verifier修正重复执行。

## Source 活跃安装 AST 闭包检查点

完整原Source distinct r2测试1PASS/7warnings48.73s，真实SCRAM/SER/runtime消费后只读采集59函数，嵌入SQL解析失败0、显式未解析调用0、实际动态EXECUTE0。词法扫描三个EXECUTE实为ACL字符串；独立synthetic语法正负例覆盖literal/dynamic/lock/assignment，不能当业务证据。public.digest两个重载保守遍历，三个非SQL密码函数仍opaque。7函数含显式锁子句，仅evidence_epoch_lock出现INSERT（缺失epoch时ON CONFLICT），隐式唯一/FK锁仍独立分析。锁子句别名与关系候选不直接等于全部真实持锁对象，控制流结构不是全writer运行顺序。

独立SER READ ONLY复核：54 helper hash未变，两个legacy profile恢复为可信原编译；两个public occupation入口由内层清理，private installation audit由exact_public_source_caller外层finally精确DROP。活跃audit先匹配occupation可信编译，清理来源经原fixture AST核对，缺失不能作当前准入。原Source签名/hash正确、registry epoch2/origin撤回，occupation角色NOLOGIN零membership，AgentRun/容量/普通预算/Eval预算0/canary0。原verifier误期待audit清理后保留，失败未修改数据库，修正仅生命周期断言；独立复核通过。所有实验库卷备份保留。

r1部分AST43函数/414解析失败归档，不抹除失败；r2严格处理PL parseMode=3固定target赋值，非支持语法仍失败透明。此检查点收窄Source helper资料缺口，不冻结完整joint锁图，不实现physical ledger/budget/Intent，不授正式库迁移或业务启动。下一候选是Source发布/撤回和审批/Provider/Price原writer与锁前缀对照，再核旧unknown零执行切换；父Task和完整Goal保持ACTIVE。
