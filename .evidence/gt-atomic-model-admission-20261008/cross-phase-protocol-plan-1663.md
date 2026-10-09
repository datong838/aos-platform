# 共同准入与 Target→Judge 跨事务阶段协议

基线 dc4c914d7 / AOS-001663；原 Task `gt-atomic-model-admission-20261008`，唯一原 owner/thread，当前有效 Lease；完整 Task 继续 ACTIVE，无 Delivery。本波 Rules：231、已批准共同终结协议1608、完整风险账本1609、费用语义1610；m1 精确提交，真库只读，Provider/Host/worker 关闭，旧证据/未提交代码不覆盖。

## 候选与本波范围

1. 共同终结器：已有授权与登记，依赖原 Source 可信提交终态、真实 token 计量、每腿费用授权、全入口锁序和最终 COMMIT 拒绝门。缺失事实不能用测试风险1minor、字节长度、提前时钟或可变布尔补齐。
2. Target→Judge 跨事务接线：已有登记与授权，依赖原两预算父行、完整计划、Target 已知提交及可信结果、Judge 当前治理。选择该项的原生阶段调查；不能把纯签名校验正向当 transport/准入正向。

精确新增本目录 `cross-phase-protocol-plan-1663.md`、`cross-phase-native-audit-1663.py`、`cross-phase-native-result-1663.json`、`cross-phase-review-1663.md`。不修改任何产品代码、迁移、数据库原件或旧文件。不启动新的写者。只读现有已归属隔离库，核 cluster/数据库/READ ONLY/SERIAL/原表 xmin 与真实事务状态；所有诊断事务 ROLLBACK，结果文件 exclusive-create。绑定 HEAD、原 proof/hash、当前产品 hash。没有合法 durable v2 whole plan 时明确记缺口，不造持久正向。

## 已有语义：fresh prepare 并非 durable consume

`aip_model_eval_execution_owner.py::validate_original_target_judge_manifest` 明确是必要准备读者，要求原 Target/newJudge 两父预算行 xmin 都等于当前 caller xid，再复核两申请、批准、Rule、费用和期限。这个要求保护原共同准备同事务；不能删掉 xmin 条件以兼容后续 Judge。

`aip_model_eval_execution_authority.py::runtime_target_fact_statements` 与现有 legacy Target reader 要求原 result producer xid 的 `pg_xact_status` 为 committed。两机制属于不同阶段；legacy reader 使用旧 Manifest，不能强行接 v2。原生只读调查须分别证明 committed parent 不属于当前新事务、原 whole prepare xid ABORTED/父行0、当前没有 durable v2 plan/result；不得称这些证明已执行真实 v2 Target/Judge，也不把准备函数称为 bug。

## 后续必须保持的阶段合同

| 阶段 | 来源与新事务要求 | 可授效果与禁止替代 |
|---|---|---|
| P0 原共同准备 | 原两申请/批准/父行新建于同 caller；完整所有 case×purpose 风险义务；原 Source、账户、治理、费用桶与 Intent；所有等待后重读期限 | 仅准备；保留现有 deferred COMMIT 拒绝，直写或提前 SET CONSTRAINTS 不能绕过 |
| P1 原共同准入已知提交 | 原 private immutable complete plan/receipt 与其 producer provenance；精确原两 parent ID/hash、完整 case 集合，提交须有独立已知事实 | 原父只创建一次；durable reader 必须另设接口，不能调用 fresh preparer 再铸父行/重复收费 |
| P2 Target 实际派发 | 当前 authenticated executor/Source/治理/批准，P1 精确 receipt、实际原 wire、真实计量和本腿 actual occupation | 原 attempt1 一次派发；未知提交或未知发送只能只读对账，保留风险/占用，不能因 TTL 清掉或自动重试 |
| P3 Target 结果生产与已知提交 | 原 executor 与当前 trusted root/epoch、原 cert、v2 整计划/腿/case、Dataset 与实际 wire/output 两种 hash；private origin 追加不可变，独立 COMMITTED 回读 | 签名 payload/current presented root 不是实际 transport/可信数据库来源；失败/未知结果不可伪造或回放 |
| P4 Judge 晚绑定与再次准入 | 新 caller 原 durable P1 plan/parent、已知 P3 原 result；重读当前 Rule、原 expected bytes、inputProtocol、Judge Model/Source/批准/预算桶；新精确晚绑定 receipt 与本腿 actual occupation | 原 awaiting_target_result Intent 不变；追加 input binding，不重建原 parent；不得把原 producer pid/xid 伪装为当前 caller。来源身份与本次 caller 两组字段分开 |
| P5 已知结算/释放 | 原 real Usage/最终费用与可信追加结算入口；提交/发送/费用未知继续保守持有 | null 费用不是0；完整报告只有所有 required case 真实终态和核验闭合才可 READY |

P1/P3 producer 的 COMMITTED 仅证明事务状态，不证明提交完成时刻符合 Source TTL；原 Source actual-end 缺口仍独立保留。Currentness 判断须在当前调用所有锁等待后用数据库时钟与原 current heads 复核，历史来源 hash 相等不能替代 current approval/撤销检查。SERIAL 旧快照冲突须原生拒绝，不能在同 attempt 私自 repair/retry。表 xmin 只能作为诊断或由原 private origin 窄函数读取，不能作为客户端可提交权威字段；冻结/维护导致来源不可证明必须拒绝，不能重新贴当前 xid。

## 后续文件级实现与退出标准

原 Main scope 的 Owner/occupation 三产品与两 PG 测试可新增独立 durable consumer；typed proof 原 Task scope 的 contracts/test 可新增严格两阶段来源合同。任何 issuer/result 表及 migration 改动须先回读其原 Task/Lease 精确归属；不得夹带既有 untracked reader 整包。全共同终结器尚无正确输入，禁止先接其 grant/DDL。

优先下一步是原 v2 Target result private producer/consumer 的文件级协议：把 v2 cert/case domain、当前 trusted root/epoch、原真实 transport receipt 与 committed plan/Intent/occupation 引用一并绑定；在未具备 P1 真提交前只能做原必要存储负门或隔离原生协议验证，不称业务正向。关键 RED：同事务未提交结果、旧 purpose/domain、仅 presented root、旧/替换 parent、错租户/计划/case、未知 outcome、重复 attempt、撤销或锁等待过期、缺 Usage、提前约束/实际 COMMIT。各阶段均须独立回读原件、保留失败与未知证据，最终以真实授权自然首链验收。
