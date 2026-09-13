# BG-02 业务应用保存与原键恢复

2026-09-14，基线a35c544a。EcommerceGrowthApplication新增save_event_policy，复用包命令构建器与原写端口，调用一次；响应严格核对策略/Case/批准/策略ref与bool重放标记，规范摘要防止bool/int弱比较，拒绝非JSON结果。超时原样抛出，不换key、不自动重试。调用者保留原binding/批准/key才可恢复。旧通用入口保持。

RED9项因缺方法失败；最终50 passed无skip（业务应用/命令/绑定/请求分派/HTTP/registry），日志/tmp/event-app-{red,green,final}.log。测试为具名端口替身，不是网络/自然链验收。AR2扫描1871模块、166分类/93迁出错误数组为空；diff通过。新方法未安装到旧运行包，主库038/代码041保持。

下一波事件绑定/消费：核对已有ScheduleBinding与record_event_batch、原批次候选Reader，设计当前来源/策略/派发资格同事务核验后写Occurrence的受控服务；不把策略保存等同启用、不把原批次读取等同自然触发完成。产品意图持久化/审批UI、真实发布评审、首链、八场景、连续观察继续待完成。
