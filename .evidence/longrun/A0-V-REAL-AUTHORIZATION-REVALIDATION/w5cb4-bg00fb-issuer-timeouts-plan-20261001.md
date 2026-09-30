# BG00FB 签发连接耗时约束计划

基线AOS-001016/m1@b2273325；复习231/409、issuer connection及consumer真实隔离登录夹具。Task W5CB4-BG00FB-20261001；真库只读，不启动当前issuer。

## 最小实现与文件
- services/aos-api/aos_api/aip_network_issuer_connection.py：固定libpq startup options，statement_timeout=10000ms、lock_timeout=5000ms、idle_in_transaction_session_timeout=10000ms；覆盖第一条scope/identity SQL并跨commit/rollback保留。环境PGOPTIONS仍拒绝，不接受请求/配置覆盖。_require_identity读pg_settings整数毫秒核验；漂移拒绝。
- services/aos-api/tests/aip/test_network_issuer_timeouts_pg.py：只用isolated_owner确认aos_test_*_ti4_test；私有0700/0600随机临时passfile、临时issuer LOGIN，结束恢复NOLOGIN/PASSWORD NULL并覆盖凭据。真实reader/writer身份与值、commit/rollback保持、SQL pg_sleep取消、advisory锁等待超时与事务恢复；不使用session_user替身。

## 验收顺序与边界
先RED核验默认无限值不符，再实现；隔离PG专项与原连接/进程/服务及客户端相邻累计；不把跳过旧外部proof目录的用例计为真实通过。文件级复审/verification/精确提交/Delivery/CAS与Prime回读。
这些是单条SQL、锁等待和空闲事务限制，不是整个多SQL审批流程的总deadline，不提供网络失联全程上限；服务层未知结果仍只读对账不重发。超时可能发生在提交前后，不自动重试。
风险/回滚：审批复杂事务超过单SQL限制会失败关闭；仅回滚连接代码，临时角色/凭据由finally复原，无当前实例配置/库改动。正式OS/OIDC、119–122部署/启动载体修复独立门。无UI变更，不做浏览器通过声明。
