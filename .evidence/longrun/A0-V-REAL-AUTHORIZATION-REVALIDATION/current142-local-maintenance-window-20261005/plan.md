# 本地维护通道零执行窗口隔离验证方案

前审计df7831e3：owner superuser与default read only off使0连接/advisory/revoke不能单独证明禁写。当前源只读操作边界维持。

本Task仅新nonce独立test-only容器/卷，无业务行/端口/网络/源卷，PG16已有本地镜像--pull never；任何旧演练目标及当前源均不修改。先在新目标默认TCP监听下真实检查TCP本地登录可达（只用该容器临时test-only角色，不读生产密码），再启动固定listen_addresses=''的本地socket维护服务，证明同容器TCP连接拒绝、socket维护连接成功、实际active client仅维护session；应用写者没有宿主入口。固定原容器角色/数据/版本身份，备份及恢复均使用显式docker exec本地socket；不能用test-only trust证明正式身份，也不能宣称这个测试能防已获docker exec权限的任意外部管理员。真正当前维护需停止已核实两个叶服务、防恢复器/并发写者、固定容器配置/监听回读，保留私有凭证与原恢复配置，单写Task/Lease持续约束本地管理员。

本轮仅证实隔离机制可行性，不执行源库listen修改或停止源服务。RED：关闭TCP后TCP应失败、socket应成功、外部端口为空；若未配置封锁而误报告窗口必须拒绝。使用实际进程/PG证据而非mock，失败保留容器/卷/日志；known terminal后新nonce继续，unknown先读对账不重启。所有目标保留，不删除卷；无页面代码，无浏览器验收。新增代码前另登记精确脚本/测试scope并完善维护时序与恢复合同。

实际probe terminal0：新容器aos-window-059e60cb41b0/新卷保留，无网络/端口，listen_addresses空；同容器TCP连接exit2而socket SELECT exit0，client backend仅本维护连接1。仅证明TCP-off+socket可用切面，没有默认TCP baseline/停写全备恢复/当前正式服务窗口；Task保持ACTIVE，不宣称完整窗口门。下一在同隔离测试状态补备份完整恢复和配置恢复时序，验收范围明确后才Delivery。
