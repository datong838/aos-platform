# 运行历史恢复候选验证

2026-09-11，基线b51d4b8e，A0V-RECOVERY-HISTORY-20260911。

list_runs增加同tenant/run Journal EXISTS和executor_stopped读取，返回recovery candidate/reason。failed+退出true+finished_at+原输入存在才ready；其他not_failed/executor_unknown/input_missing。候选不授权执行，POST仍重新校验当前绑定。原历史字段和limit保留。

新增分类测试修改前6失败17通过；最终33专项通过（1隔离PG查询、23调度分类、9HTTP）。PG复制现有run表形状后在隔离schema加退出列，最小Journal验证目标ready、canary同名输入不能满足目标、未知退出拒绝、limit及canary结果为空。此为查询过滤证据，不冒充完整生产认证/RLS迁移证明。diff-check通过。

public未迁移、API未重载。下一波dataSchedules前端恢复按钮、原因说明及请求结果未确认时保持原请求标识，随后实际安装升级与浏览器/真实源验收。真实首链与八工作台未完成，不push，230 L0挂起。
