# 联合 Owner 接线合同草案：原入口复用、同 caller、未知义务保留

本合同以 m1 56ac78b8、AOS-001475 和本目录原生证据为依据。角色窄桥已在保留隔离库验证，产品 ledger 还未实现；剩余门不因文档存在而通过。完整 231 业务目标不缩减。

## 角色与资料流

专用 occupation SCRAM session 仅 SET 原 aos_runtime，无私有表/Owner membership。原客户端 `_consumption_packet` 完成外部 JWT 验签，packet 是已验证 claims，不是 JWT；原 SQL 检查 native identity、期限、current Owner、精确 Source、原批准/Provider/Evidence/root/registry。不得公开客户端构造 claims 的捷径或把 SQL 称独立 JWT 验签器。

新独立 physical ledger Owner 应 NOLOGIN/NOINHERIT、无 membership/CREATEDB/CREATEROLE/SUPERUSER/BYPASSRLS，仅持新私有 schema。其窄 Source 桥由原 SourceOwner 持有、固定正文、search_path=pg_catalog，只委托未改变的 `read_capacity_source_for_occupation`，桥仅授新 ledger Owner EXECUTE。外层联合入口只授原 runtime。新 ledger Owner 不授原 Source 私有表、原 Source RPC 或 C verifier。所有生产表、函数、ACL、触发器与角色形态必须按 trusted 编译产物审计，不从目标 catalog 反推“期待值”。

原生 prototype 实际证明上述两层 SECURITY DEFINER 能保留 caller xid/pid，原 Source reader/auditor 定义 ACL 不变；错期限/ref/非专用 session 原 SQL 拒绝。prototype 无 production ledger 数据写入，未来生产桥与新 Owner 的正式身份仍需独立安装验收。

## 同 caller 原子协议

1. 从原批准、Source、当前 Model/Route/Price/配置/安装身份发现精确输入，保护完整原权限锁前缀，按最终强度预持费用 fence UPDATE。发现数据不是准入。
2. 取稳定物理账户 guard 并实际更新共同 version；旧 SERIAL 快照在此拒绝。独立 advisory 或不更新 FOR UPDATE 不能当“计数自动刷新”。
3. ordinary 可调用原 `reserve_pool_in_transaction` 保留单池约束；pool/revision 计数永远不能替代 physicalAccount 共同计额。新 ledger 私有 hold 与所有未决旧义务一起核并发/token 上界。
4. 回到同原生 connection 的 runtime caller，复用原普通 `reserve_in_transaction` 或 Eval `hold`。保持原真 Task / 一等 Eval request、原 checker/Price/三桶/current cost risk 语义，禁止伪 Task/AgentRun 或另开连接。
5. 联合 finalize 核全部精确绑定，持久写同一次唯一 Intent。caller 自己执行实际 COMMIT；capacity/budget/Intent 任一失败整体回滚，函数返回不能冒充 COMMIT。
6. 实际 COMMIT 前还须守期限和当前性；需要原生 deferred/等效数据库门和并发撤回证明，不能只检查 Python 返回前时间。发送权限来自独立正式门，Source 的 execution_allowed=false 仍只授非执行资料。

上述序列只定义所需协议，不代表现有独立 Content claim/start/ack 已合并。Intent writer 与预算 finalize 的精确权威校验、一次性身份和 deferred 门尚未实现。private ledger 不能信任 caller 传入的 Source DTO、budget Receipt 或“READY”标签。

## 额度与旧义务

物理主键是 server physical_account_id，跨 Provider、pool、revision、用途共同计数，继续保留租户所有者。仅 Provider id 关联不够，旧行还需 pool 精确 revision/hash 与签名 Source Provider refs、全账户映射及真实执行来源。

inflight_upper_bound 保留所有 held/prepared/submitted/unknown 未决上界；TTL/Source撤回不解除。fixed_window_rate 同时保留并发义务和签名 anchor/seconds 定义的窗口预留/支出，使用 DB clock；submitted/unknown 不因窗口滚动返还。新 Source revision 或窗口定义变更不得清零旧义务。

旧 reserved/consumed/released/expired 不能直接决定余额。仅不可变未提交证明、结算或正式只读 reconcile 可做幂等解除；不明映射或不明结果应保守保留/拒绝该账户新准入，禁止删除记录、清库或重发。当前所有盘点行是隔离 counterexample，没有合法 AgentRun；不可据此声称业务历史切换已验证。

## 全入口切换与剩余开码门

当前 ordinary/Eval 在预算桶后取原费用 fence，联合序列若 fence 前置但旧入口混跑，会有相反顺序。先零执行窗口、全入口共同切换或明确禁入旧 writer；再证明真实 opposite-writer 等待/无死锁。Source 发布/撤回、Model/Price/head、审批与成员 writer 的完整传递锁图仍须逐项核对，不以静态 AST 代替动态 SQL 与原生竞争。

拟议文件为 `aos_api/aip_physical_capacity_occupation.py`、追加迁移、完整 `tests/aip/test_physical_capacity_joint_pg.py`，再接 AgentRun、Eval、Content 原入口；这些产品文件尚未取得本 Task 的代码 Lease，不能偷偷开码。原 Source/profile dirty Scope 亦不纳入本 Task。

下一验收必须同时覆盖：两 token 模式、same caller COMMIT/rollback/replay、不同 Provider/pool/revision/ordinary/Eval 共同上限、真实并发与过时快照、等待后和实际 COMMIT 期限、旧 unknown 导入/零执行切换、合法 Skill/Logic/ModelRoute/Task 创建链、一次 Intent、原功能相邻与租户零副作用。正式数据库迁移、服务重启、自然首链、八工作台、连续观察与发布仍走 231 后续门。

## 原费用撤回隐式 writer 边补证

2026-10-07 原生catalog盘点（完整157 retained库）及cost-revoke-lock r2补证：原BudgetCostIssuer从REVIEWER member SHARE→budget-cost-review advisory→撤回 INSERT→AFTER ROW INSERT的aip_budget_cost_revoke_fence_a0v_126 UPDATE原fence。触发器body独立核对a0v_126 trusted迁移完全相同。实际签名checker/consumer/get原测试后，同批准maker签名revoke对SER/runtimecaller持有的fence真实等待；caller rollback后原Issuer COMMIT，fence1→2/revocation1/receipt1。这里的caller仅持锁，不是联合ledger caller，也没有budgethold/Intent。

原费用Issuer角色不同于SourceOwner：a0v_125要求仅原aos_runtime SET membership（无ADMIN/INHERIT），consumer无membership；不得因新Owner零membership设计而误改旧Issuer原身份。原Source reader清理由fixture完成，catalog无该入口不授重装/重发。此native边证据不能把完整锁图标GREEN；新联合Owner仍须预持并复验review/member/currentness与最终强度fence，核两方原writer对向路径，不凭词法事件猜全序。catalog_lock_inventory明确dynamic EXECUTE/helper call和控制流尚未闭包。

## Source 活跃安装 AST 闭包检查点

完整原Source distinct r2测试1PASS/7warnings48.73s，真实SCRAM/SER/runtime消费后只读采集59函数，嵌入SQL解析失败0、显式未解析调用0、实际动态EXECUTE0。词法扫描三个EXECUTE实为ACL字符串；独立synthetic语法正负例覆盖literal/dynamic/lock/assignment，不能当业务证据。public.digest两个重载保守遍历，三个非SQL密码函数仍opaque。7函数含显式锁子句，仅evidence_epoch_lock出现INSERT（缺失epoch时ON CONFLICT），隐式唯一/FK锁仍独立分析。锁子句别名与关系候选不直接等于全部真实持锁对象，控制流结构不是全writer运行顺序。

独立SER READ ONLY复核：54 helper hash未变，两个legacy profile恢复为可信原编译；两个public occupation入口由内层清理，private installation audit由exact_public_source_caller外层finally精确DROP。活跃audit先匹配occupation可信编译，清理来源经原fixture AST核对，缺失不能作当前准入。原Source签名/hash正确、registry epoch2/origin撤回，occupation角色NOLOGIN零membership，AgentRun/容量/普通预算/Eval预算0/canary0。原verifier误期待audit清理后保留，失败未修改数据库，修正仅生命周期断言；独立复核通过。所有实验库卷备份保留。

r1部分AST43函数/414解析失败归档，不抹除失败；r2严格处理PL parseMode=3固定target赋值，非支持语法仍失败透明。此检查点收窄Source helper资料缺口，不冻结完整joint锁图，不实现physical ledger/budget/Intent，不授正式库迁移或业务启动。下一候选是Source发布/撤回和审批/Provider/Price原writer与锁前缀对照，再核旧unknown零执行切换；父Task和完整Goal保持ACTIVE。

## 实际 writer 递归 AST 隔离版本检查点

pglast上游issue205（https://github.com/lelit/pglast/issues/205）记录8.x trigger malformed JSON；原8.4最小control及实际39trigger失败归档writer-lock-candidates-r1.json。专属.parser-v7固定7.18/专属.cache，独立进程不改API依赖；第一次uv cache路径已存在非目录，安装未开始，改专属cache后成功。原API parser8.4仍回读确认。只读同r2保留库的原catalog94候选递归显式helper→101函数/29候选交集，parse失败0/未解析显式callee0/已覆盖动态语句0；digest2重载保守解析，3 C函数opaque。独立回读101actual bodyhash与触发器关联、业务计数0，Source原hash相同54helper的操作序列全部相同；16函数control_flow_path因版本block wrapper不同，明确不宣称完整控制流树相等。所有库卷备份保留，版本包不纳入交付Git。

原native cost revoke已证实的隐式UPDATE现在可从actual trigger AST对应aip_budget_cost_runtime_fence；withdrawal bump为epoch INSERT/UPSERT而非显式locking clause，必须连同FK/unique/AFTER顺序审计。Provider健康touch为epoch条件INSERT→FOR UPDATE、bump为UPDATE，实际before/after/truncate关联已记录。Source59闭包不读取health epoch或cost fence，未来joint入口必须组合原健康配置及cost当前性门，不能当作Source已涵盖。

本调查仍只涵盖catalog给定范围与显式schema调用，未证明Python动态writer/所有SQL入口/隐式内核锁或实际运行总序；DML关系候选包含join读关系，不等于精确写对象。新的原生对向验证应按合同补Source批准撤回epoch链与联合健康/费用顺序，旧未决义务零执行切换与合法业务链仍pending。父合同/Goal ACTIVE，无完整业务完成或正式权限新增。

## 原撤回API实际writer双等待检查点

新完整原Source distinct fixture先完成实际SCRAM consumer与epoch/Owner/Origin负门。通过原propose_provider_capacity_source与原checker decide另建相同原Source Candidate的独立批准proposal，不修改旧批准/候选；原maker JWT→原withdraw HTTP router→原service/store，单次新request先等待proposal SHARE holder，释放后同API backend再等待epoch SHARE holder，原withdrawal INSERT/AFTER UPSERT仍未提交时observer事件0；释放epoch后原API HTTP200及实际COMMIT，proposal v2→v3 withdrawn/epoch0→1/withdrawal1/actionevent1。完整原test连同fixture清理1PASS/7warnings52.96s，库aos_test_384992d717f4_ti4_test保留。

独立SER READ ONLY核新proposal/event/maker/version/epoch和原Source引用proposal仍approved v2/epoch0，Source签名/hash有效但Origin已按原test撤回；occupation入口清理、角色惰性/无membership。actual bump body与a0v151 BUMP_BODY精确一致，原AFTER ROW INSERT、FK非延期且名称排在bump前；业务AgentRun/普通预算/Eval预算/容量0/canary0。没有direct INSERT撤回或手动increment epoch，isolated holders只是锁primitive，不能冒充joint consumer；独立提案不是已发布Source exact ref，未测试app lifespan/正式API部署。

r1等待观察未成立且撤回原fixture提案导致teardown再验失败（1FAIL+1ERROR）。只读库aos_test_6ed054c786b4_ti4_test确认实际withdrawal已COMMIT v3/epoch1、业务0/无活跃连接，结果对账记录保留、不重发。r2刷新pg_stat统计snapshot并换新独立批准proposal/新全fixture；不改旧库来清除失败。所有库卷备份保留，Source/Profile产品dirty和正式服务未改。

补齐原writer边withdrawal advisory→proposal UPDATE→draft UPDATE→withdrawal INSERT/原FK→AFTER epoch UPSERT→event→COMMIT。它与未来Source proposal/epoch预锁排序相符，仅reader-first两阶段锁primitive证明；writer-first staleSource消费拒绝和完整joint所有入口尚需后续实际证明。父合同仍pending/ACTIVE，Goal active、业务gates保持。

## 原撤回API writer-first与原事实prefix旧快照检查点

新完整原Source distinct测试及全部cleanup1PASS/7warnings51.94s。exact_public_source_caller正常finalizer先删public临时入口并恢复其原有harness grant，再由test post-finalizer使用仍存活的原专用SCRAM/SERIAL Issuer调用原publication_facts_harness→未改read_original_source_facts；未新授任何权限/新建桥。原maker/checker另建独立批准提案，精确新proposal/approval hash正向prefix读取成立。rollback后原reader164291建立旧snapshot；原maker signed API164582先持proposal等待独立epoch holder164557，reader再等待API proposal锁，未提交withdrawal0；释放epoch后API HTTP200/实际COMMIT，新proposalwithdrawn3/epoch1。旧snapshot prefix失败40001；新事务同精确ref失败P0002（原可信SELECT INTO STRICT当前性）；不重发API或重建旧外部attempt。

独立SER READ ONLY核新事件1/新提案3/epoch1、原Source引用提案仍approved2/epoch0、Source签名hash有效及Origin撤回；原Sourceprefix body精确匹配可信CAPACITY_ORIGINAL_SOURCE_FACTS_SQL、bump精确匹配a0v151 BUMP_BODY，原fact/signed harness全部清理、occupation role惰性零membership。AgentRun/普通预算/Eval预算/容量0/canary0，库aos_test_bf39f06c471f_ti4_test与bootstrap aos_test_4ef0e3d90cc0_ti4_test均保留。

该测试的目标是原Source fact prefix与真实withdrawal writer；新独立提案不是已发布Source exact ref，不覆盖完整签名occupation Source准入、joint ledger、合法AgentRun或app lifespan。即时wait/SQLSTATE证据归本次执行，独立持久回读不冒充过去阻塞观察。父合同/Goal保持ACTIVE，业务gates不变。原Source proposal/epoch有序边现在有实际reader-first原API提交及writer-first过时snapshot终止证据；费用fence/物理guard/预算桶/Intent全入口共同序列和旧unknown切换仍需完整联合门。

## 原occupation读取后 JWT 自然到期实际COMMIT检查点

r2 fresh完整原distinct test 1PASS/7warnings52.25s，实际SCRAM/SERIAL/runtime caller读取exact signed Source成功时DB clock未越JWT期限；保持同xid/pid自然等待过期后一次实际COMMIT返回IDLE。新事务同JWT被原consumer拒绝、fresh JWT正向恢复，随后原epoch/Owner/Origin负门和清理通过。r1证据查询错Eval表名1FAIL，库只读对账业务0无活跃连接、冻结失败脚本/log，r2新全fixture无重发。

该结果证明仅调用原当前非执行事实读取不会在实际COMMIT自动重新验JWT期限。原consumer仍遵守其返回时非执行资料契约；联合ledger finalize必须把deadline/currentness精确绑定到本次hold/Intent，实际提交门不得只检查Python返回前。无需修改原Source只读接口来伪造发送权限。独立回读aos_test_15623fde18e6_ti4_test签名hash/可信原facts body/完整cleanup/角色归还/业务canary0通过；即时clock与COMMIT证据不由持久row倒推。完整joint/合法AgentRun/旧unknown切换和正式业务首链仍pending。

## deferred提交期限门不能仅依赖INITIALLY DEFERRED

隔离原生4case证明早SET CONSTRAINTS IMMEDIATE会清空检查队列，切回DEFERRED无新DML也不重新排队；这两case在deadline后COMMIT仍持久1row。默认deferred和重新UPDATE排队则实际COMMIT23514整事务回滚。另4case只以pg_catalog.current_query()='COMMIT'限制test-owned gate：live canonical COMMIT成功，late canonical COMMIT/早SET/END均23514及row/audit全回滚。独立回读两新库exactbody/trigger/8case/audit时间/product0，原Source/evaluator/正式身份没有修改或绕过。

因此新ledger实际提交门需要受控结束通道；current_query候选只是可行性资料，协议/多语句/全部结束方式、之后其他trigger及等待跨期仍须原生完整证明。COMMIT内最终检查与物理WAL flush完成时限必须区分，不能虚称物理时限。原Source finalized trigger只保原子资料finalized，不能当JWT实际COMMIT期限门；不得为此冒改其现有Scope。fulljoint与合法业务链仍pending，Goal active。
