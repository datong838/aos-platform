# Dataset 与历史同事务

基线 040a403c。修改 data_os_store.persist_dataset 增加可选 history_entries；在同一连接提交前执行既有 history 替换逻辑。抽取私有 history 连接内函数复用；原独立 history API保持语义。ec_dataset_sink改为一次调用，成功后再发布缓存。文件 data_os_store.py/ec_dataset_sink.py；调整 sink测试并新增 aip/test_a0v_dataset_atomic_pg.py。

随机测试schema中验证：先存旧数据与历史，制造history插入约束失败，新dataset更新及旧history删除一起回滚；随后正常重试成功。使用隔离恢复PG，不改public业务记录。独立接口保持原提交语义，history当前替换而非追加的语义不在本轮改变。该事务不包含OT/派生/Projector，不冒充完整首链原子性。
