# 数据库健康锚点修复验证

2026-09-13T10:38:42.255491+08:00，基线84ca5d1e。
PreparationOwner接受可信异步health_clock，verify/control先取DB锚点再探测会话，提交仍用探测前时间。PreparationWorker通过既有scope runtime连接SELECT clock_timestamp读取，后台线程settle后返回，取消不遗留线程。未修改数据库/系统时钟、未扩大_fresh_health的[0,3]秒窗口；enable/renew复用control，同样使用DB观测锚点。无clock内部调用保持原行为。

RED新增4项Owner时钟测试因原构造不接受health_clock失败；修复后Owner/Worker/真实signed OCI共26通过（9.37秒）。随后完整切换+首次fenced+登记Owner+契约+准备Owner/Worker+signed OCI共132通过（33.81秒），0跳过，7既有警告。新增测试覆盖取时→健康→commit顺序、verify/control均不使用宿主观测时间、异常/naive/空时钟不探测不提交，以及4秒锚点仍被原_fresh_health拒绝。

84ca5d1e的106通过/1失败事实保留；本次明确复验其失败已消除。清册1819/158/93五类错误为空，diff-check通过。主库仍025、业务路由0，重启后的当前实例disabled/fenced且资源已释放，未真实恢复/激活。下一波按当前安装与新运行权威恢复实例，不能复用旧代次/旧许可。租约deadline其他跨时钟逻辑本波不声称全部收敛。
