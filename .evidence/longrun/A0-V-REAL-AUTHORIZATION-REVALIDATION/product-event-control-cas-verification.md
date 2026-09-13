# BG-02 绑定CAS与原控制回执连接

2026-09-14，基线95e57894。ProductEventBindingControlStore.apply先find原Receipt，再检查binding revision；初次enable复用put_binding/事务绑定连接，已有状态以CAS递增revision，随后ReceiptStore.put核验写后状态。disable不用来源/派发可用性，仍要求当前runtime scope和精确绑定；enable比对Owner提供的绑定及当前dispatch。无独立commit，上层事务失败一起回滚，尚无HTTP注册/当前审批Owner，不能作为执行许可。

原回执先行保证旧enable命令只返回历史结果，不把停用的绑定重新开启；新key且旧版本拒绝，新key+当前版本可由授权Owner开启。RED缺模块；初版direct FOR SHARE因dispatch表无UPDATE权限失败，移除该越权锁尝试，保持上层Host Owner先持既有派发锁、存储只读比对；未grant额外权限。测试管理身份只在独立库注入代际漂移。

最终46 passed无skip（CAS PG6项、回执7项、合同、Occurrence PG），含回执失败外层回滚、首次建立、新命令开启、原key保护及跨租户。日志/tmp/event-control-cas-{red,green,final,final2}.log。AR2扫描1874模块、166分类/93迁出错误数组为空，diff和memory验证通过。主库038/代码042，未注册或真实启用。

下一波当前审批/Host Owner：enable的批准必须绑定完整控制意图、当前角色/方法/来源/签名合同；disable仍必须当前有权调用者，并允许来源失效时停用。完成后才能登记新控制operation，接产品界面、原批次消费和自然Run。首链/八场景/连续观察未完成。
