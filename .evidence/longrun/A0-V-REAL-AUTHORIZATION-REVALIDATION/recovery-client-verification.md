# 恢复客户端请求身份验证

2026-09-11，基线bc1c09a9，A0V-RECOVERY-CLIENT-20260911。

新增apiPostImmediate离线直接拒绝，在线不入离线队列；现有apiPost/ReadOnly行为不变。scheduleRecovery提交前sessionStorage保存tenant/project/subject/schedule/run绑定claimId与原finishedAt；网络异常/duplicate保留，明确succeeded/failed仅在存储仍为同一请求时清理。刷新看到不同完成时间可建立新claim。缓存仅去重身份，不授予权限。

新增测试初始模块不存在而失败；最终8专项通过，包含未知重试同claim、明确完成后新claim、重复保留、跨run/tenant、旧响应不清新请求、存储失败不发送；离线客户端专项额外spy确认enqueue未调用。tsc --noEmit通过，diff-check通过。属于模拟传输与浏览器存储单测，不是实际页面验收。

限制：sessionStorage被用户清理/新标签页不共享时仍靠服务端原run claim门；页面忙碌锁/状态更新待接。UI尚未增加按钮，API未重载/public未迁移，真实首链和八工作台未完成。下一波dataSchedules实际按钮与浏览器检查。不push，230 L0挂起。
