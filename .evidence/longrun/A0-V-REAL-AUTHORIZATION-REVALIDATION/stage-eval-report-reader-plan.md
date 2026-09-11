# 阶段评测报告精确读取

2026-09-11，基线bbb391ad，AOS-000573。继承231-5和160的真实Eval与人工阶段门。

新增 services/aos-api/aos_api/ecommerce_analyst_stage_eval_report.py，显式HostTransaction/Scope，只读并锁定实际EvalReport/Run。校验实际完整报告canonical hash及原JSON/typed一致，报告通过、创建时间不在未来、所有exact（原Artifact、StepRunAttempt、EvalContract、GatePolicy、cutoff）匹配；同一stageAttempt最新报告，旧通过不能盖过新失败。实际EvalRun必须succeeded、执行时间完整、suite/target/dataset/judge/所有阶段绑定与报告一致。返回报告，不写状态，不自证当前合同、原文可读或成员权限；最终命令还需逐项联合核验。

新增 services/aos-api/tests/test_ecommerce_analyst_stage_eval_report.py：真实隔离PG用正式EvalRun/Report Owner记录合法状态序列，成功报告回读；其他scope、hash、错误阶段/产物/合同/policy/cutoff、未成功Run及新失败取代旧通过拒绝。无真实模型评分或业务数据，不声称首链完成。
