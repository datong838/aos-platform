# 开发费用授权值对象验证

基线 1e1877ab，沿用 A0-V m1 Lease。新增 aip_development_cost_authorization.py 与专项测试，未更改现有策略、价格快照或 SQL。

23 项测试通过：合法边界接受；负租户、其他工作区、Provider hash/revision 漂移、模型或批准引用漂移、开始前/到期时/无时区均拒绝；未核价金额必须 null，不能填 0 或称 settled；token 为实测非负整数，拒绝 bool/float/负数和错误总量。既有 7 项 schema/deprecation 警告与 JDBC 测试退出日志错误仍存在。

合同只是嵌入现有策略的值对象，不能将其本身作为调用授权。没有发布策略，没有打开运行豁免，没有真实调用和数据变更。下一切片必须由现有策略 Owner 持有，兼容旧 hash，并在 Resolver/Invoker 中回读，随后实现 SQL 费用待核算状态与业务恢复。

与方案一致：尚未核价和实测用量是两个独立事实，代码不将未知费用转换为免费；商业默认规则不变。当前进度不代表 A0-V/首链完成。
