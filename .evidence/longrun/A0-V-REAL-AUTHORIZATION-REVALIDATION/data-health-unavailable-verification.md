# 数据健康读取真实性验证

2026-09-12：产品页面 8434/data/health 实际显示12不可验证项。产品 API /v1/me=200 确认 org-org/dev-project、user:dev；/v1/data/source-readiness=200 blocked，12项均缺源/管道/调度及查询能力等引用。/v1/sources 与 /v1/pipelines 均返回空 items。不能将运行启用等同于数据已接入。

通过 Web identity 直接构造 SourceReadiness 的尝试被 SET ROLE aos_runtime 拒绝，没有改角色或换高权限账号重试该路径；改用已存在且有认证的正式产品 HTTP API 读取，其本身准许当前用户访问。未读取/输出真实客户明细或凭据。

发现并修复 _pg_ot_row_count 将所有异常吞成0的独立缺陷。先红2失败/2通过；修复后专项和 test_r41_current_data_truth 共10通过。正常0/42行结果保持、scope参数保持，连接/权限错误给稳定503 DATA_OBSERVATION_UNAVAILABLE，不泄露底层信息。数据健康和沿袭共用读者，不以假0继续显示。

下一步核对并重启同一诊断 API 启动入口加载代码，保持迁移/定时/业务自动化关闭；独立Host v10继续运行。安装登记访问扩展仍待用户针对性确认，未落地。真实源配置后续只走现有管理 API。
