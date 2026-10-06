# 维护身份门阶段

新增门禁拒绝Owner/thread/base/authority/status/Delivery/缺Lease/重复Lease/receipt漂移/过期或无时区/资源范围缺失。13项新测试通过；相邻累计52passed1failed，旧测试使用当前live authority但旧执行器硬编码AOS-001329导致预期scope消息变成authority拒绝，不修改旧门、不宣称相邻全绿。新Task真实read_task成功，scope及Owner未来Lease一致。

仅实现身份预检，尚无服务停止/隔离窗口/当前迁移入口；代码Schema/备份/演练/源身份和进程绑定待接入。当前权威源和服务未改；Task保持ACTIVE。方案和当前阶段一致，测试只证明身份条件，不能证明迁移完成。
