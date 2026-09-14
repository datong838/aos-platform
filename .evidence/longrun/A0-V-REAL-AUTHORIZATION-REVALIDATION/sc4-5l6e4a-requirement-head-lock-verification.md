## SC4-5l6e4a 续跑前置：原需求Head锁（2026-09-15）

基线5abe378e，属于进行中的l6e4上下文波次前置。方案已补snapshot-resume-design.md。新增a0v_049_data_requirement_current_lock.py，在原DataRequirementStore增加lock_current，新增test_data_requirement_current_lock_pg.py。旧bind已有回执重放会提前返回，不能提供恢复任务所需Head锁；新安全定义函数仅按当前GUC双租户和exact revision/hash锁原Head，无写表、无动态SQL、无租户override，原get_current完整回读。PUBLIC无执行权限，aos_runtime只有函数EXECUTE，表UPDATE仍拒绝。

Red为新迁移文件缺失；最终9项实际隔离PG通过/5.12s（/tmp/sc4-e4a-green.log），实际双连接原cancel被150ms lock_timeout阻断，第一事务结束后原cancel成功、旧ref拒绝、事件只有原request/cancel两条；wrong hash/revision/kind/receipt/bool/canary/project及非运行角色/表写拒绝。13原Store pure回归passed /5.26s，1个独立PG明确deselected（/tmp/sc4-e4a-regression.log）。AR2 1949/191/93无错误；Alembic唯一代码head成为a0v_049（原a0v_048后追加），主库最后核对仍a0v_038，此处不执行主迁移。部署前必须包含新函数，缺失时续跑关闭，不能当作已上线。

本前置只在18432 ar1c_*隔离schema使用原DDL/Store，未改变任何业务运行状态。未push，230 L0挂起；其余原改动保护。l6e4上下文仍在实施，接下来同事务原初始化、Stage A完整交付核验、Stage B当前Projection/Binding及新Head锁、不可变依据/期限后验；原Task/Run转换仍留e5。
