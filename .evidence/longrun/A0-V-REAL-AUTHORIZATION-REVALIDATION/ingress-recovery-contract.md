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

## 已准备派生阶段恢复入口（本轮实施）

新增 ec_ingress_recovery.py 内部函数，仅处理原基础命令已提交且原派生命令已保存的运行。复用Journal当前running schedule/source/graph绑定检查，持有调用方事务行锁直至返回；不开放HTTP，不伪造DLQ成功，不做未准备阶段的推断。基础exact Receipt不存在或存在ignored对象/关系时拒绝，必须另行对账。派生命令只反序列化原记录，复用ConsistencyStore幂等与CAS；中途失败不回滚已提交项，下次同命令续跑。

文件：services/aos-api/aos_api/ec_ingress_journal.py 提取可复用绑定检查；同目录新增ec_ingress_recovery.py；tests/test_ec_ingress_recovery.py验证部分提交后重放、缺失/不完整基础回执、绑定拒绝与命令缺失。SQLite验证真实ConsistencyStore写入；Journal/绑定用测试替身，PG绑定另有专项。不得以这些测试声称真实源或完整恢复已通。

仍缺原始辅助输入持久化、恢复claim/worker、当前执行授权、精确输入revision来源、投影完成和Dataset接续；该函数只有内部已授权执行者可以装配。回滚移除新入口及还原提取，不变更现有executor行为或数据。

## 规范恢复输入随基础命令原子保存

2026-09-11，基线b0968513。扩展现有envelope可选outputRows，复用a0v005不可变行及同一INSERT，无新表/DDL。旧envelope仍可读；只有携带outputRows的批次具备恢复派生准备所需输入。保存仅提取OT/Link规范字段及pay_time、_order_create_time、delivery_time辅助字段；不保存任意原始源行、连接配置或凭据。JSON规范化datetime/Decimal，拒绝未知类型与非有限数字。通过原OT规范器重建对象和关系，要求与父BatchCommand逐项一致；固定时间值在保存前已生成，恢复不盖当前时间。

文件：services/aos-api/aos_api/ec_ingress_journal.py（可选字段、规范化、完整性验证），tests/test_ec_ingress_input.py与tests/aip/test_a0v_ingress_journal_pg.py。验证datetime往返、计算辅助字段保留、基础漂移拒绝、幂等冲突及跨连接/跨租户读取。既有派生命令parentHash自然覆盖此字段。

此规范快照用于恢复计算，不保证旧Dataset全部raw列可重建；Dataset完整输出合同另行接续。实际executor暂不切换，精确输入revision及claim仍需实现；该变更不得被称为完整可恢复。
