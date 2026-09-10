# 精确配置源连接探针

基线df340754。新增POST /v1/sources/{source_id}/test，只收expectedConfigurationRevision，scope来自现有principal，不收连接串/SQL。服务从当前tenant meta_source读取FOR SHARE，检查type=jdbc-mysql-ssh、状态registered/active/ready及精确版本。共享行锁保持到独立JdbcConnectorRuntime(reuse_cache=False)结束，避免普通配置更新在探针期间穿透。只调用list_configured_tables，不读业务行；结束连接与数据库事务。连接异常固定脱敏503，不返回内部异常；失败/取消不重试。

文件source_connection_probe.py、wave_ext.py、test_source_connection_probe.py。受支持配置仍由既有严格parser验证。成功只表示此版本在测试时可访问且发现表，不升级履约/新鲜度/业务授权。网络/SSH既有timeout生效，不创建后台线程绕开取消；表上限500。验证scope/version/state/type阻断前无连接、正常使用private runtime、失败无敏感异常、返回version与真实table结果。此轮模拟传输，不宣称真实源连通。
