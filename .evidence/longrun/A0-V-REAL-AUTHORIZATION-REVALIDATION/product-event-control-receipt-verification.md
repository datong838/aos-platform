# BG-02 不可变控制回执存储

2026-09-14，基线c39c6bb7。a0v_042新增控制审计表，绑定状态仍只在automation_schedule_binding。表FORCE RLS，显式REVOKE PUBLIC及aos_runtime默认授权后仅SELECT/INSERT，immutable trigger阻止所有UPDATE/DELETE；非空downgrade拒绝，空表可回退重升。主库038未升级，代码HEAD042。

ProductEventControlReceiptStore只接HostTransaction/scope；严格解析命令，当前role/GUC检查，按policy→原key→binding锁序，核对写后绑定版本/意图/引用，保存原命令+actor+绑定快照摘要。回放返回原Receipt、不改binding；内部column/authority/command相关性复核。无独立连接/commit/启用操作。后续Owner必须先持相同policy锁再做CAS和回执写入。

RED缺模块；初次PG fixture缺完整安装字段，补齐字段后跑通；随后发现默认权限带DELETE，显式撤销修复。未关闭约束或不可变触发器。最终50 passed无skip（回执PG7项、控制合同、事件策略存储及OccurrencePG），含外层回滚、错版本、双tenant、原key冲突、旧enable回放不重新开启、owner也不能改回执、非空回退拒绝。安装fixture在外层回滚事务中，仅验证存储，不算完整安装生命周期/授权证明。日志/tmp/event-control-receipt-{red,green,green2,green3,final,final2}.log。

AR2扫描1873模块、166分类/93迁出错误数组为空；diff通过。下一波CAS状态更新与Receipt同事务服务，再连接当前角色/批准/签名Owner；尚未注册新增控制操作，也没有真实启用。原批次消费/自然Run/产品入口/真实首链/八场景/观察继续待完成。
