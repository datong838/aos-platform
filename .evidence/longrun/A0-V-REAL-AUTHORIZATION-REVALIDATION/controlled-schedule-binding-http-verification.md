# 计划批准关联HTTP入口验证

2026-09-13，8155d20f。新增POST /v1/pipelines/{pipeline_id}/schedule-control-bindings，body仅scheduleId/controlRef/previousRef；登录principal决定tenant/actor。复用严格JSON、64KiB限制、单一幂等header和错误脱敏处理。服务采用独立runtime consumer事务，Owner在提交前核对路径pipeline与当前Control。

先7项路由缺失RED。实现后HTTP/服务/Owner合计41 passed，新增路径不符前拒绝及未知错误不重试2项通过。原审批HTTP行为保持，通过既有403/404/409/412/422/503映射测试。OpenAPI仍有既有重复operation ID警告，未引入相同新路径；原两审批接口仍完整回归。

绑定不启用计划、不创建run、不读源；返回exact关联Ref不是执行许可。实际主API仍旧进程，主库024，025尚未部署，当前只代码及隔离测试。清册1805/158/93五类错误数组空，diff check通过。下一步正式运行/恢复/cron使用该关联进入受控执行器，之后备份恢复升级025及API重载。
