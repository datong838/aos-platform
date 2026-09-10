# 可执行连接配置登记验证

端到端方案fb829dc7的A/B后端增量已实现：source_connection_config解析jdbc-mysql-ssh受支持字段，校验必需字段/端口/两组认证二选一，拒绝未知及越权字段，固定错误不回显输入；wave_ext.ConnectorIn增加repr/exclude保护的config，服务器规范化后持久化到现有props，公开响应仍按白名单。无config元数据登记兼容。

先建立解析测试，缺模块红；实现解析后18项通过；接接口后19项通过。命令AOS_DOTENV_DISABLED=1 AOS_TEST_USE_SHARED_DATABASE=1 services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/test_source_connection_config.py services/aos-api/tests/test_source_registration_persistence.py -q --tb=short。git diff --check通过。测试合成凭据，未访问真实连接或写入恢复库。

方案一致性：复用meta_source配置版本机制，不另建连接权威。校验器不执行连接，配置隐藏于请求repr/model_dump，接口返回不含连接字段。现有存储使用props，未在此宣称加密Vault；secretRef沿用现有本地解析限制。连接缓存身份/凭据轮换隔离未验证前不得执行真实探针。

剩余B前端/C测试连接/D向导/E真实接入均未完成；当前向导仍缺稳定id及表发现，尚不能自然配置全流程。后续先PG保存/版本/重启回读，再完成前端和探针，不能把这19项当作首链完成。7旧警告/JDBC退出日志问题仍在。未重载API、无push，230 L0挂起。
