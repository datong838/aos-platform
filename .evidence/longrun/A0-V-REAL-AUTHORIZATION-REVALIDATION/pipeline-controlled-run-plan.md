# 当前管道控制与持久读取占用

2026-09-12，基线9c87c6c8。复查既有ec_durable_executor：成功读取后才保存Ingress，崩溃在两者之间会失去源调用事实。直接把受控读取替换旧fetch_source_rows_versioned不足以守住调用预算及未知结果不重发。

## 接线顺序

1. 增加不可变pipeline_controlled_source_claim：每个既有ScheduleRun唯一绑定一个exact运行控制、执行actor和本控制下的调用序号。引用完整租户/安装/代际/管道/controlId/revision/hash与真实ScheduleRun；绝不制造第二运行游标。序号在当前ControlOwner持有安装锁时分配，与maxSourceCalls核对后落库并提交，随后才能调用源。
2. 执行器按同一actor与controlRef重新进入当前Owner，核对ScheduleRun/graph/source后使用显式选列有界读取，保存原始canonical BatchCommand与outputRows。读取返回后须再次检查当前期限；空源走既有empty_observation，不能解释为删除全部对象。
3. 重入发现已有占用且有Ingress时只恢复同一批次；已有占用但无Ingress时返回SOURCE_OUTCOME_UNCONFIRMED，不自动重新读取。占用提交结果未知也先查询同run记录，不能换运行ID重发。新审批不自动解除旧未知占用；需明确核对/新运行流程。
4. 后续每次原子写入和恢复都重验当前控制，并比对占用绑定。旧执行器不能处理受控run而跳过检查；以独立受控模式和入口显式拒绝旧路径。当前maxSourceCalls由审批限定，不以用户忽略模型费用为理由放宽此产品控制。
5. 安装停用/失效、控制过期或被替代都拒绝新写入；恢复续期需独立保持原图/源/资产范围的明确流程，不能静默改用最新控制。该续期能力未完成前不启用真实P01。

## 本波存储切片

新增 services/aos-api/alembic/versions/a0v_024_pipeline_controlled_source_claim.py 和 tests/extension_runtime/test_pipeline_controlled_source_claim_schema_pg.py。不改已部署022/023；主库本轮仍023，只在独立测试库执行DDL。

字段：org/project、run_id、installation/generation/pipeline、control_id/revision/hash、call_ordinal(1..32)、actor、created_at。PK(scope,run_id)，唯一(scope,control_id,control_revision,call_ordinal)，完整Control FK、ScheduleRun FK。表仅INSERT/SELECT，强制RLS，UPDATE/DELETE/TRUNCATE均拒绝，清除旧默认权限继承；downgrade保留历史。无自由SQL、无执行状态布尔值、无当前权限快照字段。

数据库仅保证引用/去重/隔离及序号范围；实际maxSourceCalls和当前权限必须由下一步Owner在持锁事务内检查。验证实际PG错租户、错运行/控制/管道/hash、重复run/序号、非法序号、不可变与默认ACL；完整迁移head及AR2闭包。随后实现当前占用Owner/恢复入口，不将存储测试当作读取权限或真实经营完成。
