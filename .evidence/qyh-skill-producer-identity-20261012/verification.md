# 独立producer连接身份前置验收

初始RED为新模块缺失的collection error，不宣称原生业务失败。实现后12项原生测试通过、0skip、7既有warnings（5.48s）：真实独立LOGIN双角色正向、少/多角色、admin grant、LOGIN继承、membership继承/不可SET、LOGIN特权、错库、已切角色、管理员拒绝。原writer原生检查对双角色仍拒绝、撤finisher后单角色通过；没有修改原身份组件。

第一次包含旧凭证文件测试的相邻运行9pass/7skip，旧7项硬要求历史5433实验库，未重启/接管旧栈；不把跳过计通过。之后用同一当前隔离PG原生调用旧identity validator验证一角色正向/双角色负向，不修改旧测试或复制旧检查器。

新的12项仅在标准全schema UUID测试DB/18431，使用新测试LOGIN、临时NOLOGIN finisher，测试后清理新角色/成员/CONNECT，未给真实库或旧writer增加Run权限。新函数只检查认证连接及角色图，无配置加载、credential读取、业务调用或执行权授予。有限图检查不能替代实际权限、Owner/预算/审批/签名/tenant/currentness；完整终结和正式producer仍PENDING。方案/代码一致，原功能未修改；无页面变化所以无浏览器验收。
