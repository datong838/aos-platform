# 真实接入恢复合同与现状核查

2026-09-11，基线c427a848。目标是提交过的同一批次可以恢复，不是重新从变化的源取一批再称为重试。

## 当前证据

- wave_ext.retry_dlq 仅调用 ec_dlq_store.retry_failure，无执行器调用。
- retry_failure 只更新 retried/retry_count，写 retry receipt 与 retry_succeeded event。不存在源读取、对象提交、任务续跑动作，事件名不能作为恢复成功证据。
- record_failure 保存错误、脱敏metadata与hash，不保存原source/output rows。ec_dlq_handler明确过滤业务payload，不应往该metadata塞业务原文绕过隔离。
- phase5_pipeline_engine 将图与sample_input深拷贝交线程，但这是内存快照；ec_live_executor局部input/output也未形成不可变恢复对象。
- ecom_consistency_store.apply_batch先查exact Receipt再写，具备单批重放基础。当前writer会重新构造命令及读取checkpoint，不能自动等同于保存原命令。
- Dataset/history已同事务，Dataset发布后置；跨OT/派生/投影/Dataset仍不是同一事务。

## 实施路径

1. 新增租户作用域不可变接入批次存储，绑定run_id、pipeline_id、当前管道/源配置版本、规范输出payload及hash、序列化规则、初始exact BatchCommand。仅存执行需要的规范业务行；不得存SSH/DB凭据或整份source配置。原payload仅内部执行Owner可读，普通列表只返回状态/引用。
2. 在任何OT写入前保存批次；唯一键scope/run_id，重复同hash可回读，异hash冲突。缺少run_id或配置版本不允许宣称可恢复。规范化需要的时间戳必须已固定，恢复不再重盖当前时间。
3. 阶段以批次引用关联既有OT/派生Receipt，使用租户与批次锁串行；恢复从保存的同一命令开始核验/重放，禁止重读源替换。OT已成功时验证Receipt；派生按现有CAS检查输入revision；不能猜测成功或覆盖后来变化。
4. 投影用本批确切Outbox/对象revision证明完成；现有project_pending的局部pending不是全量指标，不能作为本批完成门。Dataset成功必须绑定批次与已完成阶段回执。
5. DLQ重试只先记requested，工作器取得批次并完成阶段后才能记succeeded；失败记failed。没有原批次的旧记录必须明确不可自动恢复，另建新运行并标明新源读取，不能伪造旧输入。
6. 故障验证覆盖保存后/OT提交后/派生后/投影后/Dataset提交后崩溃；重启后不再源读、不重复权威副作用、scope canary隔离、hash漂移拒绝。随后才在真实配置恢复后对栖月汇实际数据做同样验证。

## 文件与退出条件

计划涉及 services/aos-api/aos_api/ec_live_executor.py、ec_ot_writer.py、ec_dlq_store.py、新接入批次Owner、Alembic迁移及专项PG测试；先核对当前migration head与既有权限模板，再写DDL。沿用现有失败队列及Receipt，不创建平行审批权威。

退出条件是原输入跨进程恢复证据，而非新表/测试绿。保留单写者、租户隔离、真实数据权限、无凭据输出。不push，230 L0挂起。本文件为核查与施工合同，尚未实现批次Owner/工作器；完整经营首链和八工作台未完成。
