# BG00FT 预算签发私有连接 verification

基线 AOS-001034 / 221cded6。当前m1，既有browser插件/pnpm锁及两test-only现场文件未动。Task W5CB4-BG00FT-20261001。

## 验证记录
- RED: pytest新 test_budget_cost_connection_pg.py，缺aip_budget_cost_connection模块，exit2，0.41s。
- 首专项：21passed/7warnings/20.71s/exit0。
- 最终累计：`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_budget_cost_connection_pg.py services/aos-api/tests/aip/test_budget_cost_issuer_pg.py services/aos-api/tests/aip/test_budget_cost_proposal_pg.py services/aos-api/tests/aip/test_budget_cost_basis.py services/aos-api/tests/aip/test_aip_network_issuer_connection.py services/aos-api/tests/aip/test_network_issuer_timeouts_pg.py --tb=short --show-capture=no`。
- 结果：111 passed, 2 skipped, 7 warnings in 57.77s，exit0；日志 /tmp/aos-ft-regression.log（临时复核输出，非永久唯一证据）。2 skipped为历史BG00CM专用克隆入口未设置，不当通过；本波22项真实默认隔离PG用例已执行。
- compileall新模块和测试、git diff --check退出0；alembic heads a0v_125/exit0，未新增迁移。

## 复审结论
固定budget专域登录、显式数据库/loopback/私有绝对pgpass，无shared DSN fallback；实际TLS JWT批准/Inquiry/撤销时故意使共享DSN不可用仍通过。factory固定scope/read-only模式，每次重新检查文件权限；拒绝symlink/环境PGPASSWORD等。真实statement10s/lock5s取消后rollback恢复scope；idle10s通过PG设置回读，未另做预算idle超时演练，累计network已有真实idle测试通过。commit/rollback后身份/作用域/隔离级别与超时复验；错误数据库与timeout漂移拒绝。所有新正向登录由测试库角色临时LOGIN+私有随机凭据提供，不是正式身份材料；finally恢复NOLOGIN/PASSWORD NULL。
复用network配置校验器仅限路径/标量校验，不借其登录或批准；现有network代码零修改。既有FS _db复用专域权限校验，无新增审批权、Provider调用或自动重试。commit后回读失败仍可能返回异常，后续只读Inquiry，不重发。

## 未完成与下一步
本波完成FT连接子项，未完成原FT全范围。BG00FU精确schema（a0v124/125表、RLS/权限/函数/触发器/约束）部署预检与独立IPC接线，随后产品原请求持久恢复及受限consumer原子激活。当前真实库未连接/未写/未迁移/未重启；当前live版本不能从旧118快照推断。独立备份克隆零执行窗口恢复另波。Host/worker/Provider未启，商城源/旧12Run/手工Run/230L0无操作。无UI变更浏览器不适用。首链及发布决定未完成，Goal保持active；Watchdog方案尚未实施。
