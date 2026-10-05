# 本地维护通道零执行窗口隔离验证方案

前审计df7831e3：owner superuser与default read only off使0连接/advisory/revoke不能单独证明禁写。当前源只读操作边界维持。

本Task仅新nonce独立test-only容器/卷，无业务行/端口/网络/源卷，PG16已有本地镜像--pull never；任何旧演练目标及当前源均不修改。先在新目标默认TCP监听下真实检查TCP本地登录可达（只用该容器临时test-only角色，不读生产密码），再启动固定listen_addresses=''的本地socket维护服务，证明同容器TCP连接拒绝、socket维护连接成功、实际active client仅维护session；应用写者没有宿主入口。固定原容器角色/数据/版本身份，备份及恢复均使用显式docker exec本地socket；不能用test-only trust证明正式身份，也不能宣称这个测试能防已获docker exec权限的任意外部管理员。真正当前维护需停止已核实两个叶服务、防恢复器/并发写者、固定容器配置/监听回读，保留私有凭证与原恢复配置，单写Task/Lease持续约束本地管理员。

本轮仅证实隔离机制可行性，不执行源库listen修改或停止源服务。RED：关闭TCP后TCP应失败、socket应成功、外部端口为空；若未配置封锁而误报告窗口必须拒绝。使用实际进程/PG证据而非mock，失败保留容器/卷/日志；known terminal后新nonce继续，unknown先读对账不重启。所有目标保留，不删除卷；无页面代码，无浏览器验收。新增代码前另登记精确脚本/测试scope并完善维护时序与恢复合同。

实际probe terminal0：新容器aos-window-059e60cb41b0/新卷保留，无网络/端口，listen_addresses空；同容器TCP连接exit2而socket SELECT exit0，client backend仅本维护连接1。仅证明TCP-off+socket可用切面，没有默认TCP baseline/停写全备恢复/当前正式服务窗口；Task保持ACTIVE，不宣称完整窗口门。下一在同隔离测试状态补备份完整恢复和配置恢复时序，验收范围明确后才Delivery。

本轮具体验证：新nonce容器bootstrap aos_app/无端口无网络，默认同容器TCP baseline；只在本轮新目标ALTER SYSTEM listen_addresses=''并重启，实际TCP拒绝后经socket恢复私有r4完整globals及135 archive，沿用5183ed2d snapshot精确比较592原表及数据库/角色权限。维护态经socket再生成完整新dump，在同本轮容器中新建restored database不可保持原名故采用另一全新nonce容器，恢复--create保持原名并精确比较。最后仅本轮新目标恢复listen_addresses='*'并重启，实测同容器TCP恢复可达、外部仍无端口/网络；旧probe/clone、源库及源服务均不动。记录实际配置往返，不以test-only socket登录代替正式身份。所有目标、卷及私有备份保留。

实际完整演练terminal0/17.52s：新两个容器aos-windowfull-947482cf9502/aos-windowfull-d6b835501d51，从默认TCP正向→ALTER SYSTEM监听空+实际重启→TCP拒绝/socket成立→r4完整原globals及135archive恢复精确592表/原权限→socket维护dump4218721bytes SHA4cd31f7df5419bc64b2c72e2eeb09e495367fa84a26539823c02311c6ebb7020→第二目标完整--create恢复精确→两个目标恢复监听*并实际重启/TCP正向→全状态摘要仍一致。所有卷/私有资料保留，旧目标和当前源未碰。full-verification.json记录范围，current_zero_execution_window=false。不是正式身份/自然首链验收，也不防持有容器管理权的第二管理员；当前门仍须唯一维护执行者与对可达恢复器/外部角色的控制归属闭合。
