# BG00EK 消费者正式连接预检与接线

基线AOS-000999 / m1@3a165e9b；复习231-1/3、BG00EI/EJ与现有issuer/publisher连接。发现apply_transaction_scope会SET ROLE aos_runtime，不适合consumer。当前真实库118只读；不创建角色/凭据，不启Host。

## 文件级计划

- 新增`services/aos-api/aos_api/aip_network_consumer_connection.py`：只读预检函数require_consumer_identity(conn,scope,expected_database)。要求实际db精确匹配、session_user/current_user均caller、tenant GUC匹配；caller LOGIN/NOINHERIT/非特权、owner NOLOGIN/NOINHERIT/非特权、双方无membership；固定函数SECURITY DEFINER/owner/search_path、caller EXECUTE；caller无public表任意列SELECT/INSERT/UPDATE/REFERENCES及表DELETE/TRUNCATE/TRIGGER权限、无对象所有权。错误固定code，不回显连接信息。
- 新增`services/aos-api/tests/aip/test_network_consumer_connection_pg.py`：标准一次性PG，隔离事务内将caller LOGIN仅用于验证登录属性（不是正式凭据），SET SESSION AUTHORIZATION仅作test-only身份夹具；正向纯SELECT预检不改变业务表；错db/scope/runtime、高权限/成员关系/额外ACL/函数属性漂移拒绝。先RED缺模块，再最小实现。
- 后续同波凭据工厂必须先验证受保护文件和实际身份，独立caller无需SET ROLE；网络连接异常脱敏。未知结果只读原Receipt对账，不隐式重试消费。正式OS隔离/凭据部署留独立安全波，不能用测试身份替代。
- BG00EJ未覆盖的已有head修订与最终写入等待跨到期仍需联合测试；预检不是授权凭证，SQL消费在写入时重验。

验收：专项/相邻回归、方案代码复审、verification、精确m1提交、D-waves/上下文及Prime CAS。内部连接无页面变化，暂不涉及浏览器验收；任何未做部分明确保留，不制造正式首链证明。

## 第4/9步接续检查点

新模块与PG测试已写，缺模块RED退出2；只读身份预检GREEN：`services/aos-api/.venv/bin/python -m pytest -q tests/aip/test_network_consumer_connection_pg.py --tb=short --show-capture=no`（cwd services/aos-api，实际命令使用`.venv/bin/python`），10 passed / 7 warnings / 5.40s，句柄93117退出0。测试LOGIN修改均同事务rollback，不保留集群角色修改。

首次写测试路径误带services/aos-api前缀，shell写入失败且pytest退出4；更正工作目录相对路径后取得上述RED/GREEN，不把路径失败算业务RED。

预检尚未接凭据工厂/服务，不等于业务授权；下一步在本波补受保护passfile配置、显式caller连接和事务scope生命周期测试，继续已有head/写后时效联合验证。当前未提交，authority仍AOS-000999，Task/Lease W5CB4-BG00EK-20260930。当前库保持只读，不迁移、不启动Host。

## 连接工厂实施细化

同模块新增ConsumerDatabaseConfig(host,port,database,passfile)，仅loopback精确地址与严格数据库名；绝对私有目录0700/普通文件0600、当前uid、非符号链接、非空，连接前重新核验。拒绝PGPASSWORD/PGPASSFILE/PGSERVICE/PGSERVICEFILE/PGOPTIONS环境覆盖；显式固定caller、端口、库、passfile、connect_timeout。独立连接READ COMMITTED，事务局部tenant与statement_timeout/lock_timeout，预检后yield；不SET ROLE，不自动重试，退出由psycopg提交/回滚并关闭。只读预检可read_only=True，消费连接False；连接与提交失败统一脱敏且保留未知结果语义。OS用户分离和扩展ACL仍由独立部署门验证，不能仅凭0600声称凭据完全隔离。

连接成功链用标准一次性数据库实际TCP连接验证：在专用测试PG锁内先确认caller原本NOLOGIN且无密码，仅临时设置随机测试密码写私有临时passfile，测试完成finally恢复NOLOGIN/无密码。密码不输出、不同于正式凭据；不修改HBA。该实测只证明连接工厂真实session/事务/消费闭环，不能证明正式SCRAM或OS隔离部署。

## 2026-10-01 第5/9步检查点

ConsumerDatabaseConfig/connect_consumer已实现，凭据配置8项RED退出1后专项18 passed。真实TCP工厂消费1 passed（句柄76790），随后与原子消费/权限/到期/Producer五文件累计65 passed / 35.31s / exit0（句柄85689）；真实工厂异常事务回滚、commit后scope失效且新连接可继续已覆盖。新增已有head从revision1到2的真实Producer→独立Issuer→工厂消费者联合测试1 passed / 5.49s / exit0（句柄88695），旧Receipt重读不回退head。未声称66项一次累计；此新增测试在65累计后单独执行。

临时测试caller LOGIN/随机密码均finally恢复NOLOGIN/NULL并清空临时文件。没有正式凭据或真实库修改，未改HBA。还需最终写入等待跨到期回滚测试、连接权限/安全边界复审及最终累计；随后verification/精确提交/上下文收口。代码文件与测试仍未提交，Task/Lease仍BG00EK，authority仍999。所有上述测试句柄均终态，无在跑句柄需要重启。

最终时效验证采用仅一次性测试库的AFTER INSERT Receipt触发器等待advisory lock。测试先观察pg_stat_activity确实等待该advisory锁，再让真实批准时钟到期后释放，要求SQL返回NETWORK_CONSUMER_EXPIRED并回滚head/revision/Receipt。触发器只延迟写后返回，不替换批准/哈希/时间逻辑，finally删除；不是业务mock验收。
