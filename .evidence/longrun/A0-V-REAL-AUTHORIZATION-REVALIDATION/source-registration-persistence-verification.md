# 数据源登记持久化验证

基线d38ab971。专用恢复库只读按tenant统计meta_source=[]。恢复说明已明确历史备份不包含当前正向租户配置；未从dev-org复制配置，已向用户询问原配置位置（不索取明文凭据），不阻断独立代码修复。

create_source原先先写内存再调用吞错的_persist_safe，现直接持久化成功后才写内存。普通存储异常返回固定503/SOURCE_PERSISTENCE_UNAVAILABLE；不记录可能带连接凭据的异常文本。原ApiError保持。未知提交结果提示先读取登记状态，不自行重放接入。

专项3项先全部失败后全部通过：新登记失败无内存残留、覆盖失败保留原项、保存完成前缓存未变。命令AOS_DOTENV_DISABLED=1 AOS_TEST_USE_SHARED_DATABASE=1 services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/test_source_registration_persistence.py -q --tb=short；git diff --check通过。使用函数级存储故障注入，没有真实连接配置写入或浏览器验收。7项旧启动警告与JDBC退出日志问题仍在。

方案一致：仅改变/v1/sources存储失败时的假成功行为，不扩大到其他_persist_safe调用，不改schema或现有数据。风险：此入口ConnectorIn只含id/type/runtimeMode，真实连接参数配置尚须追踪对应入口；运行进程未重载，不能宣称线上生效。完整首链未接通，不push，230 L0挂起。
