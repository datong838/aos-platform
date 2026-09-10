# 数据源登记持久化前置修复

基线d38ab971。真实恢复库org-org/dev-project meta_source按type/status统计为空，适配器必须读取该配置才能连接源。核查/v1/sources发现先写内存再_persist_safe，后者吞掉普通数据库异常，因此存在假登记成功与重启丢失。

修改services/aos-api/aos_api/routers/wave_ext.py的create_source：直接调用persist_source，成功后更新内存；失败返回脱敏503，不回显连接配置/SQL异常，不覆盖已有内存项。其他_persist_safe调用暂不扩散修改。测试services/aos-api/tests/test_source_registration_persistence.py覆盖成功顺序、失败保留原值和未创建内存项。先红后绿，无真实数据源/模型调用。

不迁移schema、不重写已有数据；仅数据库失败时改变原假成功行为。未知提交结果返回不可用，后续须重新读取登记状态，不自动触发连接或重复接入。测试后提交，完整首链未完成。
