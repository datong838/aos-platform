# BG00FZ verification — original maker and read-only budget recovery

## 结论与范围
代码原actor消费/只读历史Receipt/私有一次attempt核心 GREEN；正式系统恢复/首链 PENDING。a0v127只在conftest独立aos_test_*_ti4_test库全迁移；当前真实数据库本波未连接/迁移/写/重启，Host/worker/Provider未启。无UI改动，browser不适用。

## 命令及结果（cwd services/aos-api）
- RED `.venv/bin/python -m pytest -q tests/aip/test_budget_consumer_service_pg.py --tb=short --show-capture=no`：exit2缺service模块。
- 隔离candidate `.venv/bin/python -m pytest -q -s tests/aip/test_budget_consumer_connection_pg.py::test_isolated_migration_manifest_candidate --tb=short --show-capture=no`：exit1，127新函数与126 manifest不符；审阅后更新，非部署库自采。
- 首轮 service/connection/cost_consumer：43passed/27.08s，exit0。
- 累计 `.venv/bin/python -m pytest -q tests/aip/test_budget_consumer_service_pg.py tests/aip/test_budget_consumer_connection_pg.py tests/aip/test_budget_cost_consumer_pg.py tests/aip/test_budget_cost_preflight_pg.py tests/aip/test_budget_cost_issuer_pg.py tests/aip/test_network_consumer_service_pg.py --tb=short --show-capture=no`：80passed/42.93s，exit0。
- 增加同请求并发后最终service专项（同RED命令）：15passed/16.91s，exit0。
- compileall连接/service/迁移 exit0；alembic heads `a0v_127 (head)` exit0；精确staged diff检查exit0。

## 具体证据
真实低权限LOGIN和TLS签名JWT：maker一次消费、重复原Receipt、批准撤销后历史仍可读、Head/Provider变化不妨碍历史、当前maker失权拒绝、checker/错hash/跨租户/过期或错签JWT写前拒绝且不落attempt。消费者不可直接执行126，inquiry只允许READ ONLY。Receipt全结果损坏返回conflict无新激活。
已有或损坏marker且无Receipt只unresolved不重发；模拟真实commit之后丢回执，write计数1并读回observed；两个并发相同请求只一次SQLwrite，最终Receipt1/active1。故障注入只包裹真实PG响应，不替代业务执行，也不是正式实例验收。

## 复审
127仅新增3函数、撤销caller直接126EXECUTE。126body及15表catalog逐项未变；snapshot新增actor/consume/reconcile后16函数，所有新增body与SQL源一致；manifest SHA256 cffc518fc23980ea7796f2916564ec612cb7237e61e2bdd478729f8ebc011319。
原actor必须原maker当前owner/admin，subject由fresh外部OIDC解析，请求不能带actor/devtoken；scope固化栖月汇。消费复用126算法；read-only STABLE查询不调用消费、不锁业务行、不写状态，以同statement快照比对原批准/Receipt请求hash/完整result/预算payload/fence。observed明确activationEligible=false，只证明历史。
复用O_EXCL+fsync私有AttemptReceipt和正式JWT校验，无HTTP、无自动role provisioning、无环境/共享API回退；stable proposal槽不允许改body换key。当前连接caller仍默认NOLOGIN，生产身份未配置；service核心不等于OS peer隔离的有限进程已部署。

## 下一波
BG00GA有限预算消费进程：复用私有Unix peer/frame/listener，先OIDC/身份/schema预检后有限accept；execute_once/inquiry固定协议，unknown只原Receipt；再接产品自然投递、真实Task预算risk联合证明、合法development价格/预算政策producer和提议UI。正式127切换需当前身份版本实测、一致备份、克隆全链、零执行窗口独立恢复波。每天重启验收不能用本测试替代。旧12Run/商城源/手工run_definition/230L0禁令不变。Goal未修改；Watchdog方案未实施。
