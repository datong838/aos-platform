# W5c9n 补订｜pytest 全局夹具造成隔离测试库迁移

RED 测试 `1 failed` 于预期的 `include_in_schema` 后者仍 true，但 pytest 自动加载 `services/aos-api/tests/conftest.py` 中 session autouse `_isolated_postgres_database`，在专用 test VM 的 127.0.0.1:5433 创建/迁移一次性 `aos_test_*` 数据库。这超出原计划“无 DB 测试”，故立即暂停编码，查明后才续。该夹具有 finally drop；专用 `aos-a0v-test-pg` 中 `aos_test_*` 现计数 0。真实 `aos-a0v-recovery-pg` 仍独立唯一真实 PG、8080 离线、18181 原纯 HTTP 存活。未读商城源。

后续所有本波专项/累计针对新测试文件均加 pytest `--noconftest`；此文件不使用全局 fixture，验证仅导入 app、读取路由表/schema，不进 lifespan/DB/端口。若需要执行依赖全局夹具的旧累计测试，必须另立隔离方案，不在本波偷跑。先在无夹具 RED 复现，再改两个 decorator、GREEN；逐步确认专用测试库仍 0。原方案其它安全边界不变。
