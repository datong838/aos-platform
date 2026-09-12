# 来源选择历史表验证

2026-09-12，基线dec5f99a。新增a0v_022仅追加pipeline_source_selection_revision历史表；双租户、安装代际、管道修订主键、唯一幂等键、同目标前序hash外键、真实源配置复合外键和payload身份CHECK。强制RLS；UPDATE/DELETE/TRUNCATE均由既有不可变历史触发器拒绝。仅既有aos_runtime获得新表SELECT/INSERT，不改变dispatch或其他表权限。downgrade保留历史、明确拒绝破坏性回退。

RED为缺迁移文件导致14 errors；实现后独立18432临时schema中14项数据库合同测试与控制草稿/源配置关联共65 passed，10.79秒，7项既有警告。API测试会从基线完整upgrade head，因此同时验证完整迁移链到a0v_022。临时schema的引用表只按真实键形状构造，不冒充真实批准或完整业务安装。包含合法两修订追加、重复修订/幂等冲突、错hash/跳号/换selection/generation、实际存在于负租户的源配置不可借用、RLS隐藏与写拒绝、空payload不可利用NULL通过检查、表Owner也无法改删截断。

AR2 ar2-7闭包1792/158/93，五类错误空，diff检查通过。真实aos_meta_head只读回查仍为a0v_021且新表不存在，见source-selection-schema-production-boundary.json；未对真实库应用迁移或生成审批记录。

结构约束不替代应用层完整合同、规范摘要复核和当前权限Owner。本波尚未实现追加/审批服务或执行接线；下一波完成服务端同事务当前安装/配置/源/图/包核对、审批记录与CAS/幂等回读，再做生产接线。P01未读源、未启用。m1串行、不push，230 L0挂起。
