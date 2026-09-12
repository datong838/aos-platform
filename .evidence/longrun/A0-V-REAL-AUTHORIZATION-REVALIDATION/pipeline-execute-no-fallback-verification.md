# 手动执行不得绕过禁入：验证

2026-09-12。wave_ext.execute_pipeline现只解析当前scope管道及持久图并委托已live的正式Engine；未知管道404、未启用/退役409、读取控制失败固定503、执行异常固定PIPELINE_EXECUTION_UNCERTAIN/503。旧500余行内联路径已移除，包括source查询缺少scope、原始SQL读源、full删除对象、绕过单一Projector写obj_instance和跨组织补登记。异常不再日志泄漏或切换执行通道重做。

先红：6 failed/4 passed；绿：76 passed（手动入口、honesty、图恢复、真实调度）。其中fake executor仅验证委托一次和返回成功/失败契约，不计真实业务成功。旧测试中仅metadata就要求直接写对象的错误期待已替换；真实Ingress/单写者由现有真实调度与独立Store测试承接。

实际后端重启后07:22:55Z，org-org/dev-project P01-shop-qyh请求mode=full返回409/PIPELINE_EXECUTION_NOT_ENABLED。图完整内容不变、revision1、builds0、schedules0、health ok。只验证禁入，没有运行P01同步、没有调用JDBC/源库；仍未完成首链。证据pipeline-execute-no-fallback-http.json。AR2闭包1790/158/93及五类错误空，diff检查通过。

边界：已live的旧手动委托仍是既有非持久结果投影，不能替代ScheduleRun/Ingress Receipt；本波没有新增live权限，也没有声称完成统一运行授权、预算或生命周期Admission。下一波将明确PipelineRuntimeControl持久配置与当前安装generation/source revision/graph hash绑定，复用meta_schedule_run与Ingress执行/恢复Owner，再允许P01实读。不允许HTTP任意execution_mode开关，不开legacy bootstrap，不用直接SQL接业务线。230 L0挂起、不push。
