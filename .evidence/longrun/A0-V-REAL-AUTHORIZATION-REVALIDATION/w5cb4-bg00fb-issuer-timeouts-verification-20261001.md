# BG00FB verification — 2026-10-01

## 改动和复审
仅issuer connection增加固定libpq options：statement_timeout 10000ms、lock_timeout 5000ms、idle_in_transaction_session_timeout 10000ms；_require_identity从pg_settings读取整数毫秒严格比较。环境PGOPTIONS仍拒绝，值不由请求/配置传入；connect_timeout原5秒保留。startup设置覆盖首条SQL，并在commit/rollback后保持。原role/scope重绑合同不变，无数据库迁移。

## 真实隔离PG证据
新夹具仅接isolated_owner确认的aos_test_*_ti4_test，临时issuer真实LOGIN且非owner，随机密码仅私有0700/0600passfile；每次finally恢复NOLOGIN/PASSWORD NULL并读回断言，覆盖凭据。无会话身份替身，没有连接当前库。
RED session78975：5 failed/4.54s/exit1；三个超时实际0，超时漂移未拒绝。实现后专项session16873：5 passed/19.16s/exit0。
追加真实idle事务终止及角色恢复回读后累计session92773：56 passed/4 skipped/35.65s/exit0，7已有warnings。包含6项新真实PG用例：reader/writer设置、commit/rollback保持、pg_sleep(12)约10秒QueryCanceled、advisory等待约5秒LockNotAvailable、漂移拒绝与回滚恢复、idle 10.3秒后IdleInTransactionSessionTimeout/连接关闭。取消后身份回读恢复，无自动重试。

```sh
services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_network_issuer_timeouts_pg.py services/aos-api/tests/aip/test_aip_network_issuer_connection.py services/aos-api/tests/aip/test_network_issuer_process.py services/aos-api/tests/aip/test_aip_network_issuer_service.py services/aos-api/tests/aip/test_network_issuer_client.py services/aos-api/tests/aip/test_network_issuer_application.py --tb=short --show-capture=no
```

旧connection两项与service两项因显式BG00cm clone/proof目录未提供而跳过；没有计为正式审批通过。新超时用例使用当前临时测试PG无跳过。git diff --check exit0。无UI改动，不声称浏览器验收。

## 剩余/下一波
单SQL/锁/空闲上限不等于多SQL业务流程总deadline，也不证明网络失联端到端有界；未知提交仍只能只读对账。当前库/配置/服务未变，正式OS/OIDC、119–122部署与启动载体修复、真实Event/八配置/Owner/Host和自然首链未完成。
BG00FC：复用私有配置读取，补issuer精确JSON、只读数据库身份/超时预检和显式check/serve CLI；默认禁入，不启动当前实例，不创建假正式身份。当前库只读、不读商城源/旧Run/manual run_definition/Provider/230L0，不push。
