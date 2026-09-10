# 重复登记配置保留验证

基线00b730ab。新增测试先复现元数据重登记丢失password/database，1 failed/4 passed；修复后配置与登记专项22 passed。重复同type从已加载项继承，显式新config清除旧连接字段后替换，异type409拒绝。成功持久化前不更新缓存，公开响应仍脱敏。git diff --check通过。

命令：AOS_DOTENV_DISABLED=1 AOS_TEST_USE_SHARED_DATABASE=1 services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/test_source_connection_config.py services/aos-api/tests/test_source_registration_persistence.py -q --tb=short。合成数据，未访问真实源/修改恢复库。旧7启动警告与JDBC退出日志问题保留。

限制：本次保护同进程登记语义，当前hydrate缓存/无CAS不能证明跨进程并发配置更新安全；后续PG回读必须把合并移至数据库事务或加expected revision，不能声称完整重启/多实例验收。精确配置观察已有reuse_cache=False，普通批读入口仍需隔离审查。向导、探针、真实配置与首链继续未完成。无push，230 L0挂起。
