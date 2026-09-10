# Dataset 与历史原子保存验证

2026-09-11，基线 040a403c。persist_dataset 可选 history_entries 在同一事务内复用历史替换函数；原独立函数保留。sink使用组合调用，提交后才发布缓存。

隔离 colima-aos-extension/aos-a0v-recovery-pg/aos_meta_head 随机 schema，克隆 dataset/history，历史自增默认改用测试本地 sequence，未消耗 public 序列。测试角色 RLS 限定 scope；测试约束制造 history INSERT 失败，确认新 dataset name 回滚、旧 history 恢复，再重试成功。先因缺接口红，实现后含 PG 的 31 项组合通过；diff --check通过。正常运行输出仍有既有启动警告。

测试使用合成记录与测试RLS，未验证生产角色权限或真实源接入。原 history 替换语义保留；本事务不包含 OT、派生、Projector，不能声明完整经营原子恢复。API 未重载本修改，不 push，230 L0 挂起。下一步接入运行的权威对象、Dataset成功状态与断点之间恢复对账。
