# 固定登记验收执行器验证

先RED模块缺失；补执行器后原始占位负例发现同安装其他登记可能被误选（1 failed/4 passed），加入本周期key回读原Receipt、group/requestHash匹配后联合26 passed。未知登记和撤回均禁止重发，固定安装漂移拒绝，本地记录0600且不可覆盖。Fake Owner只验证执行器控制流；真实Owner周期尚待执行，不把本测试算主库验收。

准备动作从专用registration连接读取当前安装/binding/config并再走完整当前校验；不借默认owner越权，不动成员角色。成功登记也仅9条legacy/fenced占位，不能执行经营任务。


2026-09-13 真实Owner验收完成：登记c0eba9c8-afde-4fc3-b9cf-f83044e0dccf，group7ef2d562-0040-4fc1-8afc-d9850fb0fe05，实际9条legacy/fenced占位，executable=false；同key读原回执一致，status=registered/unused_origin。撤回6eb4bebb-1dfd-4453-bfd5-797531e1f683，releasedOperationCount=9；原登记历史和撤回历史均一致回读，status=withdrawn/no actions，业务路由0。绑定保持新代rev4/epoch3 ready/enabled/unfenced。真实记录见qyh-registration-cycle-real-result.json。

这是首次登记的原始占位恢复路径实证，不代表完整卸载重装、默认用户UI权限、cutover或经营首链完成。下一波用新的key/group准备正式运行登记；旧已撤回key不可复活，后续切换仍须当前Origin/Release/配置与exact授权核验。没有创建经营Run、外部发布或商业操作。
