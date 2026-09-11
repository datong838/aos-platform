# D02 诊断可信保存与恢复验证

2026-09-11；基线 m1 `70d698d8`；任务 A0V-D02-TRUSTED-RECEIVER-20260911。对应 diagnosis-trusted-receiver-plan.md，逐文件 pre/post SHA-256 见 diagnosis-trusted-receiver-files.json。

## 已实现与验证

- 新 DiagnosisReceiver 只恢复原成功调用的私有正文。同连接校验租户、actor、D02、route/policy、Artifact 来源、当前 Insight 与完整受控来源，重建固定原始请求哈希后由既有 Owner 保存。
- tenant+attempt 咨询锁与原 publication receipt 保证并发及重放只产生一条诊断。Owner 新增历史 exact 诊断读取，检查 ID/revision/tenant 和正文重算哈希。
- 新发布时缺少来源、失效权限、撤销、漂移、过大资料均拒绝。已保存结果恢复不重新申请来源授权，但仍检查原回答读取权限和原始身份，且不产生后续执行许可。

执行：AOS_DOTENV_DISABLED=1 AOS_TEST_USE_SHARED_DATABASE=1 AOS_GROWTH_DRAFT_FULL_GRAPH_TEST=1 AOS_GROWTH_DRAFT_OWNED_CLONE_TEST=1，项目 Python 运行 pytest：

`test_ecommerce_analyst_diagnosis_receiver.py`、`test_ecommerce_analyst_diagnosis_generation.py`、`test_ecommerce_analyst_analysis_proposal.py`、`test_ecommerce_analyst_analysis_sources.py`、`test_ecommerce_analyst_growth_plan_receiver.py`、`test_ecommerce_analyst_growth_plan_full_graph.py`、`test_ecommerce_analyst_authority_store.py`、`test_ecommerce_analyst_growth_plan_worker.py`、`test_ecommerce_analyst_growth_plan_generation.py`。

结果：**192 passed，7 个既有 warning，5.42 s，退出码 0**。其中新接收器 35 项，含 4 组真实一次性完整 PostgreSQL 表图：提交前异常回滚后零记录；两并发单记录并可回读；来源撤销后历史结果恢复；原文权限不足/撤销/不存在授权阻止新保存。数据库来自明确的自有克隆模板，保留真实约束，测试完删除各自新库。关联原 D03 保存与工作者回归通过。

测试早期版本漂移夹具未提供 version/priorRef，先被模型校验拒绝；补齐有效 r2 夹具后验证精确读取拒绝 r1/r2 不一致，没有放宽产品校验。pytest 退出后的既有 JDBC 日志清理关闭流提示不影响测试退出码。git diff --check 通过。

## 方案一致性与限度

此波无 Provider 调用、无主库业务写入、无 API 重载、无公开入口。完整图仍是合成事实和已完成调用夹具；真实模型执行、真实 D01 指标/方法权威、真实栖月汇经营计划与首链尚未验收。当前来源读取是快照，后续生成/审批/执行仍必须校验当时权限。无 push，230 L0 挂起。

下一波：D02 生成服务组合和 TAOR 阶段接续；然后 D01 方法/指标正式来源、三阶段宿主调度、实际运行配置与真实数据恢复，执行经营参谋业务计划和八工作台场景。继续自动推进，整体未完成。
