# 固定登记验收执行器验证

先RED模块缺失；补执行器后原始占位负例发现同安装其他登记可能被误选（1 failed/4 passed），加入本周期key回读原Receipt、group/requestHash匹配后联合26 passed。未知登记和撤回均禁止重发，固定安装漂移拒绝，本地记录0600且不可覆盖。Fake Owner只验证执行器控制流；真实Owner周期尚待执行，不把本测试算主库验收。

准备动作从专用registration连接读取当前安装/binding/config并再走完整当前校验；不借默认owner越权，不动成员角色。成功登记也仅9条legacy/fenced占位，不能执行经营任务。
