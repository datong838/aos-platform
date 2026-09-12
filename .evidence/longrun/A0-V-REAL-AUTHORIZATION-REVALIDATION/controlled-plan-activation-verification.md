# 受控计划执行快照验证

2026-09-13，基线930b88c0。持久图默认disabled不代表正式已批准计划具有可恢复启动投影；直接改缓存live会让旧公共执行入口变为可调用。现复用当前Control+不可变计划关联+计划enabled作为真实运行条件，从exact批准图构造本次controlled快照，不修改全局缓存或图。图revision/hash、pipeline、SNAPSHOT、节点归属及批准时间窗均校验；每个实际阶段仍按原CurrentControl/固定Run重验。

phase5只为exact ControlledScheduleExecution读取快照，用其节点执行原预检和工作线程。无受控对象不允许controlled模式。ec_live_executor在资源装配/源读取之前拒绝controlled快照。关闭计划/拒绝当前授权/关联变化不能产生快照；公共Pipeline缓存保留disabled，恢复不需开发者重新把缓存设live。没有新增授权表、请求回调或请求执行模式参数。

RED先复现3项缺口：批准快照不能执行、旧执行器打开资源、服务无snapshot；修复后联合148 passed，包括受控服务/线程/当前claim/完整PG持久层、原Phase5、旧ec-live-v1与执行诚实性测试。源fixture均明确标注；PG变更图版本后拒绝、当前拒绝不取源、恢复原输入不重取。

代码与方案复核：未全局启用任何Pipeline，未新增源调用/批准/计划；主库025不变。主API仍旧进程，这不是浏览器真实首链验收。后续配置新的本机API启动器，读取受保护runtime凭据引用，明确固定bundle/trust roots，禁用第二Host/cron/AIP自动作业/启动预连；健康与控制路由验证后，走实际登录principal创建/批准/绑定/启用首个P01计划。
