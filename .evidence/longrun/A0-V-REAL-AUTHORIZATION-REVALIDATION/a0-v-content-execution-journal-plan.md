# 内容执行日志：复用调用状态权威

基线 ea77abb4，承接 content-real-execution-plan。预算 reservation 已拥有 held/submitted/unknown/completed 对应状态，不新增第二套调用状态机。

新增 `services/aos-api/alembic/versions/a0v_003_content_execution_journal.py`：两张不可变表保存 command 与 normalized Provider result，按 org/project/reservation 唯一。命令必须在已有 held 且 operation=ecommerce_growth_content_generate 的 reservation 上登记，结果必须属于同一 reservation 的已提交请求。结果日志仅是 Provider 原始结果证据，不冒充 Artifact/Usage 或结算完成。RLS 固定 aos.org_id/project_id，runtime 只 SELECT/INSERT，更新删除触发器拒绝；降级遇到已有日志必须拒绝，不能删除审计证据。

新增 `services/aos-api/aos_api/ecommerce_content_execution_journal.py`：使用调用方租户事务，enqueue 与现有 budget.reserve 同一事务；record_result 与后续用量/Artifact消费可分步恢复。same payload 回放读取已存记录，冲突 payload/hash 拒绝。串行锁同一个 reservation，使并发插入有确定结果；无需在日志里增加 claim/lease。worker 未来使用 BudgetStore.submit 的首次/重放结果判断是否允许首次发送，未知结果不重发。

新增 `services/aos-api/tests/aip/test_a0v_content_execution_journal_pg.py`：复用隔离预算 PG fixture，真实 SQL 验证持久化后新连接读回、same replay、drift拒绝、结果必须匹配请求、跨租户不可见、缺scope拒绝、更新删除不可用、非空downgrade拒绝。只在随机 schema 内应用，结束清理测试schema，不升级恢复库 public，不调用 Provider。

具体命令与安装/dispatch权威联检仍由 Host 执行并在新 worker 发送前复验。本 primitive 不对外暴露 API、不激活现有 no-effect Host，不能凭插入日志自行获得调用权限。后续接入必须验证命令摘要对应原 command、来源和数据分级，再发送；事务外模型调用、worker生命周期、Artifact/Usage原子消费尚须实现。
