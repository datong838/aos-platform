# AR1-c 资源组健康检查点

2026-09-06；基线m1@8b4a02a4 / AOS-000524；沿用AR1-C-LIFECYCLE-PERSISTENCE活动Lease。

已准备且仍由PreparationOwner持有的全部session接受并行受限心跳；前后检查owner状态，关闭后拒绝；任何失败/取消都drain检测任务并回收资源组。PreparedJob等待终结账本，不返回session或业务许可。兄弟检测及停止阶段的CleanupUncertainError优先保留精确异常对象，普通冲突/取消不得掩盖恢复引用。

测试：方法缺失Red 3failed，首次目标8passed/34deselected/14.80s；Prime指出异常覆盖与兄弟drain遗漏，新增反证3failed后修复；Owner/Worker18passed/7.04s。累计沿用preparation-owner-checkpoint.md命令444passed/6既有warnings/80.01s/exit0，含真实隔离PG、签名Registry、OCI容器及worker健康后binding仍0。既有JDBC退出日志问题未改。Prime增量只读复审确认组合路径修补，无新实质问题。

无页面改动，浏览器N/A；未写真实业务数据、未动共享DB、无Provider/费用/外部发布。新增业务场景0，整波仍IN_PROGRESS。下一段verify必须重新核对当前权限、签名、schema、配置、精确资源和期限；心跳不是可重放授权，尚不建立active/ready/enabled。
