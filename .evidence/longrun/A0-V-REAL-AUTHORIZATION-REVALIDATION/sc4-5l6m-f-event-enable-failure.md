# F 事件入口与启用实测

- F Product Policy 已保存：product-event-qyh-full-store-generation-f-20260916 revision 1，Case case-qyh-full-store-baseline-20260915 version 3。
- 独立 exact 审批后的 event_control 入口扩展成功。
- 修复控制意图可选 receiptId 的 null/省略差异后，40 tests passed；提交 ee8146c1。
- 真实 enable-recovered 在 BoundEcommerceGrowthRuntimeStore.put 抛出 runtime Receipt operation drifted。审查发现 Python 白名单、ar2_005 数据库约束与写函数均遗漏 event_control。
- 独立主库回读：enabled=false；该 Policy automation_schedule_binding=0；该幂等键 control receipt=0。原操作完整回滚，未形成业务启用。
- 私有原始证据：.aos-recovery-20260916/state/growth-1.9-current-package/business/successor-f/event-enable/enable-recovered-failure-readback.json。
- 下一波次：a0v_058 回执账本补齐、隔离数据库验证、受控部署、当前源窗口重新评审后真实启用。首链及八工作台不宣称完成。
