# 产品只读切换接口验证

基线890677ac。新增接口先10 failed/1 passed（原404恰好符合不存在用例，不作完整证明），实现后联合53 passed。覆盖认证Principal传递、外部身份不采纳、原key缺失/重复拒绝、安全错误、OpenAPI只读唯一和路径输入脱敏；既有登记与启动回归通过。AR2五类错误空，diff检查通过。

受控API预检GREEN，sourceCalls=0/runsCreated=0。仍是本地诊断metadata身份，productionWebIdentityComplete=false，不声称生产Web身份闭环。本次登记/切换使用独立受限身份。下一步提交后重载API并验证真实GET与浏览器；当前此文档尚无重载成功结论。

## 实际API重载与浏览器

已核对旧PID23116对应受控产品启动器后SIGTERM，使用同启动器加载c3e57bf9；新会话17152，日志/tmp/a0v-api-c3e57bf9.log。GET /v1/health=200、安装97a详情=200、带完整双租户请求头的默认用户切换history=403。初次探针误用/health/ready且漏租户头导致404/401，修正探针至代码中真实合同后通过，未改认证规则。结果cutover-read-http-live-result.json。

IAB 127.0.0.1:5173/apollo/assets刷新安装状态：97a active@5，generation3a445，enabled/ready，epoch3/binding4；默认账号登记状态无权限，未改角色。发现“当前安装没有可加载的前端扩展资源”，侧栏无可见电商入口；登记及切换历史后端就绪不等于八工作台可用。未点击停用、回滚、卸载。后续必须核验当前安装前端贡献及UI资源交付。
