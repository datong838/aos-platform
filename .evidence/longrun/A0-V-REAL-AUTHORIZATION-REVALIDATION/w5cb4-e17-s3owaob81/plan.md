# b81 正式evaluator独立连接准入

基线371166a2/权威1329，上位b80完整方案。新增aos_api/aip_binding_evaluator_connection.py与tests/aip/test_aip_binding_evaluator_connection_pg.py。先模块缺失RED，再最小实现，不修改Registry/BI身份或路由，不改migration，不把连接可用称evaluator完成。

复用RegistryIssuerDatabaseConfig的严格loopback/exact DB/0700 parent/0600 private passfile安全校验，只包装为新Evaluator config，不读复制凭证。独立固定login aos_aip_binding_evaluator，SERIALIZABLE/非autocommit/读写、GUC exact tenant、10s statement/5s lock/10s idle，session=current role=独立login，LOGIN/NOINHERIT/NOSUPERUSER/NOBYPASSRLS/无CREATEROLE/CREATEDB/replication/角色成员。任何环境PG认证/配置重定向拒绝，连接失败只安全错误不暴露secret。

真实一次性PG新随机独立role、随机测试口令仅临时文件，测试patch固定login到自有随机名，不改任何既有role；测试合法backend session/role/DB/scope/isolation/超时，错误scope/不安全文件/PGOPTIONS/授runtime成员/INHERIT/CREATEDB均拒绝且不yield。finally只清自建role/私有目录。继承原Grant为零，连接能通不授表写权限。应用入口尚未配置，无真库role或业务写入。

正式HTTP命令/同事务evaluator/source schema仍下一实现，不将缺模块RED当HTTP业务RED。编译/diff、真实PG专项与既有事务接缝相邻，Task/Delivery/01/06/D-wave精确提交；无UI浏览器不适用，Goal active。生产Role供给/私有配置独立门，未满足连接fail-closed。

自复审补门：底层私有文件validator Path(None/int)会先TypeError，需同样映射安全EvaluatorBlocked；新增真实RED两项，最小catch TypeError/ValueError/OSError，不改旧Registry validator或暴露配置值。
