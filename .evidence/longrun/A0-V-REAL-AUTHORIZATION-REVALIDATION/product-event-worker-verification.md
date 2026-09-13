# BG-02 生命周期worker接线验证

基线41a7e40e。ACTIVE runtime host且平台Factory/LiveDirectory完整时，main将ProductEventConsumptionWorker加入统一background tasks并共享stop事件；host退出后不继续tick。每轮最多4个target、各5个候选，字典序分页+回绕只决定扫描顺序，实际业务去重仍Occurrence。当前membership/bearer markings来自DB，不继承安装所需权限作为自身授权。原actor/run/current controlRef进入completed-read consumer；单候选失败记录固定异常类型与身份，不打印业务载荷/秘密，继续后项；取消不吞。

RED缺worker模块；首轮worker/旧startup21通过；补实际main生命周期挂接、五目标轮转与SQL/消费PG回归后38项通过（7条既有依赖警告）。安装和Source/IPC仍命名替身，SQL/Occurrence在18432临时关系/库真实执行；不能当作新签名包已在实际运行。AR2-7扫描1883/分类168/迁移93，各错误数组空，diff通过。

源码存在生产调用链：main→worker→当前目录/候选发现→工厂→completed-read原批次→已安装core纯计算→当前事务重验→Occurrence/outbox。当前服务未重启，主库仍未迁移到042，新core/growth未发布安装，故真实运行尚未走此链。下一项Occurrence领取到分析Run/Receipt的正式处理器，随后新候选独立评审、安装配置启用、栖月汇实链和八场景连续观察。未push。
