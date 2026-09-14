## 2026-09-15 SC4-5l6e6c 原生十二类对象投影

基线1363ca8b981a3626cc1cb28568b60b8ce246e2e3，m1串行。新增test_analysis_snapshot_native_projection_pg.py，在逐用例私有完整public结构上复用e6b原12输入、实际ControlledSnapshotGroupObjectExecutor/ConsistencyStore/Projector/Dataset；原Policy/Assessment负责解析、hash和整组验证，安装资产/release及源读取继续named。没有新增DDL、GRANT、影子表或SQL前缀替换。

首次完整执行3 passed/102.12s（/tmp/sc4-e6c-first.log），七项既有警告。证明12个ecom_object/ecom_ingest_receipt/obj_instance/meta_dataset/meta_dataset_history/ecommerce_ingress_dataset_receipt真实保存且重复计数不增长；各成员pending=0；首成员独立提交后抛错，已有1个投影可见，恢复后完整12且源调用总计1；当前策略禁入时原对象0。这里未执行关系链接/清退或调度终态，不能称完成组可供分析消费。

AR2 1951/192/93五类错误为空（/tmp/sc4-e6c-closure.log）。主库未迁移、无真实源/模型/Task/安装发布动作，用户既有三份改动保留，不push，230 L0挂起。

下一波e6d优先补真实接线缺口：原completed_group测试手工UPDATE succeeded/stopped，原GroupObject/Link/Retirement Executor没有统一调度完成入口。先设计原调度状态Owner与完整组当前证据/单写者的收尾组合，不能继续用手填状态绕过；组合后才能把原12完成组交给原初始化/Pending/证据/快照恢复。计划保留首链自然触发、八工作台、经营产物/人工评审续跑、连续观察和发布判断，不以PG测试替代这些目标。
