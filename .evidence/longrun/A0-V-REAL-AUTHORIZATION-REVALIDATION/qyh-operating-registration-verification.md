# 正式运行登记固定profile自测

基线997fcda0。新profile缺失时1 failed/5 passed；复用执行器并增加精确前驱门后联合28 passed。覆盖新旧key/state隔离、默认参数不落旧目录、错误前驱拒绝、原默认unregistered路径、未知不重发等。尚未实际登记；下一动作prepare/register/read。原验收回执不修改，不启用业务路由。

## 实际运行登记回读（2026-09-13）

固定新键已完成 prepare/register/read/status；回执 c46bfc40-c1c8-41d4-b7c8-7a1d929c8102，组 b551fe9a-8462-4e85-9258-0a0151ac8e6d。与撤回的验收组不同，9 项均 legacy/fenced；status registered/unused_origin，executable=false。详见 qyh-operating-registration-real-result.json。无业务 Run 或路由启用。

下一波：核对生产 cutover Owner 装配和精确审批入口；当前只有 Store 实现，未找到产品调用方。不得绕过真实注册引用或通过直接改 dispatch 表完成切换。
