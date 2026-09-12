# 启用后休眠失效的恢复施工

基线42d1cc15。真实安装af1992e8，generation bba8cd06，曾enable成功但尚未登记/切换电商业务调度。05:04复查已禁入、三资源confirmed released。

时间证据：系统12:34:45因Low Power Sleep进入休眠，12:57:37唤醒，间隔1372秒；最后续租12:34:24，租约12:37:24到期；Host12:57:42退出。过期资源不可复活，不能通过放宽TTL解决机器停机。当前安全禁入有效，真实恢复仍待实施。

第一项：scripts/a0v_ecommerce_runtime_host.py当前错误输出只有最后异常的栈，清理异常可能覆盖原始原因。增加有界errorChain，仅类型/栈位置及关联方式，不含异常message、args、locals或源码。捕获cause/context，循环去重、最多16项，每项最多32帧；保留旧errorType/frames字段兼容。测试services/aos-api/tests/extension_runtime/test_a0v_ecommerce_runtime_host.py覆盖嵌套清理异常、敏感message不泄漏、循环与截断，主入口确实落盘。

第二项：读取现有disable、uninstall、运行恢复合同；先正式disable相同installation/generation/binding revision，冻结命令并幂等回读。已enable而未dispatch的卸载与自动重建必须有独立exact证明，不套用never_enabled分支。若现有接口无此路径，先补方案、隔离PG验证，再在正常Owner权限内执行。不得借登记权限待批项增加权限。保留旧配置、旧enable及所有Receipt。

第三项：恢复后重新verify/configure/enable，跨初始期限且持续观察；本地休眠会中断worker，不能宣称具备无人值守在线服务。业务自然首链仍须先恢复真实源及正式调度登记，八场景和发布评估未完成。

禁用执行文件：scripts/a0v_ecommerce_1_7_disable.py增加--after-config-recovery，复用configuration_target读取已冻结新安装id，为旧e42和新af1992e8分别选择命令文件/幂等键，默认旧路径不变。tests/extension_runtime/test_a0v_recovered_configuration_target.py验证隔离选择。执行前检查无另一Host，启动新v11状态文件；原服务校验当前权限、exact版本，正常Host消费。只接受succeeded及真实disabled_committed回读，未知不重发新key。
