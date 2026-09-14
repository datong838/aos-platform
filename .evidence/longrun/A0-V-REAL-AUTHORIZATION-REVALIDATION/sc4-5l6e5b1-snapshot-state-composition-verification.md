## SC4-5l6e5b1 原Task与业务Run状态组合（2026-09-15）

基线d1d7426a，m1/AOS-000573。按snapshot-resume-design.md新增内部_AnalysisSnapshotResumeSession._resume_states及extension_runtime/test_analysis_snapshot_resume_states_pg.py。只在同事务active原stage里回读原Requirement/Run/Compilation/Binder，核WAITING_DATA/RUNNING/no unknown、同pending与阶段A完整runtime/checkpoint/Plan，再通过原_AnalysisRunAndTaskResumer与原Store各执行一次CAS。转换后原timeline、原Run和read_data_resume_receipt精确回读，原Task控制证据按固定键/actor/原_control_request全字段核验，最后返回e3独立结果合同；无假水合，没有新状态存储。

Red为缺少_resume_states，1失败7.31s（/tmp/sc4-e5b1-red.log）。18432隔离PG 4 passed /9.89s（/tmp/sc4-e5b1-green.log）：实际原初始化建立Task/TaskRun/Checkpoint/Requirement/业务Run；成功同TaskRun版本+1、Task版本+1、业务Run版本+1到PREPARING、未执行模型步骤；重复首次调用拒绝且原状态不再增加；原业务Run失败、返回结果漂移、后置异常时两原状态与控制Receipt均回滚。此测试的整个十二源交付stage明确named；只证明原状态Owner组合，不替代e6完整12+原起点端到端。

81项原快照命令/会话纯回归通过5.56s（/tmp/sc4-e5b1-pure.log）；AR2 1951/192/93错误列表空（/tmp/sc4-e5b1-closure.log）；编译/diff和memory validate通过。无主库升级/安装/真实商城读取/Provider调用，不push，230 L0挂起，原用户改动保留。当前内部状态方法尚无生产调用者和统一Host注册；e5b2必须完成统一Receipt后才形成可调用恢复入口。

已复现下一段原控制Receipt消费缺陷：AipTaskStore._control_request合法裸hash被_strict_resume_control_receipt当成带sha256前缀hash拒绝，/tmp/sc4-e5b2-control-format-red.log AssertionError。e5b2先按原合同修消费端并补测试，不能改原表或把fixture改成假前缀；再接快照统一Host Receipt，e5c已提交只读回查/未知结果，e6真实起点+十二源组合，继续Outbox自然消费、主升级安装、真实首链/八场景/连续观察与发布判断。
