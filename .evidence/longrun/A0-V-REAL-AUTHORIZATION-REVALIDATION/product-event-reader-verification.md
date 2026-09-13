# BG-02 当前来源事件候选读取验证

2026-09-14，基线de6efc2f。ProductEventCandidateReader仅接受PipelineSourceSelectionOwner，复用当前签名映射及安装/配置/期限锁定回调；固定平台店铺对象并使用来源行数限额。只返回事件元数据，不返回payload、不ACK投影、不创建Occurrence。

先缺模块RED；事件合同/读取边界与隔离PG累计30项通过。真实双连接临时schema验证：低序号事务晚提交仍被随后查询选中；其他租户Occurrence不误排、projected不影响、错店铺/对象/来源/窗口拒选。Owner拒绝及映射店铺漂移在边界测试中拒绝查询，明确这些fake不证明真实主库权限。diff通过，memory-validate GREEN。

没有主库部署或连接验收，没有生产消费者启用。尚缺完整事件校验、事件策略持久批准/绑定、与Occurrence同事务的接续及自然Run。下一波核对现有策略批准Owner与事件调度绑定合同，先确定复用路径，不增加另一个approved布尔值冒充权威。
