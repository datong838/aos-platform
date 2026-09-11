# 阶段人工决定 Owner 验证

2026-09-11，基线 e8fff35d，AOS-000573。方案 stage-decision-owner-plan.md；文件哈希 stage-decision-owner-files.json。

## 验证

`AOS_DOTENV_DISABLED=1 AOS_TEST_USE_SHARED_DATABASE=1 AOS_GROWTH_DRAFT_FULL_GRAPH_TEST=1 services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/test_ecommerce_analyst_stage_decision_store.py -q`

7 passed，2.02s，退出码0。已有7项告警及退出时 JDBC logging closed-stream 提示。实际一次性 PostgreSQL 克隆应用012→013→014；覆盖并发幂等、冲突、外层回滚、撤销后旧当前决定拒绝但历史可读、租户隔离、runtime权限、历史UPDATE/DELETE/TRUNCATE拒绝，以及身份/hash/目标/时间/初始撤销拒绝。

## 一致性与限制

Owner 复用事务包装和回执，只有外层提交。固定目标单head，历史读取不能充当当前执行授权。迁移显式撤回默认权限，revision无UPDATE，主库未应用013/014。与方案一致。

尚未核验真实评审人的当前职责、当前Eval和业务产物；没有业务API、自动续跑或真实首链成功证明。下一波补正式评审来源与职责核验，再接宿主评审命令。真实数据连接与事实质量/对账缺口仍保留。
