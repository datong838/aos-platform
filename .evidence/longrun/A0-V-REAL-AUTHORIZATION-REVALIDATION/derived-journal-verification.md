# 原批次关联派生命令验证

2026-09-11，基线af387877。a0v_006新增派生命令不可变表，FK关联原run；save/read检查parent完整hash、非删除父对象identity/type、stream及无重复，完整命令含CAS/幂等键原样保存。空列表在合同上允许，不等于缺记录。

新增PG组合先因迁移缺失红，实现后与原journal/准备测试共4通过。覆盖新连接回读、重复保存、CAS变化冲突、非父对象拒绝、canary不可见、非空降级拒绝。diff --check通过。只在隔离恢复PG随机schema用合成数据，未运行public迁移或真实上游；既有启动警告仍在。

本存储尚未核验base Receipt已提交和input_revision来源，不构成执行授权。恢复执行入口/完整派生输入准备仍待装配，不能重新prepare替换旧记录。API未重载，首链与八工作台未完成，不push，230 L0挂起。
