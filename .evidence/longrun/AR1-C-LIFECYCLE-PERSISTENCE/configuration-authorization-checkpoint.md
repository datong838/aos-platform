# AR1-c 配置引用统一校验检查点

2026-09-06；基线3cdee39f/AOS-000533；实现由AR1-C-LIFECYCLE-PERSISTENCE主Lease覆盖，交付复核单独登记CHECKPOINT任务。

ConfigurationAuthorization按用途及authority精确选择受信同步reader；复制注册映射并只读封装，无通配或缺失回退。重验严格ConfigurationDocument和当前事务租户、actor；每次先独立复核当前actor权限，随后按role/data/budget/policy及authority/id稳定顺序逐引用校验，任何非严格True或延迟返回拒绝。reader复用同事务conn和精确目标；预算原对象不能凭真值充当许可。宿主仍须提供原权威当前有效性和持锁实现，没有以组合器替代正式接线。

Red14缺实现→14passed/6.84s；隔离配置存储测试改用此组合器，保留显式test_configuration权威SQL持锁reader，联合46passed/9.07s。增加5项登记/顺序反证后，最终累计640passed/6既有warnings/95.69s/exit0，含真实隔离OCI/PG。git diff --check通过，独立Prime只读审查无实质问题。既有退出JDBC关闭日志警告仍存在。

无页面、共享迁移、真实业务数据写或费用；不新增页面验收及业务场景完成结论。配置仍仅暂存，AR1-c IN_PROGRESS、新增业务场景0；下一项配置生效的排空确认与原子提交，不自动enable。
