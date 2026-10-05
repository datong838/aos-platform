# 完整 evaluator 必要的 Capacity / Budget 锁序验证

2026-10-05，基线 ea110644 / Authority1339；沿完整 evaluator 实施 Task（18:00）。本段不关闭该 Task。

## 原缺陷与最小修正

原 ContentBudgetCommandOwner 在同 HostTransaction 先持 Capacity head SHARE，再 require_cost_risk 取得 Budget fence UPDATE。原完整评估拟 Budget SHARE → Capacity UPDATE 会互相等待。新私有 `_prepare_formal_capacity_head` 在 native SCRAM / SERIALIZABLE / 固定 evaluator 身份下严格重新解析 Capacity exact ref，先取得原 pool head UPDATE，核验 current_revision/version。它不授予容量许可、不读成假 READY、不预留、不过期、不消费；完整命令仍须核验原正式池内容和占用。

范围仅 evaluator、其 PG 测试及已登记实施文档。原 content writer、Budget require_cost_risk、迁移/ACL和当前库未改。初始 Binding 行锁与全图剩余检查已在 composition-plan 标明，Source/Owner/Installation、ModelEval、Budget配置/发行、Capacity reserve/publish、ModelRuntime和Health锁模式已逐边复核；未把 SHARE/SHARE的顺序不同误报成死锁，亦未宣称全图闭合。

## 实际证据

- RED：两事务测试旧逆序 1 passed，新顺序缺预锁入口 1 failed（ImportError），10.02s。旧逆序实测双向 pg_blocking_pids 并由 PostgreSQL 报 DeadlockDetected；不是业务八facts正向RED。
- 最小实现：同两参 2 passed，9.40s。
- 相邻：formal evaluator PG、strict contracts、native evaluator connection，111 passed，36.59s；含原 Health/来源/费用/ACL 与新六项身份、scope、strict revision和current head负例。
- 最终证据补全：锁图与六项负例 8 passed，9.71s。保存 native SCRAM、实际 backend PID、双向等待/单向等待、六表计数、Budget fence与Capacity head revision/version；前后相等。
- `py_compile`、精确路径 `git diff --check` 通过。没有UI/路由变化，本段浏览器不适用。

日志：capacity-budget-lock-red.log、capacity-budget-lock-green.log、capacity-budget-adjacent-green.log、capacity-budget-final-green.log；实际图见 capacity-budget-lock-budget_first.json / capacity-budget-lock-capacity_first.json。只使用5433自动销毁 aos_test_*_ti4_test。Budget来自原正式Provider与HTTPS签名原批准/激活/配置；Capacity head明确是协调探针，没有revision，不可能形成正式Capacity事实或proof。两端回滚原fence version写入，未生成任何原评估三写。

## 未完成

完整 `evaluate_binding_in_transaction` 仍缺失，实际正式Capacity正向、非空八facts、Source/Owner/签名安装/预算整合、原CAS/Receipt/proof同caller三写实际COMMIT、幂等重验、错误/过期/并发回滚及正式产品API/ToolBinding继续待验。不得把本段更名为整波GREEN或自然首链。当前142真库只读、Host/worker/Provider仍未获得业务启用授权；独立督导429阻断保留，不阻止本安全代码施工。下一步立即回完整命令，而非新建辅助机制任务。
