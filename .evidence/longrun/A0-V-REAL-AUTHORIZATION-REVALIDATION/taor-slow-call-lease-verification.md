# 慢调用租约维持验证

2026-09-11；A0V-TAOR-SLOW-CALL-LEASE-20260911，基线 b4102ec2。

新增 opt-in 续租适配器；首次、等待期间及返回时用既有 Owner 续租，默认路径不变。Store 追加 running/executing、pausing/paused 状态配对，保留租户、owner、fence、assignment 与到期检查。

验证：新参数在实现前专项失败。实现后第一轮31专项通过；增加真实fence接管负例后，包含续租/观察恢复/生成组合/私有正文/AgentRun执行/完整依赖图/接收/来源/草稿/原合同/Owner/审批共208 passed、7既有警告，退出0，12.40秒。新续租专项13项。

真实隔离证据：4个一次性完整克隆，均由真实Owner创建并批准合成Task/Plan/Run；每次步骤租约1秒，单次adapter act等待1.4秒。正常场景成功且只有1调用/1检查点；暂停场景到检查点变paused；取消后act evidence为空、检查点0且Run仍cancelled；模拟assignment current_fence接管后旧worker无法续租，act evidence与检查点均空。每个DBfinally删除，无主库/真实Provider写入。

单元负例覆盖错误时长/布尔配置、调用前续租失败不进入adapter、调用中失租等待原结果后阻断、不重发、不暴露连接异常正文、默认不启动续租。旧观察恢复测试及生成恢复相关回归保持通过。

限制：不是强制取消外部调用；已发出的调用会等待原传输层返回/超时，不后台遗留新的重试。数据库故障可能延长等待，不保证性能SLA。历史元数据不是新授权；当前API未重载、生产入口尚未开启opt-in，真实业务计划与八场景未完成。既有JDBC退出日志closed-stream错误未改动。

下一入口：D03受信工作者核验Task/Plan/AgentRun/assignee谱系、绑定唯一原attempt、使用此opt-in与GrowthPlanGenerationService，将正式GrowthPlan exact ref回写检查点；未知状态不能被误判为安全失败后重发。然后真实数据/安装配置、首次分析及自然触发、内容评审续跑与八工作台。
