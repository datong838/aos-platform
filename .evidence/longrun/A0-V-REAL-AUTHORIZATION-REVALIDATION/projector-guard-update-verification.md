# 投影器更新归属门验证

2026-09-11，基线6d88f8f5，A0V-PROJECTOR-GUARD-UPDATE-20260911。

PG恢复组合安装原o1r2_001生产trigger后，非actor Payment→Other更新未被拒绝，复现1失败4通过。新增a0v010只替换同名guard函数，按操作读取OLD/NEW分类，任一侧受保护均要求现有投影actor。普通Other写入不限制，原历史迁移不改。安全修复forward-only，downgrade拒绝恢复已知绕过路径；领域包物理卸载不是平台schema降级。

最终7场景通过，验证非actor创建Payment拒绝、Payment→Other拒绝、Other→Payment拒绝、受保护rel→OtherRel及删除拒绝、普通Other正常更新；真实Store→projector在生产guard下完成Payment和后续Dataset/恢复事务。diff-check通过，alembic heads仅a0v_010。表仍隔离最小兼容表，非全库安装升级证明。

public未迁移、API未重载；API/UI恢复入口、完整安装迁移与真实源首链仍待执行，八工作台未完成。不push，230 L0挂起。
