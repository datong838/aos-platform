# Budget 正式读取施工检查点

2026-10-05，原完整Task保持ACTIVE。本段为完整Task内部施工，不是整波Delivery。

实际原HTTPS JWT独立批准、原budget consume与configure SQL生成BudgetRevision/Price/BudgetPolicy，无price_for或DISABLE TRIGGER正向。native evaluator SCRAM/SERIAL原权限读取；提取原issuer非秘密request hash，旧认证、签发、幂等写逻辑保持。预算原Proposal、批准、未撤回、两当前成员、Provider、Price及精确Budgetpayload/hash/current head、原签发Receipt、有限有效窗和剩一风险量子均核验。共享fence，不UPDATE、不hold、不commit、不重试；原40001不包装。

实际RED：budget-consumer-red.log，1failed/6.02s，原配置已生成后缺read_formal_budget_fact入口。初次正向1passed/7.73s。最终budget-consumer-adjacent-r2.log：79passed/7warnings/75.33s；涵盖正式评估器原测试与原预算issuer/consumer/configuration，以及本次正向、错误hash、Provider漂移、Budgethead变更、成员撤权、批准撤回。实际fence version读取前后保持不变。diff检查通过，测试输入hash见budget-consumer-tested-hashes.json。

仍待：预算consumer实际并发hold/revoke阻塞及旧snapshot40001、canary/独立有效期和风险耗尽；完整Source与Budget联合锁序、八facts组合、原binding-CAS/Receipt/proof实际提交及产品API/ToolBinding仍未完成。当前真库142只读、业务进程关闭。不得将79passed或本reader视为业务READY或自然首链。

## 最终并发与隔离验证

budget-concurrency-r3.log：9passed1failed/18.36s。canary实际已被原身份门BindingEvaluatorConnectionBlocked拒绝，失败为测试预期误设ValueError；仅修正精确测试预期，身份门保持。原hold在实际writer PID上等待reader共享fence；原signed revoke在实际writer PID上等待reader advisory，释放后由原issuer独立提交version+1。hold试验rollback，reader自身仍不写fence。旧SERIAL快照在原issuer提交revoke后读取fence实际原生40001，未包装。

最终budget-consumer-final-r4.log：139passed/7warnings/83.15s，包含上述10个Budget正负/并发案例、原evaluator及strict合同、原Budget签发/消费/配置回归。所有进程terminal后复核测试hash，精确diff-check通过。输出含精确Budget/Price/Provider引用、activationReceipt、issuerRequestHash、proposal/decision/fence/原风险/累计/DB时间，供最终proof组合。无UI变化，浏览器不适用。Prime服务实时running/PID1844/runs1/never exited，仅服务证据，无新增模型调用。

剩余专项：独立有效期、无activationReceipt、风险耗尽、多Source及完整联合锁序、八facts组合、同caller原三写实际COMMIT、产品API/ToolBinding。所有正式身份配置、当前142迁移与自然首链仍独立pending。139passed不能升整体GREEN。

## 原风险耗尽/无回执/独立到期补验

budget-exhaustion-r5.log：12passed/20.68s，新增strict不存在Budget无activation立即拒绝、原require_cost_risk逐个风险批准后原结构ledger maxRequests个holds已提交，正式reader拒绝额外量子。ledger为隔离风险输入，无Provider执行。budget-expiry-r6.log：1passed，原prepared(window8)及signed批准/consume/configure，先native正向，再按DB clock等待原deadline后拒绝，未注入caller时间或改immutable期限。最终budget-consumer-final-r7.log为本段稳定测试输入累计；完整Task仍ACTIVE。本段无新增runtime代码，完整命令组合计划见composition-plan.md；不得以分段读取替代自然首链。
