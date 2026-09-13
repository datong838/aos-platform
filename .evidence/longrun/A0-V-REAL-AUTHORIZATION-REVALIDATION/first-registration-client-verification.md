# 登记客户端合同验证｜2026-09-13

基线3e638c9f。第1/6复核现有客户端/认证/读取状态机；第2/6完善withdrawal-design前端合同；第3/6新增parser测试RED后实现严格响应解析与GET适配；第4/6补错安装/不可用不重试/可信headers；第5/6 Vitest两文件24项通过、tsc --noEmit通过；第6/6本片提交后直接进入页面状态与撤回操作接线。

文件apps/web/src/api/assetControl/{registrationStatus.ts,registrationStatus.test.ts,client.ts,client.test.ts,operations.ts}。状态不一致、未知动作、不安全etag、无ref拒绝；唯一GET走原认证体系且校验installationId，不发写请求、不生成手填key、不持久化响应。日志/tmp/a0v-status-client-final.log和/tmp/a0v-status-client-tsc.log。该片没有页面变更，浏览器验收在下一片；不声称主库或首链通过。
