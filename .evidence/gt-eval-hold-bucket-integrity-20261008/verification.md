# Eval 已有预留共享桶一致性：验证与交付边界

Rules：231八步、先方案/原生RED/精确Task-Lease后最小产品修复；m1单写、正式库只读、不push、不部署、不改Goal。Task gt-eval-hold-bucket-integrity-20261008，产品仅 aip_model_eval_budget_reservation.py，新增16行已有hold只读关联核验。

原HEAD a7935cc9实际native RED：独立新随机全迁移测试库，原隔离模型/费用来源、申请与原maker/checker批准；先原hold形成完整行并ROLLBACK，再runtime INSERT准确完整hash行但无3桶/link，原hold DID NOT RAISE。反例窗口ROLLBACK，回读该申请hold0，Provider0。原证据在父Task eval-hold-bucket-native-red.log/json/rollback.json，不改旧claim。

最小修复：保留完整stored/expected hash与所有原审批/费用/tenant门；已有hold返回前查询原3links与精确FK对应budget buckets，核count3、各reserved=upperBound、currency、正确request task账号及当前BudgetRevision daily/pilot账号、held>=本关联金额。PK保证三种bucket各至多1。无新增锁、扣款、DDL、迁移或历史行修复；新hold分支算法未改。使用原关联period，不按今天重算历史hold，不将跨日合法重放误判。

native r1失败为测试准备UPDATE漏version递增，原 guard_ar2_budget_bucket_update 拒绝，未到held不足门。finally连接ROLLBACK。随后独立SERIAL READ ONLY核4表0/exposure0，保留failed-attempt-independent-readback.json与r1输入。修正测试 UPDATE同时version+1和clock_timestamp，使用全新随机库/独立r2 claim，不重放未知事务。

native r2 1 passed/无skip，13.92秒/7既有警告：原准确hold/replay保持同ID仅1行；在测试回滚窗口里已有3links却held降为0时拒绝；准确hash仅hold而无links时拒绝。全部预算窗口ROLLBACK，源申请/审计和随机数据库保留。独立readback四表（Eval hold/link/AgentRun/Modelcapacity）0，bucket held+submitted+unknown总敞口0，精确cluster7693564235776004128。相邻50 passed/无skip/7既有警告；py_compile及diffcheck通过。

自审：bool_and空集合NULL明确拒绝，缺link或FK对应桶导致count不足拒绝；query参数化tenant/reservation/currency/accounts；预算桶主键/FK精确join，不加锁改变原成本锁序。已有hold只读不重扣。当前汇总held充足只是本关联可见余额一致，不证明所有风险账本/唯一Intent/Source原子授权；仍须联合Owner全局核验。数据异常只拒绝，不自动清账/恢复。

浏览器不适用（无UI修改）；未独立模型review，不称PASS；固定测试身份/隔离签名不是正式Provider或经营授权。包装器scope旧bridge模板不作完成依据，真实nodeid及本记录明确范围。当前API仍旧快照，未部署。此小修复收口不代表父联合准入、完整Model/Route执行或自然首链完成。
