# 派生原子基础版本门验证

2026-09-11，基线a277f15b，A0V-ATOMIC-BASE-GUARD-20260911。

update_derived_metrics新增内部expected_base：先验证身份/type/未删除，再在现有对象FOR UPDATE锁后比较payload_hash，变化则在任何新派生副作用前拒绝。恢复入口从原BatchCommand取对象传递，不另造版本。旧接口/Receipt哈希不变，exact已提交Receipt仍优先回读。测试包装器透传新参数。

验证：新增测试先因缺参数失败；最终SQLite Store/恢复54通过，隔离PG Store+既有Journal组合5通过，共59独立用例。PG新专项用SQLAlchemy metadata创建隔离6张Store表、local sequence、runtime角色和FORCE RLS；执行基础预检→另一基础事务变更→旧expected_base派生拒绝，派生Receipt/Event均0；匹配版本提交后重复Receipt仍1、canary读取不到。不是生产migration全量证明。恢复专项在读取原水位后插入基础更新，确认服务传入旧对象并被Store拦截。diff-check通过。

限制：只绑定派生目标基础对象，不代替关联Order等输入的版本证明；原非恢复入口未强制传expected_base。public未迁移，API未重载，空批/重新claim/全调度真实源验收待完成。完整真实经营首链和八工作台未完成，不push，230 L0挂起。
