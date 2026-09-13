# 产品只读切换接口验证

基线890677ac。新增接口先10 failed/1 passed（原404恰好符合不存在用例，不作完整证明），实现后联合53 passed。覆盖认证Principal传递、外部身份不采纳、原key缺失/重复拒绝、安全错误、OpenAPI只读唯一和路径输入脱敏；既有登记与启动回归通过。AR2五类错误空，diff检查通过。

受控API预检GREEN，sourceCalls=0/runsCreated=0。仍是本地诊断metadata身份，productionWebIdentityComplete=false，不声称生产Web身份闭环。本次登记/切换使用独立受限身份。下一步提交后重载API并验证真实GET与浏览器；当前此文档尚无重载成功结论。
